"""Finest partition on toy data: complete, non-overlapping coverage with fallback."""

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import box

from pab import combine, geom


def _row(
    uid: str, level: str, parent: str | None, g: shapely.Geometry, code: str
) -> dict:
    return {
        "uid": uid,
        "iso3": "FJI",
        "level_code": level,
        "level_type": "district",
        "nests": True,
        "parent_uid": parent,
        "unit_code": code,
        "unit_name": uid,
        "source_id": "toy",
        "license_restricted": False,
        "geometry": geom.normalize(g)[0],
    }


def _toy() -> gpd.GeoDataFrame:
    rows = [
        _row("T:admin0:T", "admin0", None, box(0, 0, 2, 1), "T"),
        _row("T:admin1:a", "admin1", "T:admin0:T", box(0, 0, 1, 1), "a"),
        _row("T:admin1:b", "admin1", "T:admin0:T", box(1, 0, 2, 1), "b"),
        # admin2 covers only part of 'a' and overlaps its sibling and spills into 'b'
        _row("T:admin2:a1", "admin2", "T:admin1:a", box(0, 0, 0.6, 0.5), "a1"),
        _row("T:admin2:a2", "admin2", "T:admin1:a", box(0.5, 0, 1.2, 0.5), "a2"),
    ]
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs="EPSG:4326")


def test_partition_complete_and_disjoint() -> None:
    pieces = combine.land_partition(_toy())
    geoms = [p["geom"] for p in pieces]
    a0 = geom.to_overlay([box(0, 0, 2, 1)])[0]
    total = sum(g.area for g in geoms)
    assert abs(total - a0.area) / a0.area < 1e-9  # exactly covers admin0
    union = shapely.union_all(geoms)
    assert abs(union.area - total) / total < 1e-9  # no overlaps
    finest = sorted(
        max(p["chain"], key=["admin0", "admin1", "admin2"].index)
        + ":"
        + p["chain"][max(p["chain"], key=["admin0", "admin1", "admin2"].index)].uid
        for p in pieces
    )
    # 'a' remainder falls back to admin1, 'b' has no children
    assert finest == [
        "admin1:T:admin1:a",
        "admin1:T:admin1:b",
        "admin2:T:admin2:a1",
        "admin2:T:admin2:a2",
    ]


def test_partition_clips_children_to_parent() -> None:
    pieces = combine.land_partition(_toy())
    a2 = next(
        p
        for p in pieces
        if "admin2" in p["chain"] and p["chain"]["admin2"].uid == "T:admin2:a2"
    )
    parent_a = geom.to_overlay([box(0, 0, 1, 1)])[0]
    assert shapely.difference(a2["geom"], parent_a).area < 1e-6 * parent_a.area


def test_partition_across_antimeridian() -> None:
    rows = [
        _row("T:admin0:T", "admin0", None, box(179, -1, 181, 0), "T"),
        _row("T:admin1:w", "admin1", "T:admin0:T", box(179, -1, 180, 0), "w"),
        _row("T:admin1:e", "admin1", "T:admin0:T", box(-180, -1, -179, 0), "e"),
    ]
    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs="EPSG:4326")
    pieces = combine.land_partition(gdf)
    assert len(pieces) == 2
    back = [geom.from_overlay(p["geom"]) for p in pieces]
    assert all(-180 <= b.bounds[0] and b.bounds[2] <= 180 for b in back)


def test_row_groups_never_span_countries(tmp_path: object) -> None:
    import pyarrow.parquet as pq

    from pab import io as pio

    rows = [
        _row(f"{c}:admin1:{i}", "admin1", None, box(i, 0, i + 1, 1), str(i))
        for c, n in (("AAA", 7), ("BBB", 3))
        for i in range(n)
    ]
    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs="EPSG:4326")
    gdf["iso3"] = [r.split(":")[0] for r in gdf["uid"]]
    path = f"{tmp_path}/t.parquet"
    pio.write_geoparquet(gdf, path, max_rows=5)
    md = pq.ParquetFile(path).metadata
    sizes = [md.row_group(i).num_rows for i in range(md.num_row_groups)]
    assert sizes == [5, 2, 3]
    back = pio.read_geoparquet(path)
    assert len(back) == 10 and back.crs.to_epsg() == 4326
