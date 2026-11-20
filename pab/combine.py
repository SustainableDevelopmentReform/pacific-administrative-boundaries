"""Per-country tables -> data/combined/pacific_admin.parquet and pacific_admin_finest.parquet.

Licence-restricted rows are excluded from both combined products (spec section 5/brief).

Finest partition (spec section 8), built per country in EPSG:3832:

1. start from admin0; for each nesting admin level, replace every piece by its children
   (children clipped to the piece; siblings may not overlap, earlier code wins); the part of a
   piece not covered by children stays as the coarser unit (partial-coverage fallback);
2. clip land pieces to the country's 200NM EEZ polygons (hole-filled), splitting and flagging
   pieces that straddle EEZ lines; land beyond every EEZ outline (PNG mainland) is kept,
   attached to its unit's EEZ, and the zone domain is (EEZ outline + that land);
3. marine remainder = EEZ (hole-filled) minus land pieces, one row per EEZ polygon;
4. overlapping-claim / joint-regime polygons are added once each as marine rows.
"""

from __future__ import annotations

import logging
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry.base import BaseGeometry

from pab import geom, registry
from pab import io as pio
from pab.registry import ADMIN_CODES

logger = logging.getLogger(__name__)

COMBINED_DIR = "data/combined"
LONG_PATH = f"{COMBINED_DIR}/pacific_admin.parquet"
FINEST_PATH = f"{COMBINED_DIR}/pacific_admin_finest.parquet"
MIN_PIECE_M2 = 1.0  # drop slivers below 1 m2 (EPSG:3832 units)

FINEST_COLUMNS = [
    "uid", "iso3", "country_name", "sovereign_iso3", "political_status", "eez_uid", "eez_name", "is_marine",
    "finest_level_code", "finest_level_type",
    "admin0_uid", "admin0_name",
    *[f"admin{i}_{s}" for i in range(1, 6) for s in ("uid", "name", "type")],
    "source_ids", "license", "license_agreement", "geometry_method", "area_km2", "geometry",
]  # fmt: skip


#: separator for several agreements in one finest-partition row (agreement texts may hold ';')
AGREEMENT_SEP = " | "


def _joined(values: list[object], sep: str = ";") -> str | None:
    """Distinct non-null values joined with ``sep`` (None when there are none)."""
    out = [str(v) for v in dict.fromkeys(values) if v is not None and not pd.isna(v)]
    return sep.join(out) or None


def land_partition(country: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    """Planar partition of a country's admin0 into its finest nesting units.

    ``country`` holds one country's (open) long-table rows. Returns pieces as dicts with
    ``geom`` (EPSG:3832) and ``chain`` ({level_code: row Series}).
    """
    nest = country[(country["level_code"].isin(ADMIN_CODES)) & country["nests"]]
    a0 = nest[nest["level_code"] == "admin0"]
    if len(a0) != 1:
        raise ValueError(f"expected exactly one admin0 row, found {len(a0)}")
    proj = dict(zip(nest["uid"], geom.to_overlay(list(nest.geometry)), strict=True))
    rows = {
        u: r for u, r in zip(nest["uid"], nest.itertuples(index=False), strict=True)
    }
    pieces = [
        {
            "geom": shapely.make_valid(proj[a0["uid"].iloc[0]]),
            "chain": {"admin0": rows[a0["uid"].iloc[0]]},
            "methods": [],
        }
    ]
    for level in ADMIN_CODES[1:]:
        kids = nest[nest["level_code"] == level]
        if kids.empty:
            continue
        by_parent = {
            p: grp.sort_values("unit_code") for p, grp in kids.groupby("parent_uid")
        }
        nxt = []
        for pc in pieces:
            deepest = pc["chain"][max(pc["chain"], key=ADMIN_CODES.index)]
            grp = by_parent.get(deepest.uid)
            if grp is None:
                nxt.append(pc)
                continue
            remaining = pc["geom"]
            for kid in grp.itertuples(index=False):
                if remaining.is_empty:
                    break
                g = shapely.make_valid(shapely.intersection(proj[kid.uid], remaining))
                g = _polys(g)
                if g.is_empty or g.area < MIN_PIECE_M2:
                    continue
                nxt.append(
                    {
                        "geom": g,
                        "chain": {**pc["chain"], level: rows[kid.uid]},
                        "methods": pc["methods"],
                    }
                )
                remaining = _polys(shapely.make_valid(shapely.difference(remaining, g)))
            if not remaining.is_empty and remaining.area >= MIN_PIECE_M2:
                nxt.append(
                    {
                        "geom": remaining,
                        "chain": pc["chain"],
                        "methods": [*pc["methods"], f"no_{level}_coverage"],
                    }
                )
        pieces = nxt
    return pieces


def _polys(g: BaseGeometry) -> shapely.MultiPolygon:
    parts = geom.polygonal_parts(g)
    return shapely.MultiPolygon(parts) if parts else shapely.MultiPolygon()


def _row(
    piece: dict[str, Any], meta: dict[str, Any], eez: tuple[str | None, str | None]
) -> dict[str, Any]:
    chain = piece["chain"]
    deepest_level = max(chain, key=ADMIN_CODES.index)
    d = chain[deepest_level]
    r: dict[str, Any] = {
        "uid": d.uid,
        "iso3": meta["iso3"],
        "country_name": meta["name"],
        "sovereign_iso3": meta["sovereign_iso3"],
        "political_status": meta["political_status"],
        "eez_uid": eez[0],
        "eez_name": eez[1],
        "is_marine": False,
        "finest_level_code": deepest_level,
        "finest_level_type": d.level_type,
        "admin0_uid": chain["admin0"].uid,
        "admin0_name": chain["admin0"].unit_name,
        "source_ids": ";".join(
            dict.fromkeys(chain[lv].source_id for lv in ADMIN_CODES if lv in chain)
        ),
        "license": _joined([chain[lv].license for lv in ADMIN_CODES if lv in chain]),
        "license_agreement": _joined(
            [
                getattr(chain[lv], "license_agreement", None)
                for lv in ADMIN_CODES
                if lv in chain
            ],
            AGREEMENT_SEP,
        ),
        "geometry_method": ";".join(piece["methods"]) or "as_published",
        "geom": piece["geom"],
    }
    for i in range(1, 6):
        c = chain.get(f"admin{i}")
        r[f"admin{i}_uid"] = c.uid if c is not None else None
        r[f"admin{i}_name"] = c.unit_name if c is not None else None
        r[f"admin{i}_type"] = c.level_type if c is not None else None
    return r


def country_finest(
    country: gpd.GeoDataFrame, eez_rows: gpd.GeoDataFrame | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Finest-partition rows for one country plus area-check stats."""
    from pab.eez import outline_overlay

    iso3 = country["iso3"].iloc[0]
    meta = {**registry.country_meta(iso3), "iso3": iso3}
    pieces = land_partition(country)
    stats: dict[str, Any] = {"iso3": iso3, "land_pieces": len(pieces)}
    a0_area = float(country.loc[country["level_code"] == "admin0", "area_km2"].iloc[0])
    land_area = sum(geom.area_km2([geom.from_overlay(p["geom"])])[0] for p in pieces)
    stats["admin0_km2"] = round(a0_area, 4)
    stats["land_pieces_km2"] = round(float(land_area), 4)
    out: list[dict[str, Any]] = []
    zones = (
        eez_rows[eez_rows["nests"]] if eez_rows is not None and len(eez_rows) else None
    )
    if zones is None or zones.empty:
        for p in pieces:
            out.append(_row(p, meta, (None, None)))
        stats["eez"] = "not available"
        return out, stats
    zg = {r.uid: outline_overlay(r.geometry, r.source_id) for r in zones.itertuples()}
    zname = dict(zip(zones["uid"], zones["unit_name"], strict=True))
    land_in_zone: dict[str, list[Any]] = {u: [] for u in zg}
    beyond: dict[str, list[Any]] = {u: [] for u in zg}
    all_zones = shapely.union_all(list(zg.values()))
    for p in pieces:
        placed = []
        for zu, z in zg.items():
            g = _polys(shapely.make_valid(shapely.intersection(p["geom"], z)))
            if not g.is_empty and g.area >= MIN_PIECE_M2:
                placed.append((zu, g, "clipped_to_eez"))
        rest = _polys(shapely.make_valid(shapely.difference(p["geom"], all_zones)))
        if not rest.is_empty and rest.area >= MIN_PIECE_M2:
            # land beyond every EEZ outline (e.g. PNG mainland on the land border): keep it,
            # attached to the unit's own EEZ (or the nearest zone)
            deepest = p["chain"][max(p["chain"], key=ADMIN_CODES.index)]
            zu = getattr(deepest, "eez_uid", None)
            if zu not in zg:
                zu = min(zg, key=lambda u: shapely.distance(rest, zg[u]))
            placed.append((zu, rest, "land_outside_eez_outline"))
            beyond[zu].append(rest)
        # one row per (unit, zone): merge the in-outline and beyond-outline parts of a unit
        merged: dict[str, tuple[list[Any], list[str]]] = {}
        for zu, g, token in placed:
            merged.setdefault(zu, ([], []))
            merged[zu][0].append(g)
            merged[zu][1].append(token)
        for zu, (gs, tokens) in merged.items():
            g = (
                gs[0]
                if len(gs) == 1
                else _polys(shapely.make_valid(shapely.union_all(gs)))
            )
            extra = [
                t
                for t in dict.fromkeys(tokens)
                if len(merged) > 1 or t != "clipped_to_eez"
            ]
            out.append(
                _row(
                    {**p, "geom": g, "methods": [*p["methods"], *extra]},
                    meta,
                    (zu, zname[zu]),
                )
            )
            land_in_zone[zu].append(g)
    checks = []
    for zu, z in zg.items():
        land = (
            shapely.union_all(land_in_zone[zu])
            if land_in_zone[zu]
            else shapely.MultiPolygon()
        )
        marine = _polys(shapely.make_valid(shapely.difference(z, land)))
        out.append(
            _marine_row(
                meta,
                zu,
                zname[zu],
                marine,
                zones.loc[zones["uid"] == zu].iloc[0],
            )
        )
        domain = shapely.union_all([z, *beyond[zu]])
        out_km2 = (
            float(geom.area_km2([geom.from_overlay(shapely.union_all(beyond[zu]))])[0])
            if beyond[zu]
            else 0.0
        )
        checks.append(
            {
                "eez_uid": zu,
                "zone_km2": float(geom.area_km2([geom.from_overlay(domain)])[0]),
                "land_outside_outline_km2": round(out_km2, 4),
            }
        )
    stats["zones"] = checks
    return out, stats


def _marine_row(
    meta: dict[str, Any],
    eez_uid: str,
    eez_name: str,
    g: BaseGeometry,
    eez_row: Any,  # noqa: ANN401 - long-table row (itertuples/Series) of the EEZ polygon
) -> dict[str, Any]:
    r = {
        "uid": f"{meta['iso3']}:marine:{eez_uid}",
        "iso3": meta["iso3"],
        "country_name": meta["name"],
        "sovereign_iso3": meta["sovereign_iso3"],
        "political_status": meta["political_status"],
        "eez_uid": eez_uid,
        "eez_name": eez_name,
        "is_marine": True,
        "finest_level_code": "eez",
        "finest_level_type": "eez",
        "admin0_uid": None,
        "admin0_name": None,
        "source_ids": eez_row.source_id,
        "license": eez_row.license,
        "license_agreement": _joined([getattr(eez_row, "license_agreement", None)]),
        "geometry_method": "eez_minus_land",
        "geom": g,
    }
    for i in range(1, 6):
        for s in ("uid", "name", "type"):
            r[f"admin{i}_{s}"] = None
    return r


def combine(overwrite: bool = False, iso3s: list[str] | None = None) -> dict[str, Any]:
    """Build both combined products. Returns area-check statistics."""
    from pab import eez as eezmod
    from pab import process

    if pio.exists(FINEST_PATH) and pio.exists(LONG_PATH) and not overwrite:
        logger.info("combined products exist; use --overwrite")
        return {}
    iso3s = iso3s or [
        i for i in registry.all_iso3() if pio.exists(process.admin_path(i))
    ]
    tables = [process.load_country(i) for i in iso3s]  # restricted rows dropped below
    long = pd.concat(tables, ignore_index=True)
    restricted = long[long["license_restricted"]]
    open_rows = gpd.GeoDataFrame(
        long[~long["license_restricted"]], geometry="geometry", crs=geom.STORAGE_CRS
    )
    open_rows = open_rows.sort_values(
        list(process.SORT_KEYS), kind="stable"
    ).reset_index(drop=True)
    pio.write_geoparquet(open_rows, LONG_PATH)
    logger.info(
        "wrote %d rows (%d restricted excluded) to %s",
        len(open_rows),
        len(restricted),
        LONG_PATH,
    )

    rows: list[dict[str, Any]] = []
    stats: list[dict[str, Any]] = []
    eez_all = eezmod.load_eez() if eezmod.eez_available() else None
    for iso3 in iso3s:
        c = open_rows[open_rows["iso3"] == iso3]
        ez = c[c["level_code"] == "eez"] if (c["level_code"] == "eez").any() else None
        r, s = country_finest(c, ez)
        rows.extend(r)
        stats.append(s)
        logger.info("%s: %d finest rows", iso3, len(r))
    if eez_all is not None:
        for e in eez_all[~eez_all["nests"]].itertuples():
            claim = [c for c in e.claimants.split(";") if c in registry.countries()]
            meta = {**registry.country_meta(claim[0]), "iso3": claim[0]}
            g = geom.to_overlay([e.geometry])[0]
            rr = _marine_row(
                meta,
                e.uid,
                f"{e.unit_name} [{e.pol_type}; claimants {e.claimants}]",
                g,
                e,
            )
            rr["geometry_method"] = (
                f"as_published;{e.pol_type.lower().replace(' ', '_')}"
            )
            rows.append(rr)
    fin = pd.DataFrame(rows)
    fin["geometry"] = [geom.from_overlay(g) for g in fin.pop("geom")]
    fin = gpd.GeoDataFrame(fin, geometry="geometry", crs=geom.STORAGE_CRS)
    fin = fin[~fin.geometry.is_empty]
    fin["area_km2"] = geom.area_km2(fin.geometry)
    fin = (
        fin[FINEST_COLUMNS]
        .sort_values(["iso3", "is_marine", "uid"], kind="stable")
        .reset_index(drop=True)
    )
    fin["is_marine"] = fin["is_marine"].astype(bool)
    pio.write_geoparquet(fin, FINEST_PATH)
    logger.info("wrote %d rows to %s", len(fin), FINEST_PATH)
    if eez_all is not None:
        eezmod.set_land_marine(zone_areas(fin))
    checks = area_checks(fin, stats)
    pio.write_json(
        f"{COMBINED_DIR}/partition_checks.json",
        {
            "checks": checks,
            "restricted_rows_excluded": {
                f"{k[0]}:{k[1]}": int(v)
                for k, v in restricted.groupby(["iso3", "level_code"]).size().items()
            },
            "finest_rows_by_level": fin.groupby("finest_level_code").size().to_dict(),
        },
    )
    from pab.provenance import append_step, step_record

    append_step(
        f"{COMBINED_DIR}/provenance.json",
        step_record(
            "combine",
            inputs={
                "country_tables": [process.admin_path(i) for i in iso3s],
                "eez": eezmod.EEZ_PATH if eez_all is not None else None,
            },
            outputs={
                "long": LONG_PATH,
                "long_rows": len(open_rows),
                "restricted_rows_excluded": len(restricted),
                "finest": FINEST_PATH,
                "finest_rows": len(fin),
                "eez_land_marine_km2": eezmod.EEZ_PATH if eez_all is not None else None,
            },
        ),
    )
    return {
        "stats": stats,
        "checks": checks,
        "restricted": restricted.groupby(["iso3", "level_code"]).size().to_dict(),
    }


def zone_areas(fin: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """(land km2, marine km2) per EEZ uid from the finest partition (D-024)."""
    out: dict[str, tuple[float, float]] = {}
    for zu, grp in fin.groupby("eez_uid"):
        land = float(grp.loc[~grp["is_marine"], "area_km2"].sum())
        marine = float(grp.loc[grp["is_marine"], "area_km2"].sum())
        out[str(zu)] = (round(land, 4), round(marine, 4))
    return out


def area_checks(
    fin: gpd.GeoDataFrame, stats: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Sum of partition parts per EEZ vs the zone domain (hole-filled EEZ + attached land); tolerance 0.01 %."""
    out = []
    for s in stats:
        for z in s.get("zones", []):
            parts = fin.loc[fin["eez_uid"] == z["eez_uid"], "area_km2"].sum()
            diff = (
                100 * (parts - z["zone_km2"]) / z["zone_km2"]
                if z["zone_km2"]
                else np.nan
            )
            out.append(
                {
                    "iso3": s["iso3"],
                    "eez_uid": z["eez_uid"],
                    "eez_km2": round(z["zone_km2"], 1),
                    "parts_km2": round(float(parts), 1),
                    "diff_pct": round(float(diff), 5),
                    "ok": bool(abs(diff) <= 0.01),
                    "land_outside_outline_km2": z.get("land_outside_outline_km2", 0.0),
                }
            )
    return out
