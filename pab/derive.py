"""Derived levels: units that no source publishes directly.

Methods are referenced from a register level entry by ``derive: {method: <name>, ...}``.

``islands_from_parts``
    Split land polygons into islands/atolls by assigning every polygon part to the nearest
    named island point (within ``max_km``). ``sources`` are tried in priority order; an island
    with no parts in the first source is filled from the next (e.g. geoBoundaries land, then
    census districts). ``collapse`` dissolves everything into a single unit (admin0 use).
    Rulings E-005/E-006 (COK, TKL).

``dissolve_children``
    Build a coarser level by dissolving already-built child units, either by an explicit
    ``groups`` membership list or by majority-area overlap with a ``group_layer``.
"""

from __future__ import annotations

import logging
from typing import Any

import geopandas as gpd
import numpy as np

from pab import fields, geom, layers
from pab.registry import LevelSpec, slug

logger = logging.getLogger(__name__)


def islands_from_parts(
    spec: LevelSpec, sources: dict[str, dict[str, Any]]
) -> tuple[gpd.GeoDataFrame, list[str]]:
    """See module docstring. ``sources`` maps source_id -> register source entry."""
    cfg = spec.level["derive"]
    islands = cfg["islands"]
    max_km = float(cfg.get("max_km", 30))
    notes: list[str] = []
    filled: dict[str, dict[str, Any]] = {}
    for rank, src_cfg in enumerate(cfg["sources"]):
        src = sources[src_cfg["source_id"]]
        gdf = layers.read_layer(
            src, src_cfg["layer"], src_cfg.get("filter"), src_cfg.get("exclude")
        )
        parts = []
        for g in gdf.geometry:
            mg, _ = geom.normalize(g)
            parts.extend(geom.polygonal_parts(mg))
        if not parts:
            continue
        dist = np.column_stack(
            [geom.distance_km(parts, isl["lon"], isl["lat"]) for isl in islands]
        )
        nearest = dist.argmin(axis=1)
        near_d = dist[np.arange(len(parts)), nearest]
        too_far = near_d > max_km
        if rank == 0 and too_far.any():
            lost = float(
                geom.area_km2(
                    gpd.GeoSeries(
                        np.asarray(parts, dtype=object)[too_far], crs=geom.STORAGE_CRS
                    )
                ).sum()
            )
            notes.append(
                f"{int(too_far.sum())} part(s) of {src['source_id']} ({lost:.3f} km2) lie > {max_km:g} km from every island point and were not assigned"
            )
        token = src_cfg.get(
            "method_token",
            "split_from_admin0_by_island"
            if rank == 0
            else "supplemented_from_alternative_source",
        )
        for k, isl in enumerate(islands):
            if isl["code"] in filled:
                continue
            mine = [parts[i] for i in np.flatnonzero((nearest == k) & ~too_far)]
            if not mine:
                continue
            filled[isl["code"]] = {
                "unit_code": isl["code"],
                "unit_name": isl["name"],
                "unit_name_alt": isl.get("name_alt"),
                "parent_code": isl.get("group"),
                "code_scheme": spec.level.get("code_scheme", "name-slug"),
                "methods": [token],
                "source_id": src["source_id"],
                "geometry": geom.union_4326(mine),
                "_max_km": float(near_d[(nearest == k) & ~too_far].max()),
                "_n_parts": len(mine),
            }
            if rank > 0:
                notes.append(
                    f"{isl['name']}: not in {cfg['sources'][0]['source_id']}; taken from {src['source_id']} ({len(mine)} part(s))"
                )
    missing = [isl["name"] for isl in islands if isl["code"] not in filled]
    if missing:
        notes.append(f"no open polygon found for: {', '.join(missing)}")
    rows = [filled[i["code"]] for i in islands if i["code"] in filled]
    for r in rows:
        notes.append(
            f"{r['unit_name']}: {r.pop('_n_parts')} part(s), farthest {r.pop('_max_km'):.1f} km from island point"
        )
    units = gpd.GeoDataFrame(rows, geometry="geometry", crs=geom.STORAGE_CRS)
    if cfg.get("collapse"):
        col = cfg["collapse"]
        methods = sorted({m for ms in units["methods"] for m in ms})
        units = gpd.GeoDataFrame(
            [
                {
                    "unit_code": col["code"],
                    "unit_name": col["name"],
                    "unit_name_alt": None,
                    "parent_code": None,
                    "code_scheme": col.get("code_scheme", "iso3166-1-alpha-3"),
                    "methods": methods,
                    "source_id": spec.source_id,
                    "geometry": geom.union_4326(units.geometry),
                }
            ],
            geometry="geometry",
            crs=geom.STORAGE_CRS,
        )
    return units, notes


def dissolve_children(
    spec: LevelSpec, children: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, dict[str, str], list[str]]:
    """Dissolve child units into groups.

    Returns (group units, {child unit_code: group unit_code}, notes).
    """
    cfg = spec.level["derive"]
    notes: list[str] = []
    membership: dict[str, str] = {}
    names: dict[str, str] = {}
    if "groups" in cfg:
        for gcode, g in cfg["groups"].items():
            names[str(gcode)] = g["name"]
            for m in g["members"]:
                membership[str(m)] = str(gcode)
    else:
        src = spec.source
        glayer = layers.read_layer(
            src, cfg["group_layer"], cfg.get("filter"), cfg.get("exclude")
        )
        gnames = fields.evaluate(glayer, cfg["group_name_field"])
        gcodes = (
            fields.evaluate(glayer, cfg.get("group_code_field"))
            if cfg.get("group_code_field")
            else gnames.map(slug)
        )
        gg = [geom.normalize(g)[0] for g in glayer.geometry]
        best, share = geom.largest_overlap(list(children.geometry), gg)
        for code, b, s in zip(children["unit_code"], best, share, strict=True):
            if b < 0:
                notes.append(
                    f"child {code} overlaps no group polygon; left without group"
                )
                continue
            membership[code] = gcodes.iloc[b]
            names[gcodes.iloc[b]] = gnames.iloc[b]
            if s < 0.9:
                notes.append(
                    f"child {code} only {s:.0%} inside its group polygon {gnames.iloc[b]}"
                )
        notes.append(
            f"children assigned to {cfg['group_layer']} polygons by largest overlap; group geometry = union of children"
        )
    unknown = sorted(set(children["unit_code"]) - set(membership))
    if unknown:
        notes.append(f"children not in any group: {unknown}")
    rows = []
    for gcode in sorted(set(membership.values())):
        kids = children[children["unit_code"].map(membership.get) == gcode]
        if kids.empty:
            notes.append(f"group {gcode} has no built children; skipped")
            continue
        rows.append(
            {
                "unit_code": gcode,
                "unit_name": names[gcode],
                "unit_name_alt": None,
                "parent_code": None,
                "code_scheme": spec.level.get("code_scheme", "name-slug"),
                "methods": ["dissolved_from_children"],
                "source_id": spec.source_id
                if not cfg.get("source_from_children")
                else kids["source_id"].mode().iloc[0],
                "geometry": geom.union_4326(kids.geometry),
            }
        )
    return (
        gpd.GeoDataFrame(rows, geometry="geometry", crs=geom.STORAGE_CRS),
        membership,
        notes,
    )
