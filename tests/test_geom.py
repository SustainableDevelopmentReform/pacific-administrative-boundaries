"""Geometry helpers: antimeridian handling, validity, precision, overlay round trips."""

import shapely
from shapely.geometry import MultiPolygon, Polygon, box

from pab import geom


def _lon_ok(g: MultiPolygon) -> bool:
    minx, _, maxx, _ = g.bounds
    return (
        -180 <= minx
        and maxx <= 180
        and all(p.bounds[2] - p.bounds[0] <= 180 for p in g.geoms)
    )


def test_split_wrapped_polygon() -> None:
    # vertices jump from +179 to -179: a 2-degree-wide polygon stored "wrapped"
    wrapped = Polygon([(179, -17), (-179, -17), (-179, -16), (179, -16)])
    out, changed = geom.split_antimeridian(wrapped)
    assert changed
    assert len(out.geoms) == 2
    assert _lon_ok(out)
    # area equals the true 2 x 1 degree box
    assert abs(out.area - 2.0) < 1e-9


def test_split_0_360_polygon() -> None:
    out, changed = geom.split_antimeridian(box(178, -10, 182, -9))
    assert changed and _lon_ok(out)
    assert abs(out.area - 4.0) < 1e-9


def test_untouched_polygon() -> None:
    p = box(170, -10, 171, -9)
    out, changed = geom.split_antimeridian(p)
    assert not changed
    assert out.equals(MultiPolygon([p]))


def test_make_valid_bowtie() -> None:
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
    assert not bowtie.is_valid
    out, methods = geom.normalize(bowtie)
    assert out.is_valid and isinstance(out, MultiPolygon)
    assert "made_valid" in methods
    assert out.area > 0


def test_normalize_precision_and_type() -> None:
    out, _ = geom.normalize(box(0.123456789, 0.1, 0.2, 0.2))
    x = out.geoms[0].exterior.coords[0][0]
    assert round(x, 7) == x
    assert isinstance(out, MultiPolygon)


def test_overlay_roundtrip_across_antimeridian() -> None:
    # two halves of an island split at 180 dissolve to one continuous shape in EPSG:3832
    left, right = box(179.5, -17, 180, -16.5), box(-180, -17, -179.5, -16.5)
    u = geom.union_4326([left, right])
    assert _lon_ok(u) and u.is_valid
    assert (
        abs(geom.area_km2([u])[0] - geom.area_km2([left, right]).sum())
        / geom.area_km2([u])[0]
        < 1e-6
    )


def test_largest_overlap_picks_majority_parent() -> None:
    parents = [box(0, 0, 1, 1), box(1, 0, 2, 1)]
    child = box(0.8, 0.2, 1.6, 0.4)  # 25 % in parent 0, 75 % in parent 1
    idx, share = geom.largest_overlap([child], parents)
    assert idx[0] == 1
    assert 0.7 < share[0] < 0.8


def test_area_km2_one_degree_at_equator() -> None:
    a = geom.area_km2([box(0, 0, 1, 1)])[0]
    assert 12_300 < a < 12_400


def test_from_overlay_is_valid() -> None:
    p = geom.to_overlay([box(179, -1, 180, 0)])[0]
    back = geom.from_overlay(shapely.buffer(p, 1000))
    assert back.is_valid and _lon_ok(back)


def test_eez_outline_closes_hole_cut_by_antimeridian() -> None:
    # an EEZ split at 180 whose land hole (an island on the 180 line) is cut into two notches
    from pab.eez import fill_holes

    island = box(179.9, -16.9, 180.1, -16.7)
    zone = box(178, -18, 182, -15).difference(island)
    split, _ = geom.split_antimeridian(zone)
    assert len(split.geoms) == 2  # the hole is now two notches, no interior ring left
    assert all(len(p.interiors) == 0 for p in split.geoms)
    outline = fill_holes(split)
    land, _ = geom.split_antimeridian(island)
    covered = geom.intersection_4326(outline, land)
    assert abs(geom.area_km2([covered])[0] - geom.area_km2([land])[0]) < 1e-3
