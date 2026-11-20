"""EEZ zone domains (D-024), SPC attribute corrections (D-025) and cross-source clipping (D-023)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from pab import eez, geom, process
from pab import io as pio
from pab.registry import LevelSpec

RING = Polygon(
    [(170, -20), (175, -20), (175, -15), (170, -15)],
    [[(172, -18), (173, -18), (173, -17), (172, -17)]],
)


def test_marine_regions_holes_are_filled() -> None:
    dom = eez.outline_overlay(RING, "marineregions-eez-v12")
    assert len(list(dom.interiors) if dom.geom_type == "Polygon" else []) == 0
    assert dom.area == pytest.approx(geom.to_overlay([box(170, -20, 175, -15)])[0].area)


def test_spc_zones_are_kept_as_published() -> None:
    dom = eez.outline_overlay(RING, "spc-gem-pacific-eez-200nm")
    assert dom.area == pytest.approx(geom.to_overlay([RING])[0].area)
    assert dom.area < geom.to_overlay([box(170, -20, 175, -15)])[0].area


def test_spc_attribute_corrections() -> None:
    f0 = pd.Series({"mrgid_eez": 8319.0, "iso_ter1": "FIJ", "pol_type": "200NM"})
    fixes, notes = eez._attribute_notes(
        "spc-gem-pacific-eez-200nm", "8318", f0, "MHL", "200NM", "200 NM"
    )
    assert fixes == {"mrgid_eez": "8318"}
    assert any("mrgid_eez 8319 corrected to 8318" in n for n in notes)
    assert any("pol_type '200 NM'" in n for n in notes)
    notes = []
    assert eez._published_area("0", notes=notes) is None
    assert notes == ["area_km2 attribute 0 treated as missing"]


def test_clip_to_other_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pio, "ROOT", str(tmp_path))
    coast = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")
    raw = tmp_path / "data/raw/TST/coast"
    raw.mkdir(parents=True)
    coast.to_file(raw / "coast.geojson", driver="GeoJSON")
    sources = {
        "coast": {
            "source_id": "coast",
            "raw_path": "data/raw/TST/coast/",
            "crs": "EPSG:4326",
        },
        "census": {"source_id": "census", "raw_path": "data/raw/TST/census/"},
    }
    level = {
        "level_code": "admin1",
        "nests": True,
        "clip_to": {"source_id": "coast", "layer": "coast.geojson"},
    }
    units = gpd.GeoDataFrame(
        {
            "unit_code": ["a", "b", "sea"],
            "unit_name": ["a", "b", "sea"],
            "methods": [[], [], []],
            "source_id": ["census"] * 3,
        },
        geometry=[
            geom.normalize(box(-0.1, 0, 0.5, 1))[0],  # spills 0.1 deg into the sea
            geom.normalize(box(0.5, 0, 1, 1))[0],
            geom.normalize(box(2, 2, 3, 3))[0],  # all sea: dropped
        ],
        crs="EPSG:4326",
    )
    b = process.Built(spec=LevelSpec(sources["census"], level, 0), units=units)
    process._apply_clip_to([b], sources)
    assert list(b.units["unit_code"]) == ["a", "b"]
    assert all("clipped_to_coastline" in m for m in b.units["methods"])
    assert b.units.geometry.iloc[0].bounds[0] == pytest.approx(0, abs=1e-7)
    assert any("empty after clip" in n for n in b.notes)
