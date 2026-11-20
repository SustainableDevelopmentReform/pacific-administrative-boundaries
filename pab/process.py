"""raw -> per-country long GeoParquet (spec section 7) + provenance.json + report.

Driven entirely by ``config/sources/<ISO3>.yml`` (see :mod:`pab.registry` for which level
entries are used and :mod:`pab.layers` / :mod:`pab.derive` for how units are built).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pab import derive, geom, layers, licenses, registry
from pab import io as pio
from pab.provenance import append_step, step_record
from pab.registry import ADMIN_CODES, LEVEL_RANK, LevelSpec

logger = logging.getLogger(__name__)

LONG_COLUMNS = [
    "uid", "iso3", "country_name", "sovereign_iso3", "political_status", "level_rank", "level_code",
    "level_type", "level_name_local", "nests", "unit_name", "unit_name_alt", "unit_code", "code_scheme",
    "parent_uid", "eez_uid", "source_id", "source_publisher", "source_url", "source_version", "source_date",
    "retrieved_at", "license", "license_url", "license_agreement", "license_restricted", "geometry_method",
    "area_km2", "geometry",
]  # fmt: skip

#: nullable string columns of the long table (None, never NaN)
NULLABLE_STR = (
    "unit_name_alt",
    "parent_uid",
    "eez_uid",
    "source_version",
    "license_agreement",
)
SORT_KEYS = ("iso3", "level_rank", "unit_code", "uid")  # spec order; uid breaks ties
SPLIT_MIN_SHARE = (
    0.01  # a unit is split across parents when a second parent holds >= 1% ...
)
SPLIT_MIN_KM2 = 0.01  # ... and >= 0.01 km2 of it


def country_dir(iso3: str) -> str:
    """Processed output folder for a country."""
    return f"data/processed/{iso3}"


def admin_path(iso3: str) -> str:
    """Per-country long table path."""
    return f"{country_dir(iso3)}/{iso3.lower()}_admin.parquet"


@dataclass
class Built:
    """A built level: its spec, unit table and processing notes."""

    spec: LevelSpec
    units: gpd.GeoDataFrame
    notes: list[str] = field(default_factory=list)
    nests: bool = True
    parent_candidate: bool = True
    parent_stats: dict[str, Any] = field(default_factory=dict)

    @property
    def level_code(self) -> str:
        """Level code of the spec."""
        return self.spec.level_code


def build_levels(iso3: str, reg: dict[str, Any]) -> list[Built]:
    """Build every used level of a register (plain, island-derived, then child-dissolved)."""
    sources = {s["source_id"]: s for s in reg["sources"]}
    specs = registry.used_levels(reg)
    built: list[Built] = []
    deferred: list[LevelSpec] = []
    for spec in specs:
        method = (spec.level.get("derive") or {}).get("method")
        if method == "dissolve_children":
            deferred.append(spec)
            continue
        if method == "islands_from_parts":
            units, notes = derive.islands_from_parts(spec, sources)
        elif method is None:
            units, notes = layers.build_units(spec)
        else:
            raise ValueError(f"{spec.source_id}: unknown derive method {method!r}")
        built.append(_new_built(spec, units, notes))
    for spec in deferred:
        cfg = spec.level["derive"]
        kids = [
            b
            for b in built
            if b.level_code == cfg["child_level"] and b.parent_candidate
        ]
        if cfg.get("child_source"):
            kids = [b for b in kids if b.spec.source_id == cfg["child_source"]]
        if len(kids) != 1:
            raise ValueError(
                f"{spec.source_id}: dissolve_children needs exactly one {cfg['child_level']} child level, found {len(kids)}"
            )
        units, membership, notes = derive.dissolve_children(spec, kids[0].units)
        child = kids[0]
        child.units["parent_code"] = child.units["unit_code"].map(membership)
        child.notes.append(f"parent codes set from derived {spec.level_code} groups")
        built.append(_new_built(spec, units, notes))
    _apply_land_masks(built, sources)
    _apply_clip_to(built, sources)
    return built


def _new_built(spec: LevelSpec, units: gpd.GeoDataFrame, notes: list[str]) -> Built:
    return Built(
        spec=spec,
        units=units,
        notes=[*spec.notes, *notes],
        nests=bool(spec.level.get("nests")),
        parent_candidate=bool(spec.level.get("parent_candidate", True))
        and bool(spec.level.get("nests")),
    )


def _apply_land_masks(built: list[Built], sources: dict[str, dict[str, Any]]) -> None:
    """Clip every unit of a source that declares ``land_mask`` to that mask (EPSG:3832)."""
    masks: dict[str, Any] = {}
    for b in built:
        src = sources.get(b.spec.source_id) or {}
        cfg = src.get("land_mask")
        if not cfg:
            continue
        if src["source_id"] not in masks:
            mgdf = layers.read_layer(
                src, cfg["layer"], cfg.get("filter"), cfg.get("exclude")
            )
            parts = [geom.normalize(g)[0] for g in mgdf.geometry]
            masks[src["source_id"]] = geom.to_overlay([geom.union_4326(parts)])[0]
            logger.info(
                "%s: land mask from %s (%d features)",
                src["source_id"],
                cfg["layer"],
                len(mgdf),
            )
        mask = masks[src["source_id"]]
        before = geom.area_km2(b.units.geometry).sum()
        projected = geom.to_overlay(list(b.units.geometry))
        clipped = shapely.intersection(projected, mask)
        b.units = b.units.assign(geometry=[geom.from_overlay(g) for g in clipped])
        b.units["methods"] = b.units["methods"].map(lambda m: [*m, "clipped_to_land"])
        empty = b.units.geometry.is_empty
        after = geom.area_km2(b.units.geometry).sum()
        b.notes.append(
            f"clipped to land mask ({cfg['layer']}): {before:.1f} -> {after:.1f} km2"
        )
        if empty.any():
            b.notes.append(
                f"{int(empty.sum())} water-only unit(s) dropped after land clip"
            )
            b.units = b.units[~empty].reset_index(drop=True)


def _apply_clip_to(built: list[Built], sources: dict[str, dict[str, Any]]) -> None:
    """Clip levels that declare ``clip_to: {source_id, layer}`` to another source's land.

    Cross-source clipping (D-023): e.g. census villages clipped to an official coastline.
    Units are intersected with the union of the clip layer in EPSG:3832 and flagged
    ``clipped_to_coastline``; units left empty are dropped.
    """
    masks: dict[tuple[str, str], Any] = {}
    for b in built:
        cfg = b.spec.level.get("clip_to")
        if not cfg:
            continue
        if cfg["source_id"] not in sources:
            raise ValueError(
                f"{b.spec.source_id}: clip_to source {cfg['source_id']!r} not in register"
            )
        key = (cfg["source_id"], cfg["layer"])
        if key not in masks:
            mgdf = layers.read_layer(
                sources[cfg["source_id"]],
                cfg["layer"],
                cfg.get("filter"),
                cfg.get("exclude"),
            )
            parts = [geom.normalize(g)[0] for g in mgdf.geometry]
            masks[key] = geom.to_overlay([geom.union_4326(parts)])[0]
        mask = masks[key]
        before = geom.area_km2(b.units.geometry)
        projected = geom.to_overlay(list(b.units.geometry))
        clipped = [shapely.make_valid(shapely.intersection(g, mask)) for g in projected]
        b.units = b.units.assign(
            geometry=[
                geom.normalize(geom.from_overlay(g))[0]
                if not g.is_empty
                else shapely.MultiPolygon()
                for g in clipped
            ]
        )
        b.units["methods"] = b.units["methods"].map(
            lambda m: [*m, "clipped_to_coastline"]
        )
        after = geom.area_km2(b.units.geometry)
        b.notes.append(
            f"clipped to {cfg['source_id']} {cfg['layer']}: {before.sum():.2f} -> "
            f"{after.sum():.2f} km2 (largest unit change "
            f"{float(np.max(np.abs(before - after))):.3f} km2)"
        )
        empty = b.units.geometry.is_empty
        if empty.any():
            b.notes.append(f"{int(empty.sum())} unit(s) empty after clip, dropped")
            b.units = b.units[~empty].reset_index(drop=True)


def make_admin0(iso3: str, built: list[Built]) -> Built:
    """Return the admin0 level, dissolving admin1 when no admin0 source is used."""
    meta = registry.country_meta(iso3)
    own = [b for b in built if b.level_code == "admin0"]
    if len(own) > 1:
        raise ValueError(f"{iso3}: more than one admin0 level entry used")
    if own:
        b = own[0]
        g = (
            geom.union_4326(b.units.geometry)
            if len(b.units) > 1
            else b.units.geometry.iloc[0]
        )
        methods = sorted(
            {m for ms in b.units["methods"] for m in ms}
            | ({"dissolved_from_parts"} if len(b.units) > 1 else set())
        )
        src = b.units["source_id"].iloc[0]
        spec = b.spec
        built.remove(b)
        notes = b.notes
    else:
        kids = [b for b in built if b.level_code == "admin1" and b.parent_candidate]
        if not kids:
            raise ValueError(f"{iso3}: no admin0 and no admin1 level to dissolve")
        k = kids[0]
        g = geom.union_4326(k.units.geometry)
        methods = ["dissolved_from_children"]
        src = k.units["source_id"].mode().iloc[0]
        lvl = {
            "level_code": "admin0",
            "level_type": "country",
            "level_name_local": meta.get("official_name") or meta["name"],
            "nests": True,
            **(
                {"license": k.spec.level["license"]}
                if k.spec.level.get("license")
                else {}
            ),
        }
        spec = LevelSpec(k.spec.source, lvl, -1)
        notes = [f"admin0 dissolved from admin1 ({k.spec.source_id})"]
    units = gpd.GeoDataFrame(
        [
            {
                "unit_code": iso3,
                "unit_name": meta["name"],
                "unit_name_alt": meta.get("official_name"),
                "parent_code": None,
                "code_scheme": "iso3166-1-alpha-3",
                "methods": methods,
                "source_id": src,
                "geometry": g,
            }
        ],
        geometry="geometry",
        crs=geom.STORAGE_CRS,
    )
    return Built(spec=spec, units=units, notes=notes)


def uid_for(iso3: str, b: Built, code: str) -> str:
    """Build a uid (``other`` layers carry their layer key so several can coexist)."""
    if b.level_code == "other":
        return f"{iso3}:other-{b.spec.key}:{code}"
    return f"{iso3}:{b.level_code}:{code}"


def assign_parents(iso3: str, built: list[Built]) -> None:
    """Fill ``parent_uid`` for nesting levels (by code where possible, else largest overlap)."""
    for b in built:
        b.units["uid"] = [uid_for(iso3, b, c) for c in b.units["unit_code"]]
        b.units["parent_uid"] = None
    by_level: dict[str, list[Built]] = {}
    for b in built:
        by_level.setdefault(b.level_code, []).append(b)
    for k, code in enumerate(ADMIN_CODES[1:], start=1):
        for b in by_level.get(code, []):
            if not b.nests:
                continue
            prev = next(
                (
                    ADMIN_CODES[j]
                    for j in range(k - 1, -1, -1)
                    if by_level.get(ADMIN_CODES[j])
                ),
                None,
            )
            if prev is None:
                continue
            cands = [p for p in by_level[prev] if p.parent_candidate]
            if not b.parent_candidate:
                same = [
                    p for p in by_level[prev] if p.spec.source_id == b.spec.source_id
                ]
                cands = same or cands
            parents = pd.concat([p.units for p in cands], ignore_index=True)
            _link(
                b,
                gpd.GeoDataFrame(parents, geometry="geometry", crs=geom.STORAGE_CRS),
                prev,
            )


def _link(b: Built, parents: gpd.GeoDataFrame, prev: str) -> None:
    units = b.units
    best, _ = geom.largest_overlap(list(units.geometry), list(parents.geometry))
    spatial_uid = np.array(
        [parents["uid"].iloc[i] if i >= 0 else None for i in best], dtype=object
    )
    code_to_uid = dict(zip(parents["unit_code"], parents["uid"], strict=True))
    if prev == "admin0" and len(parents) == 1:
        # the only possible parent: source country codes (STATEFP, ADM0_PCODE...) are irrelevant
        units["parent_code"] = parents["unit_code"].iloc[0]
    # parent codes may be None or NaN (pandas) when absent
    pcodes = [c if isinstance(c, str) else None for c in units["parent_code"]]
    final, method = [], []
    unmatched = 0
    for i, pc in enumerate(pcodes):
        cu = code_to_uid.get(pc) if pc is not None else None
        if cu is not None:
            final.append(cu)
            method.append("parent_by_code")
        else:
            if pc is not None:
                unmatched += 1
            final.append(spatial_uid[i])
            method.append("parent_by_overlap")
    units["parent_uid"] = final
    units["methods"] = [
        [*m, pm] for m, pm in zip(units["methods"], method, strict=True)
    ]
    disagree = int(
        sum(
            1
            for f, s, pm in zip(final, spatial_uid, method, strict=True)
            if pm == "parent_by_code" and s is not None and f != s
        )
    )
    orphan = int(sum(1 for f in final if f is None))
    # share of each child inside its *final* parent
    puid_geom = dict(zip(parents["uid"], parents.geometry, strict=True))
    inside = []
    for g, pu in zip(units.geometry, final, strict=True):
        if pu is None:
            inside.append(0.0)
            continue
        a, p = geom.to_overlay([g, puid_geom[pu]])
        inside.append(
            float(shapely.area(shapely.intersection(a, p)) / shapely.area(a))
            if shapely.area(a) > 0
            else 0.0
        )
    inside_arr = np.array(inside)
    weights = geom.area_km2(units.geometry)
    wshare = (
        float((inside_arr * weights).sum() / weights.sum())
        if weights.sum() > 0
        else 0.0
    )
    b.parent_stats = {
        "parent_level": prev,
        "by_code": method.count("parent_by_code"),
        "by_overlap": method.count("parent_by_overlap"),
        "code_unmatched": unmatched,
        "code_vs_overlap_disagree": disagree,
        "orphans": orphan,
        "area_weighted_share_inside_parent": round(wshare, 5),
        "units_below_90pct_inside": int((inside_arr < 0.9).sum()),
    }
    if unmatched:
        b.notes.append(
            f"{unmatched} parent code(s) did not match a {prev} unit; parent assigned by largest overlap"
        )
    if disagree:
        b.notes.append(
            f"{disagree} unit(s) whose coded parent differs from the largest-overlap parent (code kept)"
        )
    if b.spec.level.get("split_by_parent"):
        _split_by_parent(b, parents)
    check = b.spec.level.get("nest_check")
    if check and wshare < float(check.get("min_share", 0.95)):
        b.nests = False
        b.notes.append(
            f"nest check failed: only {wshare:.1%} of area inside assigned {prev} parents (< {float(check.get('min_share', 0.95)):.0%}); nests set to false, parent kept by largest overlap"
        )
    elif check:
        b.notes.append(
            f"nest check passed: {wshare:.1%} of area inside assigned {prev} parents"
        )


def _split_by_parent(b: Built, parents: gpd.GeoDataFrame) -> None:
    """Split units that straddle several parents into one piece per parent."""
    rows = []
    pgeo = geom.to_overlay(list(parents.geometry))
    tree = shapely.STRtree(pgeo)
    for _, u in b.units.iterrows():
        ug = geom.to_overlay([u.geometry])[0]
        idx = tree.query(ug, predicate="intersects")
        pieces = [(j, shapely.intersection(ug, pgeo[j])) for j in idx]
        total = shapely.area(ug)
        big = [
            (j, g)
            for j, g in pieces
            if shapely.area(g) >= SPLIT_MIN_SHARE * total
            and geom.area_km2([geom.from_overlay(g)])[0] >= SPLIT_MIN_KM2
        ]
        if len(big) < 2:
            rows.append(u.to_dict())
            continue
        for j, g in big:
            p = parents.iloc[j]
            r = u.to_dict()
            r["unit_code"] = f"{u['unit_code']}-{p['unit_code']}"
            r["unit_name"] = f"{u['unit_name']} ({p['unit_name']})"
            r["parent_uid"] = p["uid"]
            r["uid"] = u["uid"].rsplit(":", 1)[0] + ":" + r["unit_code"]
            r["methods"] = [
                m for m in u["methods"] if not m.startswith("parent_by")
            ] + ["split_by_parent", "parent_by_overlap"]
            r["geometry"] = geom.from_overlay(g)
            rows.append(r)
        b.notes.append(
            f"{u['unit_name']} ({u['unit_code']}) straddles {len(big)} parents: split into {[r['unit_code'] for r in rows[-len(big) :]]}"
        )
    b.units = gpd.GeoDataFrame(rows, geometry="geometry", crs=geom.STORAGE_CRS)


def _manifest_time(source: dict[str, Any]) -> pd.Timestamp | None:
    raw = source.get("raw_path")
    if not raw:
        return None
    path = f"{raw.rstrip('/')}/manifest.json"
    if not pio.exists(path):
        return None
    ts = pio.read_json(path).get("retrieved_at")
    return (
        pd.Timestamp(ts).tz_convert("UTC")
        if ts and pd.Timestamp(ts).tzinfo
        else (pd.Timestamp(ts, tz="UTC") if ts else None)
    )


def _as_date(v: object) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def assemble(iso3: str, reg: dict[str, Any], built: list[Built]) -> gpd.GeoDataFrame:
    """Stack all built levels into the long-table schema (spec section 7)."""
    meta = registry.country_meta(iso3)
    sources = {s["source_id"]: s for s in reg["sources"]}
    frames = []
    for b in built:
        u = b.units.copy()
        lvl = b.spec.level
        u["iso3"] = iso3
        u["country_name"] = meta["name"]
        u["sovereign_iso3"] = meta["sovereign_iso3"]
        u["political_status"] = meta["political_status"]
        u["level_rank"] = LEVEL_RANK[b.level_code]
        u["level_code"] = b.level_code
        u["level_type"] = lvl["level_type"]
        u["level_name_local"] = lvl.get("level_name_local")
        u["nests"] = b.nests
        if not b.nests and not lvl.get("nest_check"):
            u["parent_uid"] = None
        u["eez_uid"] = None
        own = (
            *licenses.resolve(b.spec.source, lvl),
            licenses.agreement(b.spec.source, lvl),
        )
        u["_lic"] = [
            own
            if sid == b.spec.source_id
            else (*licenses.resolve(sources[sid]), licenses.agreement(sources[sid]))
            for sid in u["source_id"]
        ]
        frames.append(u)
    df = pd.concat(frames, ignore_index=True)
    src = df["source_id"].map(sources.get)
    df["source_publisher"] = src.map(lambda s: s.get("publisher"))
    df["source_url"] = src.map(lambda s: s.get("landing_url"))
    df["source_version"] = src.map(
        lambda s: None if s.get("version") in (None, "") else str(s.get("version"))
    )
    df["source_date"] = src.map(lambda s: _as_date(s.get("publication_date")))
    df["retrieved_at"] = pd.to_datetime(src.map(_manifest_time), utc=True)
    df["license"] = df["_lic"].map(lambda t: t[0])
    df["license_url"] = df["_lic"].map(lambda t: t[1])
    df["license_agreement"] = df["_lic"].map(lambda t: t[2])
    df["license_restricted"] = src.map(lambda s: not licenses.redistributable(s))
    df["geometry_method"] = df["methods"].map(
        lambda m: ";".join(dict.fromkeys(m)) if m else "as_published"
    )
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=geom.STORAGE_CRS)
    gdf["area_km2"] = geom.area_km2(gdf.geometry)
    gdf = gdf[LONG_COLUMNS]
    gdf["level_rank"] = gdf["level_rank"].astype("int16")
    gdf["nests"] = gdf["nests"].astype(bool)
    gdf["license_restricted"] = gdf["license_restricted"].astype(bool)
    for c in NULLABLE_STR:
        gdf[c] = gdf[c].astype(object).where(gdf[c].notna(), None)
    dup = gdf["uid"][gdf["uid"].duplicated()]
    if len(dup):
        raise ValueError(f"{iso3}: duplicate uids {dup.tolist()[:10]}")
    return gdf.sort_values(list(SORT_KEYS), kind="stable").reset_index(drop=True)


def restricted_path(iso3: str) -> str:
    """Local-only companion file holding licence-restricted rows (no STAC item, never published)."""
    return f"{country_dir(iso3)}/{iso3.lower()}_admin_restricted.parquet"


def save_country(iso3: str, gdf: gpd.GeoDataFrame) -> tuple[int, int]:
    """Write open rows to ``<iso3>_admin.parquet`` and restricted rows to the companion file.

    Returns (open rows, restricted rows). A stale companion file is removed when no row is
    restricted.
    """
    restricted = gdf[gdf["license_restricted"]]
    open_rows = gdf[~gdf["license_restricted"]]
    pio.write_geoparquet(open_rows.reset_index(drop=True), admin_path(iso3))
    rpath = restricted_path(iso3)
    if len(restricted):
        pio.write_geoparquet(restricted.reset_index(drop=True), rpath)
    elif pio.exists(rpath) and not pio.is_remote(rpath):
        import os

        os.remove(pio.resolve(rpath))
    return len(open_rows), len(restricted)


def load_country(iso3: str, include_restricted: bool = True) -> gpd.GeoDataFrame:
    """Read a country's long table (optionally with its restricted companion rows)."""
    gdf = pio.read_geoparquet(admin_path(iso3))
    rpath = restricted_path(iso3)
    if include_restricted and pio.exists(rpath):
        both = pd.concat([gdf, pio.read_geoparquet(rpath)], ignore_index=True)
        gdf = gpd.GeoDataFrame(both, geometry="geometry", crs=geom.STORAGE_CRS)
        gdf = gdf.sort_values(list(SORT_KEYS), kind="stable").reset_index(drop=True)
    if "license_agreement" not in gdf:  # tables written before the column existed
        gdf.insert(gdf.columns.get_loc("license_url") + 1, "license_agreement", None)
    return gdf


def process_country(iso3: str, overwrite: bool = False) -> gpd.GeoDataFrame | None:
    """Process one country end to end. Returns the full long table (None when skipped)."""
    out = admin_path(iso3)
    if pio.exists(out) and not overwrite:
        logger.info("%s exists; use --overwrite to rebuild", out)
        return None
    reg = registry.load_register(iso3)
    used = registry.sources_used(reg)
    sources = {s["source_id"]: s for s in reg["sources"]}
    manifests = [f"{sources[u]['raw_path'].rstrip('/')}/manifest.json" for u in used]
    missing = [m for m in manifests if not pio.exists(m)]
    if missing:
        raise FileNotFoundError(
            f"{iso3}: raw sources not cached (run `pab cache {iso3}`): {missing}"
        )
    built = build_levels(iso3, reg)
    admin0 = make_admin0(iso3, built)
    built.insert(0, admin0)
    assign_parents(iso3, built)
    gdf = assemble(iso3, reg, built)
    stray = set(gdf["source_id"]) - set(used)
    if stray:
        raise ValueError(
            f"{iso3}: rows from sources outside sources_used: {sorted(stray)}"
        )
    from pab import eez

    if eez.eez_available():
        gdf = eez.assign_country(gdf, iso3)
    n_open, n_restricted = save_country(iso3, gdf)
    logger.info(
        "%s: wrote %d rows to %s (+%d restricted rows to %s)",
        iso3,
        n_open,
        out,
        n_restricted,
        restricted_path(iso3),
    )

    from pab import qa, report, stac

    qa_result = qa.country_qa(gdf)
    report.write_processing_report(iso3, reg, built, gdf, qa_result)
    append_step(
        f"{country_dir(iso3)}/provenance.json",
        step_record(
            "process",
            inputs={
                "register": f"config/sources/{iso3}.yml",
                "sources_used": used,
                "raw_manifests": manifests,
            },
            outputs={
                "admin": out,
                "rows": n_open,
                "restricted_file": restricted_path(iso3) if n_restricted else None,
                "restricted_rows": n_restricted,
                "levels": gdf.groupby("level_code").size().to_dict(),
            },
        ),
    )
    stac.write_country_item(iso3, gdf[~gdf["license_restricted"]])
    return gdf
