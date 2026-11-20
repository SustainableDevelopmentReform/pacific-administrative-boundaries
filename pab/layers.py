"""Read one register level entry from data/raw into a normalised *unit table*.

A unit table is a GeoDataFrame (EPSG:4326) with columns ``unit_code``, ``unit_name``,
``unit_name_alt``, ``parent_code``, ``code_scheme``, ``methods`` (list of geometry_method
tokens), ``source_id`` and ``geometry`` (MultiPolygon, normalised per :func:`pab.geom.normalize`).
Raw files are untrusted data and are only ever *read* through pyogrio.
"""

from __future__ import annotations

import logging
import warnings
from collections import Counter
from typing import Any

import geopandas as gpd
import pandas as pd

from pab import fields, geom
from pab import io as pio
from pab.registry import LevelSpec

logger = logging.getLogger(__name__)

UNIT_COLUMNS = [
    "unit_code",
    "unit_name",
    "unit_name_alt",
    "parent_code",
    "code_scheme",
    "methods",
    "source_id",
]


def empty_units() -> gpd.GeoDataFrame:
    """An empty unit table."""
    return gpd.GeoDataFrame(
        {c: [] for c in UNIT_COLUMNS}, geometry=[], crs=geom.STORAGE_CRS
    )


def raw_file(source: dict[str, Any], layer: str) -> tuple[str, str | None]:
    """Resolve ``layer`` (``path[::sublayer]``, relative to ``raw_path``) to (gdal path, sublayer)."""
    path, _, sub = layer.partition("::")
    full = f"{source['raw_path'].rstrip('/')}/{path.strip()}"
    if not pio.exists(full):
        raise FileNotFoundError(f"{source['source_id']}: layer file not found: {full}")
    return pio.gdal_path(full), (sub.strip() or None)


def read_layer(
    source: dict[str, Any],
    layer: str,
    include: dict[str, Any] | None = None,
    exclude: dict[str, Any] | None = None,
) -> gpd.GeoDataFrame:
    """Read a raw layer with pyogrio, apply filters and reproject to EPSG:4326."""
    path, sub = raw_file(source, layer)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        gdf = gpd.read_file(path, layer=sub, engine="pyogrio")
    if gdf.crs is None:
        crs = str(source.get("crs") or "")
        if not crs.startswith("EPSG:"):
            raise ValueError(
                f"{source['source_id']}: {layer} has no CRS and register crs is {crs!r}"
            )
        gdf = gdf.set_crs(crs)
    gdf = fields.apply_filter(gdf, include, exclude)
    return gdf.to_crs(geom.STORAGE_CRS)


def default_code_scheme(code_spec: fields.FieldSpec) -> str:
    """Infer ``code_scheme`` from the code field name when the register does not set one."""
    if code_spec is None:
        return "generated"
    col = next(iter(fields.columns_of(code_spec)), "").lower()
    for key, scheme in (
        ("pcode", "pcode"),
        ("geoid", "fips"),
        ("shapeid", "geoboundaries"),
        ("shapeiso", "iso3166-2"),
        ("code_com", "insee"),
        ("gid_", "gadm"),
    ):
        if key in col:
            return scheme
    return "source"


def build_units(
    spec: LevelSpec, gdf: gpd.GeoDataFrame | None = None
) -> tuple[gpd.GeoDataFrame, list[str]]:
    """Build the unit table for a plain (non-derived) level entry.

    Returns (units, notes) where notes are human-readable processing remarks for the report.
    """
    lvl = spec.level
    notes: list[str] = []
    if gdf is None:
        gdf = read_layer(
            spec.source, lvl["layer"], lvl.get("filter"), lvl.get("exclude")
        )
    n_in = len(gdf)
    df = pd.DataFrame(index=gdf.index)
    code = fields.evaluate(gdf, lvl.get("code_field"))
    df["unit_code"] = code if code is not None else None
    name = fields.evaluate(gdf, lvl.get("name_field"))
    df["unit_name"] = name if name is not None else None
    alt = fields.evaluate(gdf, lvl.get("name_alt_field"))
    df["unit_name_alt"] = alt if alt is not None else None
    parent = fields.evaluate(gdf, lvl.get("parent_field")) if lvl.get("nests") else None
    df["parent_code"] = parent if parent is not None else None
    df["code_scheme"] = lvl.get("code_scheme") or default_code_scheme(
        lvl.get("code_field")
    )
    df["source_id"] = spec.source_id

    geoms, methods = [], []
    for g in gdf.geometry:
        mg, m = geom.normalize(g)
        geoms.append(mg)
        methods.append(m)
    df["methods"] = methods
    units = gpd.GeoDataFrame(df, geometry=geoms, crs=geom.STORAGE_CRS)
    empty = units.geometry.is_empty
    if empty.any():
        notes.append(f"dropped {int(empty.sum())} empty/non-polygonal feature(s)")
        logger.warning(
            "%s %s: dropped %d empty geometries",
            spec.source_id,
            spec.key,
            int(empty.sum()),
        )
        units = units[~empty]

    units = _resolve_codes(units, spec, notes)
    if lvl.get("name_map"):
        mapping = {fields.to_str(k): v for k, v in lvl["name_map"].items()}
        hit = units["unit_code"].isin(list(mapping))
        if hit.any():
            old = units.loc[hit, "unit_name"].tolist()
            units.loc[hit, "unit_name"] = units.loc[hit, "unit_code"].map(mapping)
            units.loc[hit, "methods"] = units.loc[hit, "methods"].map(
                lambda m: [*m, "name_corrected"]
            )
            for c, o, n in zip(
                units.loc[hit, "unit_code"],
                old,
                units.loc[hit, "unit_name"],
                strict=True,
            ):
                if o != n:
                    notes.append(f"name corrected for code {c}: {o!r} -> {n!r}")
    nulls = units["unit_name"].isna()
    if nulls.any():
        units.loc[nulls, "unit_name"] = units.loc[nulls, "unit_code"]
        notes.append(
            f"{int(nulls.sum())} unit(s) without a name use their code as name"
        )
    logger.info(
        "%s %s %s: %d features -> %d units",
        spec.source_id,
        spec.level_code,
        spec.key,
        n_in,
        len(units),
    )
    return units.reset_index(drop=True), notes


def _resolve_codes(
    units: gpd.GeoDataFrame, spec: LevelSpec, notes: list[str]
) -> gpd.GeoDataFrame:
    """Dissolve rows sharing a code, suffix genuine clashes, generate missing codes."""
    lvl = spec.level
    if units["unit_code"].isna().all():
        # no code field: dissolve by name when asked, then generate codes in name order
        if lvl.get("dissolve"):
            units = units.assign(unit_code=units["unit_name"])
            units = dissolve_by_code(units, "dissolved_by_name")
            notes.append("dissolved on name (no code field)")
        units = units.sort_values("unit_name", kind="stable").reset_index(drop=True)
        units["unit_code"] = [f"gen-{i + 1}" for i in range(len(units))]
        units["code_scheme"] = "generated"
        return units
    if units["unit_code"].isna().any():
        n = int(units["unit_code"].isna().sum())
        units = units.copy()
        units.loc[units["unit_code"].isna(), "unit_code"] = [
            f"gen-{i + 1}" for i in range(n)
        ]
        notes.append(f"{n} feature(s) without a code got generated codes")
    counts = Counter(units["unit_code"])
    dup = {c for c, n in counts.items() if n > 1}
    if not dup:
        return units
    if lvl.get("dissolve"):
        before = len(units)
        units = dissolve_by_code(units, "dissolved_by_code")
        notes.append(
            f"dissolved {before} features into {len(units)} units on the code field"
        )
        return units
    same_name = [
        c
        for c in dup
        if units.loc[units["unit_code"] == c, "unit_name"].nunique(dropna=False) == 1
    ]
    if same_name:
        mask = units["unit_code"].isin(same_name)
        merged = dissolve_by_code(units[mask], "dissolved_multipart")
        units = pd.concat([units[~mask], merged], ignore_index=True)
        notes.append(
            f"{len(same_name)} code(s) split over several features with one name: merged ({sorted(same_name)[:5]})"
        )
    clash = sorted(dup - set(same_name))
    if clash:
        units = units.copy()
        for c in clash:
            idx = units.index[units["unit_code"] == c]
            for k, i in enumerate(idx, start=1):
                units.at[i, "unit_code"] = f"{c}-{k}"
        notes.append(
            f"{len(clash)} code(s) shared by differently named units: suffixed -1, -2, ... ({clash[:5]})"
        )
        logger.warning(
            "%s %s: duplicate codes with different names %s",
            spec.source_id,
            spec.key,
            clash[:10],
        )
    return gpd.GeoDataFrame(units, geometry="geometry", crs=geom.STORAGE_CRS)


def dissolve_by_code(units: gpd.GeoDataFrame, method: str) -> gpd.GeoDataFrame:
    """Union rows sharing ``unit_code`` (in EPSG:3832); attributes from the most common value."""
    rows = []
    for code, grp in units.groupby("unit_code", sort=True, dropna=False):
        parents = grp["parent_code"].dropna().unique()
        rows.append(
            {
                "unit_code": code,
                "unit_name": _mode(grp["unit_name"]),
                "unit_name_alt": _mode(grp["unit_name_alt"]),
                "parent_code": parents[0] if len(parents) == 1 else None,
                "code_scheme": grp["code_scheme"].iloc[0],
                "methods": sorted(
                    {m for ms in grp["methods"] for m in ms}
                    | ({method} if len(grp) > 1 else set())
                ),
                "source_id": grp["source_id"].iloc[0],
                "geometry": geom.union_4326(grp.geometry)
                if len(grp) > 1
                else grp.geometry.iloc[0],
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=geom.STORAGE_CRS)


def _mode(s: pd.Series) -> object:
    vals = s.dropna()
    return vals.mode().iloc[0] if len(vals) else None
