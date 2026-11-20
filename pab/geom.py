"""Geometry helpers (spec section 9).

* Storage CRS is EPSG:4326 with polygons split at the antimeridian (RFC 7946 style).
* Planar overlay work runs in EPSG:3832 (PDC Mercator, central meridian 150E), where the
  whole Pacific is continuous; results are projected back and re-split at 180 degrees.
* Areas are computed in EPSG:6933 (equal area).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import geopandas as gpd
import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry

STORAGE_CRS = "EPSG:4326"
OVERLAY_CRS = "EPSG:3832"
AREA_CRS = "EPSG:6933"
PRECISION = 1e-7  # 7 decimal places, ~1 cm

_TO_3832 = Transformer.from_crs(STORAGE_CRS, OVERLAY_CRS, always_xy=True)
_FROM_3832 = Transformer.from_crs(OVERLAY_CRS, STORAGE_CRS, always_xy=True)
_EMPTY = MultiPolygon()


def polygonal_parts(geom: BaseGeometry | None) -> list[Polygon]:
    """Return the non-empty Polygon parts of any geometry (collections are flattened)."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if hasattr(geom, "geoms"):
        out: list[Polygon] = []
        for g in geom.geoms:
            out.extend(polygonal_parts(g))
        return out
    return []


def to_multipolygon(geom: BaseGeometry | None) -> MultiPolygon:
    """Promote to MultiPolygon, dropping non-polygonal parts (empty -> empty MultiPolygon)."""
    parts = [p for p in polygonal_parts(geom) if p.area > 0]
    return MultiPolygon(parts) if parts else _EMPTY


def make_valid_polygonal(geom: BaseGeometry | None) -> tuple[MultiPolygon, bool]:
    """``shapely.make_valid`` keeping only polygonal output; returns (geometry, was_changed)."""
    if geom is None or geom.is_empty:
        return _EMPTY, False
    if geom.is_valid:
        return to_multipolygon(geom), False
    fixed = shapely.make_valid(geom, method="structure", keep_collapsed=False)
    return to_multipolygon(fixed), True


def _shift(geom: BaseGeometry, dx: float) -> BaseGeometry:
    return shapely.transform(geom, lambda c: c + np.array([dx, 0.0]))


def _unwrap(poly: Polygon) -> Polygon:
    """Move vertices with negative longitude by +360 so a wrapped polygon becomes continuous."""
    return shapely.transform(
        poly, lambda c: np.where(c[:, :1] < 0, c + np.array([360.0, 0.0]), c)
    )


_WINDOWS = [(-540.0, -180.0, 360.0), (-180.0, 180.0, 0.0), (180.0, 540.0, -360.0)]


def split_antimeridian(geom: BaseGeometry | None) -> tuple[MultiPolygon, bool]:
    """Split polygons at 180 degrees so every part lies within [-180, 180].

    Handles parts expressed beyond +/-180 (0..360 style) and "wrapped" parts whose vertices
    jump from ~+180 to ~-180 (detected by a longitude span > 180 degrees). Returns
    (geometry, was_split).
    """
    out: list[Polygon] = []
    changed = False
    for part in polygonal_parts(geom):
        minx, _, maxx, _ = part.bounds
        if minx >= -180 and maxx <= 180 and (maxx - minx) <= 180:
            out.append(part)
            continue
        changed = True
        cont = _unwrap(part) if (maxx - minx) > 180 else part
        if not cont.is_valid:
            cont = shapely.make_valid(cont)
        for lo, hi, dx in _WINDOWS:
            piece = cont.intersection(box(lo, -90, hi, 90))
            if not piece.is_empty:
                out.extend(polygonal_parts(_shift(piece, dx)))
    return (MultiPolygon(out) if out else _EMPTY), changed


def set_precision(geom: MultiPolygon) -> MultiPolygon:
    """Round coordinates to :data:`PRECISION` keeping the result valid and polygonal."""
    if geom.is_empty:
        return geom
    rounded = shapely.set_precision(geom, PRECISION, mode="valid_output")
    if not rounded.is_valid:
        rounded = shapely.make_valid(rounded)
    return to_multipolygon(rounded)


def normalize(geom: BaseGeometry | None) -> tuple[MultiPolygon, list[str]]:
    """Full storage normalisation of a 4326 geometry.

    make_valid -> antimeridian split -> 7-decimal precision -> MultiPolygon.
    Returns the geometry and the list of ``geometry_method`` tokens that applied.
    """
    methods: list[str] = []
    if geom is None or geom.is_empty:
        return _EMPTY, methods
    # wrapped parts must be unwrapped before make_valid, else make_valid mangles them
    split, was_split = split_antimeridian(geom)
    fixed, was_fixed = make_valid_polygonal(split)
    if was_fixed:
        methods.append("made_valid")
    if was_split:
        methods.append("antimeridian_split")
    return set_precision(fixed), methods


def to_overlay(geoms: Sequence[BaseGeometry] | gpd.GeoSeries) -> np.ndarray:
    """Project 4326 geometries to EPSG:3832 (continuous across the antimeridian).

    Reprojection can make a valid geometry invalid (tiny rings, parts touching the seam);
    such outputs are repaired with ``make_valid`` so GEOS overlays never fail.
    """
    arr = np.asarray(geoms, dtype=object)
    out = shapely.transform(
        arr, lambda c: np.column_stack(_TO_3832.transform(c[:, 0], c[:, 1]))
    )
    bad = ~shapely.is_valid(out) & ~shapely.is_missing(out)
    if bad.any():
        out[bad] = [to_multipolygon(shapely.make_valid(g)) for g in out[bad]]
    return out


def from_overlay(geom: BaseGeometry) -> MultiPolygon:
    """Project an EPSG:3832 geometry back to 4326, split at 180 and normalised."""
    if geom is None or geom.is_empty:
        return _EMPTY
    back = shapely.transform(
        geom, lambda c: np.column_stack(_FROM_3832.transform(c[:, 0], c[:, 1]))
    )
    return normalize(back)[0]


def union_4326(geoms: Iterable[BaseGeometry]) -> MultiPolygon:
    """Union of 4326 geometries computed in EPSG:3832."""
    projected = [g for g in to_overlay(list(geoms)) if g is not None and not g.is_empty]
    if not projected:
        return _EMPTY
    return from_overlay(
        shapely.union_all(shapely.make_valid(np.asarray(projected, dtype=object)))
    )


def area_km2(geoms: gpd.GeoSeries | Sequence[BaseGeometry]) -> np.ndarray:
    """Area in km2 (EPSG:6933) of 4326 geometries."""
    gs = (
        geoms
        if isinstance(geoms, gpd.GeoSeries)
        else gpd.GeoSeries(list(geoms), crs=STORAGE_CRS)
    )
    if gs.crs is None:
        gs = gs.set_crs(STORAGE_CRS)
    return gs.to_crs(AREA_CRS).area.to_numpy() / 1e6


def largest_overlap(
    children: Sequence[BaseGeometry], parents: Sequence[BaseGeometry]
) -> tuple[np.ndarray, np.ndarray]:
    """For each child, index of the parent with the largest intersection area (EPSG:3832).

    Returns (parent_index or -1, share of child area inside that parent).
    """
    c = to_overlay(children)
    p = to_overlay(parents)
    best = np.full(len(c), -1, dtype=int)
    share = np.zeros(len(c))
    if len(c) == 0 or len(p) == 0:
        return best, share
    tree = shapely.STRtree(p)
    ci, pi = tree.query(c, predicate="intersects")
    if len(ci) == 0:
        return best, share
    inter = shapely.area(shapely.intersection(c[ci], p[pi]))
    carea = shapely.area(c)
    best_area = np.zeros(len(c))
    for i, j, a in zip(ci, pi, inter, strict=True):
        if a > best_area[i]:
            best_area[i], best[i] = a, j
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(carea > 0, best_area / carea, 0.0)
    return best, share


def intersection_4326(a: BaseGeometry, b: BaseGeometry) -> MultiPolygon:
    """Intersection of two 4326 geometries computed in EPSG:3832."""
    pa, pb = to_overlay([a, b])
    return from_overlay(shapely.intersection(pa, pb))


def difference_4326(a: BaseGeometry, b: BaseGeometry) -> MultiPolygon:
    """Difference ``a - b`` of two 4326 geometries computed in EPSG:3832."""
    pa, pb = to_overlay([a, b])
    return from_overlay(shapely.difference(pa, pb))


def distance_km(geoms: Sequence[BaseGeometry], lon: float, lat: float) -> np.ndarray:
    """Approximate distance (km, EPSG:3832 metres scaled by cos(lat)) from geometries to a point."""
    pt = to_overlay([shapely.Point(lon, lat)])[0]
    d = shapely.distance(to_overlay(geoms), pt)
    return d * np.cos(np.radians(lat)) / 1000.0
