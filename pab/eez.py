"""EEZ stage: EEZ polygons -> data/processed/EEZ/pacific_eez.parquet, and eez_uid assignment.

Polygon selection comes from ``config/eez_polygons.csv`` (rows with ``relevance`` ``pict`` or
``shared``; ``pab_iso3`` may list several PICTs, e.g. ``NCL;VUT``). Column names are matched
case-insensitively. Each row names the polygon by ``mrgid`` and, optionally, where to read it
from: ``source_id`` (a source in config/sources/EEZ.yml) and ``layer`` (a file under that
source's ``raw_path``, e.g. ``extracted/fj_eez_pol.shp``; a bare layer name such as
``fj_eez_pol`` is looked up as ``extracted/<name>.shp``). Rows without them fall back to the
register's ``selected`` source and its level ``layer`` (the Marine Regions single-layer reader).

Both readers expect the Marine Regions attribute schema in lower case (``mrgid``, ``geoname``,
``pol_type``, ``territory1``, ``iso_ter1``, ``sovereign1``, ``iso_sov1``, ``mrgid_eez``,
``area_km2``; SPC Pacific Maritime Boundaries layers add ``source``, the legal instrument the
limits are built from, kept as ``boundary_source``). Rulings E-009/E-010: overlapping claims and
joint regimes are kept as flagged rows (``nests = false``) and never used to assign ``eez_uid``
to land units; only ``200NM`` polygons are.

``assign_country`` is a separate, re-runnable step: it (re)stamps ``eez_uid`` on every land
unit of a per-country table by majority area and (re)inserts that country's EEZ rows.
"""

from __future__ import annotations

import logging
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from pab import geom, licenses, registry
from pab import io as pio
from pab.process import (
    LONG_COLUMNS,
    NULLABLE_STR,
    SORT_KEYS,
    _as_date,
    _manifest_time,
)
from pab.provenance import append_step, step_record

logger = logging.getLogger(__name__)

EEZ_DIR = "data/processed/EEZ"
EEZ_PATH = f"{EEZ_DIR}/pacific_eez.parquet"
EEZ_EXTRA = [
    "mrgid",
    "pol_type",
    "claimants",
    "mrgid_eez",
    "area_km2_published",
    "boundary_source",
    "attribute_notes",
    "land_km2",
    "marine_km2",
]
#: sources whose EEZ polygons cut land out as holes (Marine Regions); the zone domain is then
#: the outline with holes filled. Other sources (SPC, D-024) publish solid zones: domain as is.
HOLES_ARE_LAND = {"marineregions-eez-v12", "marineregions-eez-boundaries-v12"}
#: known attribute faults corrected in processing (D-025): (source_id, mrgid) -> {field: value}
ATTRIBUTE_FIXES: dict[tuple[str, str], dict[str, str]] = {
    # SPC codes MHL (8318) with mrgid_eez 8319 and Wake (8319) with 8318: swapped
    ("spc-gem-pacific-eez-200nm", "8318"): {"mrgid_eez": "8318"},
    ("spc-gem-pacific-eez-200nm", "8319"): {"mrgid_eez": "8319"},
}
SELECTION_CSV = "config/eez_polygons.csv"
#: published areas above this are taken to be in m2 (some SPC layers), not km2
_AREA_M2_THRESHOLD = 1e8


def eez_available() -> bool:
    """True once the EEZ product has been built."""
    return pio.exists(EEZ_PATH)


def _mrgid(v: object) -> str | None:
    """MRGID as a plain integer string ('8325.0' -> '8325'); None for blanks."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() == "":
        return None
    return str(int(float(str(v).strip())))


def _pol_type(v: object) -> str:
    """Normalise ``pol_type`` spellings ('200 NM' -> '200NM')."""
    t = str(v or "").strip()
    return "200NM" if t.replace(" ", "").upper() == "200NM" else t


def selection(reg: dict[str, Any] | None = None) -> pd.DataFrame:
    """PICT-relevant rows of config/eez_polygons.csv with ``source_id``/``layer`` filled in.

    Columns are lower-cased; ``claimants`` is a list of ISO3 codes; ``mrgid`` is an integer
    string. Rows without a ``source_id``/``layer`` get the register's selected source and its
    level layer.
    """
    from io import BytesIO

    sel = pd.read_csv(BytesIO(pio.read_bytes(SELECTION_CSV)), dtype=str)
    sel.columns = [c.strip().lower() for c in sel.columns]
    sel = sel[sel["relevance"].isin(["pict", "shared"])].copy()
    sel["mrgid"] = sel["mrgid"].map(_mrgid)
    sel["claimants"] = (
        sel["pab_iso3"]
        .fillna("")
        .map(lambda s: [x.strip() for x in s.split(";") if x.strip()])
    )
    reg = reg or registry.load_register("EEZ")
    default = next(s for s in reg["sources"] if s["status"] == "selected")
    for col, fallback in (
        ("source_id", default["source_id"]),
        ("layer", None),
    ):
        if col not in sel:
            sel[col] = None
        sel[col] = sel[col].where(sel[col].notna() & (sel[col] != ""), fallback)
    by_id = {s["source_id"]: s for s in reg["sources"]}
    unknown = set(sel["source_id"]) - set(by_id)
    if unknown:
        raise ValueError(
            f"{SELECTION_CSV}: source_id(s) not in config/sources/EEZ.yml: {sorted(unknown)}"
        )
    sel["layer"] = [
        lay if isinstance(lay, str) and lay.strip() else _default_layer(by_id[sid])
        for sid, lay in zip(sel["source_id"], sel["layer"], strict=True)
    ]
    return sel.reset_index(drop=True)


def _default_layer(src: dict[str, Any]) -> str:
    levels = src.get("levels") or []
    if not levels or not levels[0].get("layer"):
        raise ValueError(f"{src['source_id']}: no level layer and no `layer` in CSV")
    return levels[0]["layer"]


def _layer_path(src: dict[str, Any], layer: str) -> str:
    """Resolve a CSV/register layer name to a path relative to the source's raw_path."""
    root = src["raw_path"].rstrip("/")
    base = layer.strip()
    cands = [base]
    if "/" not in base:
        cands.append(f"extracted/{base}")
    if (
        not base.lower().endswith((".shp", ".gpkg", ".geojson", ".zip"))
        and "::" not in base
    ):
        cands += [f"{c}.shp" for c in list(cands)]
    for c in cands:
        if pio.exists(f"{root}/{c.partition('::')[0]}"):
            return c
    raise FileNotFoundError(
        f"{src['source_id']}: layer {layer!r} not found under {root}"
    )


def read_polygons(src: dict[str, Any], layer: str) -> gpd.GeoDataFrame:
    """Read one EEZ layer (Marine Regions or SPC schema) with lower-case columns.

    ``mrgid`` becomes an integer string and ``pol_type`` is normalised.
    """
    from pab import layers

    raw = layers.read_layer(src, _layer_path(src, layer))
    raw.columns = [c.lower() if c != "geometry" else c for c in raw.columns]
    raw = raw.set_geometry("geometry")
    raw["mrgid"] = raw["mrgid"].map(_mrgid)
    if "pol_type" in raw:
        raw["pol_type"] = raw["pol_type"].map(_pol_type)
    return raw


def _published_area(*vals: object, notes: list[str] | None = None) -> float | None:
    """First usable published area in km2 (values above 1e8 are converted from m2).

    Zero or negative values are treated as missing. Corrections are appended to ``notes``.
    """
    for v in vals:
        try:
            a = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if np.isnan(a):
            continue
        if a <= 0:
            if notes is not None:
                notes.append(f"area_km2 attribute {a:g} treated as missing")
            continue
        if a > _AREA_M2_THRESHOLD:
            logger.warning("published EEZ area %s looks like m2; converted to km2", a)
            if notes is not None:
                notes.append(f"area_km2 attribute {a:.0f} is in m2; converted to km2")
            a = a / 1e6
        return round(a, 1)
    return None


def _attribute_notes(
    src_id: str, mrgid: str, f0: pd.Series, claim: str, pol: str, raw_pol: str | None
) -> tuple[dict[str, str], list[str]]:
    """Corrections for known SPC attribute faults (D-025) and the notes describing them."""
    fixes = dict(ATTRIBUTE_FIXES.get((src_id, mrgid), {}))
    notes = [
        f"{k} {_mrgid(f0.get(k)) or f0.get(k)} corrected to {v}"
        for k, v in fixes.items()
        if str(_mrgid(f0.get(k)) or f0.get(k)) != v
    ]
    iso = _first(f0, "iso_ter1")
    if pol == "200NM" and iso and iso.upper() != claim:
        notes.append(f"iso_ter1 {iso!r} read as {claim}")
    if raw_pol and raw_pol != pol:
        notes.append(f"pol_type {raw_pol!r} normalised to {pol!r}")
    return fixes, notes


def _first(row: pd.Series | None, *cols: str) -> str | None:
    if row is None:
        return None
    for c in cols:
        v = row.get(c)
        if (
            v is not None
            and not (isinstance(v, float) and np.isnan(v))
            and str(v).strip()
        ):
            return str(v).strip()
    return None


def _pict_claimants(claimants: list[str]) -> list[str]:
    known = registry.countries()
    return [c for c in claimants if c in known]


def build_eez(overwrite: bool = False) -> gpd.GeoDataFrame | None:
    """Build ``pacific_eez.parquet`` (one row per selected EEZ polygon)."""
    if eez_available() and not overwrite:
        logger.info("%s exists; use --overwrite", EEZ_PATH)
        return None
    reg = registry.load_register("EEZ")
    by_id = {s["source_id"]: s for s in reg["sources"]}
    sel = selection(reg)
    cache: dict[tuple[str, str], gpd.GeoDataFrame] = {}
    for key in dict.fromkeys(zip(sel["source_id"], sel["layer"], strict=True)):
        cache[key] = read_polygons(by_id[key[0]], key[1])
    missing = [
        f"{r.mrgid} ({r.source_id}:{r.layer})"
        for r in sel.itertuples()
        if not (cache[(r.source_id, r.layer)]["mrgid"] == r.mrgid).any()
    ]
    if missing:
        raise ValueError(
            f"MRGIDs in {SELECTION_CSV} not found in their layer: {missing}"
        )
    rows = []
    for _, s in sel.iterrows():
        src = by_id[s["source_id"]]
        lvl = (src.get("levels") or [None])[0]
        raw = cache[(s["source_id"], s["layer"])]
        feats = raw[raw["mrgid"] == s["mrgid"]]
        f0 = feats.iloc[0]
        g, methods = geom.normalize(
            shapely.union_all(feats.geometry.to_numpy())
            if len(feats) > 1
            else feats.geometry.iloc[0]
        )
        claim = _pict_claimants(s["claimants"])
        first = claim[0]
        meta = registry.country_meta(first)
        raw_pol = _first(s, "pol_type") or _first(f0, "pol_type")
        pol = _pol_type(raw_pol)
        licenses.check(src, lvl)
        lic, lic_url = licenses.resolve(src, lvl)
        fixes, notes = _attribute_notes(
            src["source_id"], s["mrgid"], f0, first, pol, raw_pol
        )
        published_area = _published_area(
            _first(s, "area_km2"), _first(f0, "area_km2"), notes=notes
        )
        rows.append(
            {
                "uid": f"{first}:eez:{s['mrgid']}",
                "iso3": first,
                "country_name": meta["name"],
                "sovereign_iso3": meta["sovereign_iso3"],
                "political_status": meta["political_status"],
                "level_rank": 0,
                "level_code": "eez",
                "level_type": "eez",
                "level_name_local": {"200NM": "Exclusive Economic Zone (200 NM)"}.get(
                    pol, pol
                ),
                "nests": pol == "200NM",
                "unit_name": _first(s, "geoname") or _first(f0, "geoname"),
                "unit_name_alt": None,
                "unit_code": s["mrgid"],
                "code_scheme": "mrgid",
                "parent_uid": None,
                "eez_uid": None,
                "source_id": src["source_id"],
                "source_publisher": src.get("publisher"),
                "source_url": src.get("landing_url"),
                "source_version": str(src.get("version"))
                if src.get("version")
                else None,
                "source_date": _as_date(src.get("publication_date")),
                "retrieved_at": _manifest_time(src),
                "license": lic,
                "license_url": lic_url,
                "license_agreement": licenses.agreement(src, lvl),
                "license_restricted": not licenses.redistributable(src),
                "geometry_method": ";".join(methods) or "as_published",
                "mrgid": s["mrgid"],
                "pol_type": pol,
                "claimants": ";".join(s["claimants"]),
                "mrgid_eez": fixes.get("mrgid_eez")
                or _mrgid(_first(f0, "mrgid_eez") or _first(s, "mrgid_eez")),
                "area_km2_published": published_area,
                "boundary_source": _first(f0, "source"),
                "attribute_notes": "; ".join(dict.fromkeys(notes)) or None,
                "land_km2": None,  # filled by `pab combine` from the finest partition (D-024)
                "marine_km2": None,
                "geometry": g,
            }
        )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=geom.STORAGE_CRS)
    gdf["area_km2"] = geom.area_km2(gdf.geometry)
    gdf = _typed(gdf[[*LONG_COLUMNS, *EEZ_EXTRA]])
    for c in (*NULLABLE_STR, "mrgid_eez", "boundary_source", "attribute_notes"):
        gdf[c] = gdf[c].astype(object).where(gdf[c].notna(), None)
    gdf = gdf.sort_values(list(SORT_KEYS), kind="stable").reset_index(drop=True)
    pio.write_geoparquet(gdf, EEZ_PATH)
    used = sorted(set(sel["source_id"]))
    append_step(
        f"{EEZ_DIR}/provenance.json",
        step_record(
            "process-eez",
            inputs={
                "register": "config/sources/EEZ.yml",
                "selection": SELECTION_CSV,
                "raw_manifests": [
                    f"{by_id[u]['raw_path'].rstrip('/')}/manifest.json" for u in used
                ],
                "layers": sorted({f"{a}:{b}" for a, b in cache}),
            },
            outputs={"eez": EEZ_PATH, "rows": len(gdf)},
        ),
    )
    logger.info("wrote %d EEZ polygons to %s", len(gdf), EEZ_PATH)
    return gdf


def _typed(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["level_rank"] = gdf["level_rank"].astype("int16")
    gdf["retrieved_at"] = pd.to_datetime(gdf["retrieved_at"], utc=True)
    for c in ("nests", "license_restricted"):
        gdf[c] = gdf[c].astype(bool)
    return gdf


def load_eez() -> gpd.GeoDataFrame:
    """Read the EEZ product."""
    gdf = pio.read_geoparquet(EEZ_PATH)
    if "license_agreement" not in gdf:  # product written before the column existed
        gdf.insert(gdf.columns.get_loc("license_url") + 1, "license_agreement", None)
    return gdf


def set_land_marine(areas: dict[str, tuple[float, float]]) -> None:
    """Write ``land_km2`` / ``marine_km2`` per EEZ uid into pacific_eez.parquet (D-024).

    ``areas`` maps the product's ``uid`` to (land km2, marine km2), taken from the finest
    partition (marine = zone minus the union of the country's land units).
    """
    gdf = load_eez()
    gdf["land_km2"] = [areas.get(u, (None, None))[0] for u in gdf["uid"]]
    gdf["marine_km2"] = [areas.get(u, (None, None))[1] for u in gdf["uid"]]
    for c in ("land_km2", "marine_km2"):
        gdf[c] = gdf[c].astype("float64")
    pio.write_geoparquet(gdf, EEZ_PATH)


def country_eez_rows(eez: gpd.GeoDataFrame, iso3: str) -> gpd.GeoDataFrame:
    """EEZ rows for one country (shared polygons re-keyed to this country's uid)."""
    mine = eez[eez["claimants"].map(lambda c: iso3 in c.split(";"))].copy()
    meta = registry.country_meta(iso3)
    mine["uid"] = [f"{iso3}:eez:{m}" for m in mine["mrgid"]]
    mine["iso3"] = iso3
    mine["country_name"] = meta["name"]
    mine["sovereign_iso3"] = meta["sovereign_iso3"]
    mine["political_status"] = meta["political_status"]
    return mine


def outline_overlay(g: BaseGeometry, source_id: str | None = None) -> BaseGeometry:
    """EEZ zone domain in EPSG:3832: halves split at 180 are merged; land holes are filled.

    Marine Regions EEZ polygons exclude land as holes; a hole cut by the antimeridian (e.g.
    Taveuni, Fiji) only closes once both halves are merged in a continuous projection. Holes
    are filled only for sources in :data:`HOLES_ARE_LAND` (or when ``source_id`` is None);
    SPC zones are solid and any interior ring is a real gap (the high-seas pocket inside
    French Polynesia), so they are kept as published (D-024).
    """
    merged = shapely.union_all(geom.to_overlay(geom.polygonal_parts(g)))
    if source_id is not None and source_id not in HOLES_ARE_LAND:
        return merged
    shells = [Polygon(p.exterior) for p in geom.polygonal_parts(merged)]
    return shapely.union_all(shells)


def fill_holes(g: BaseGeometry, source_id: str | None = None) -> MultiPolygon:
    """Zone domain in EPSG:4326 (see :func:`outline_overlay`)."""
    return geom.from_overlay(outline_overlay(g, source_id))


def assign_country(
    gdf: gpd.GeoDataFrame, iso3: str, eez: gpd.GeoDataFrame | None = None
) -> gpd.GeoDataFrame:
    """(Re)stamp ``eez_uid`` on land units by majority area and (re)insert the EEZ rows."""
    eez = load_eez() if eez is None else eez
    rows = country_eez_rows(eez, iso3)
    zones = rows[rows["pol_type"] == "200NM"].reset_index(drop=True)
    land = gdf[gdf["level_code"] != "eez"].copy()
    if zones.empty:
        logger.warning("%s: no 200NM EEZ polygon in selection", iso3)
        land["eez_uid"] = None
    else:
        outlines = [
            fill_holes(g, sid)
            for g, sid in zip(zones.geometry, zones["source_id"], strict=True)
        ]
        best, _ = geom.largest_overlap(list(land.geometry), outlines)
        # land outside every outline (e.g. PNG mainland on the Indonesian land border): nearest zone
        miss = np.flatnonzero(best < 0)
        if len(miss):
            zproj = geom.to_overlay(outlines)
            lproj = geom.to_overlay(list(land.geometry.iloc[miss]))
            dist = np.array(
                [[shapely.distance(lg, zg) for zg in zproj] for lg in lproj]
            )
            best[miss] = dist.argmin(axis=1)
            logger.info(
                "%s: %d land unit(s) outside every EEZ outline -> nearest zone",
                iso3,
                len(miss),
            )
        land["eez_uid"] = [zones["uid"].iloc[b] for b in best]
    out = pd.concat([rows[LONG_COLUMNS], land[LONG_COLUMNS]], ignore_index=True)
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=geom.STORAGE_CRS)
    out = _typed(out)
    for c in NULLABLE_STR:
        out[c] = out[c].astype(object).where(out[c].notna(), None)
    return out.sort_values(list(SORT_KEYS), kind="stable").reset_index(drop=True)


def assign_eez(iso3: str) -> int:
    """Re-run EEZ assignment on an existing per-country table in place. Returns land rows without an EEZ."""
    from pab import process

    path = process.admin_path(iso3)
    out = assign_country(process.load_country(iso3), iso3)
    process.save_country(iso3, out)
    missing = int(((out["level_code"] != "eez") & out["eez_uid"].isna()).sum())
    append_step(
        f"{process.country_dir(iso3)}/provenance.json",
        step_record(
            "assign-eez",
            inputs={"admin": path, "eez": EEZ_PATH},
            outputs={"admin": path, "land_rows_without_eez": missing},
        ),
    )
    logger.info("%s: eez_uid assigned (%d land rows without EEZ)", iso3, missing)
    return missing


def eez_coverage(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    """QA: share of land area outside the assigned EEZ (hole-filled), per country table."""
    eez = gdf[gdf["level_code"] == "eez"]
    land = gdf[(gdf["level_code"] == "admin0")]
    if eez.empty or land.empty:
        return {}
    zones = eez[eez["nests"]]
    if zones.empty:
        return {}
    a0 = land.geometry.iloc[0]
    zone_union = geom.union_4326(
        [
            fill_holes(g, sid)
            for g, sid in zip(zones.geometry, zones["source_id"], strict=True)
        ]
    )
    outside = geom.difference_4326(a0, zone_union)
    out_km2 = float(geom.area_km2([outside])[0]) if not outside.is_empty else 0.0
    return {
        "admin0_km2": float(land["area_km2"].iloc[0]),
        "admin0_outside_eez_km2": round(out_km2, 4),
    }
