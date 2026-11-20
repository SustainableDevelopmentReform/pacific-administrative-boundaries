"""STAC layout (D-022), provenance fields (D-021), publish dry run, licence agreements (D-019/20)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pystac
import pytest
from shapely.geometry import box

from pab import geom, licenses, stac
from pab import io as pio
from pab import publish as pub

HTTPS = "https://bucket.s3.amazonaws.com/prefix"
REPO = "https://github.com/example-org/example-repo"

SOURCES: dict[str, dict[str, Any]] = {
    "tst-open": {
        "source_id": "tst-open",
        "title": "Test open boundaries",
        "publisher": "Test Statistics Office",
        "landing_url": "https://example.org/open",
        "publication_date": "2020-01-01",
        "license": {"name": "CC-BY-4.0", "redistribution_ok": True},
        "raw_path": "data/raw/TST/tst-open/",
        "levels": [],
    },
    "tst-spc": {
        "source_id": "tst-spc",
        "title": "Test SPC boundaries",
        "publisher": "Pacific Community (SPC)",
        "landing_url": "https://example.org/spc",
        "publication_date": "2022-01-01",
        "license": {
            "name": "CC-BY-NC-SA-4.0",
            "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "redistribution_ok": True,
            "agreement": "CSDR-SPC data use agreement",
        },
        "raw_path": "data/raw/TST/tst-spc/",
        "levels": [],
    },
}


def _write(root: Path, rel: str, text: str = "{}") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A toy project tree with one country table, its sources and the publish config."""
    monkeypatch.setattr(pio, "ROOT", str(tmp_path))
    monkeypatch.setattr(stac, "_all_sources", lambda: SOURCES)
    pub.config.cache_clear()
    stac._doc_anchors.cache_clear()
    _write(
        tmp_path,
        "config/publish.yml",
        f"repo_url: {REPO}\ns3_bucket: bucket\ns3_prefix: prefix\nhttps_base: {HTTPS}\n"
        "version: v9.9.9\n",
    )
    _write(
        tmp_path, "docs/sources.md", "# Sources\n\n## Summary\n\n### TST: Testland\n"
    )
    for sid in SOURCES:
        _write(tmp_path, f"data/raw/TST/{sid}/manifest.json")
        _write(tmp_path, f"data/raw/TST/{sid}/original.shp", "x")
    _write(tmp_path, "data/processed/TST/provenance.json")
    _write(tmp_path, "data/processed/TST/.DS_Store", "x")
    _write(tmp_path, "data/combined/partition_checks.json")
    gdf = _table()
    pio.write_geoparquet(gdf, "data/processed/TST/tst_admin.parquet")
    pio.write_geoparquet(
        gdf.iloc[:1], "data/processed/TST/tst_admin_restricted.parquet"
    )
    yield tmp_path
    pub.config.cache_clear()
    stac._doc_anchors.cache_clear()


def _table() -> gpd.GeoDataFrame:
    rows = [
        {
            "uid": "TST:eez:1",
            "iso3": "TST",
            "level_code": "eez",
            "source_id": "tst-spc",
            "source_date": "2022-01-01",
            "license": "CC-BY-NC-SA-4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "license_agreement": "CSDR-SPC data use agreement",
            "geometry": geom.normalize(box(170, -10, 175, -5))[0],
        },
        {
            "uid": "TST:admin0:TST",
            "iso3": "TST",
            "level_code": "admin0",
            "source_id": "tst-open",
            "source_date": "2020-01-01",
            "license": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "license_agreement": None,
            "geometry": geom.normalize(box(171, -9, 172, -8))[0],
        },
    ]
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs="EPSG:4326")


def _build(base_url: str | None = None) -> dict[str, Any]:
    path = "data/processed/TST/tst_admin.parquet"
    item = stac.make_item(
        "pab-tst-admin",
        path,
        _table(),
        "Testland",
        "All levels.",
        {"pab:iso3": "TST"},
        docs_key="TST",
    )
    d = stac.write_item(item, base_url)
    stac.write_catalog([(stac.item_path(path), d)], base_url)
    return d


def _links(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())["links"]


def test_stac_root_in_data_with_relative_links(project: Path) -> None:
    d = _build()
    assert (project / "data/catalog.json").exists()
    assert (project / "data/collection.json").exists()
    assert not (project / "stac").exists()
    cat = _links(project / "data/catalog.json")
    selfs = [lk["href"] for lk in cat if lk["rel"] == "self"]
    assert selfs == [f"{HTTPS}/catalog.json"]  # only absolute link of the tree
    internal = {"root", "parent", "child", "item", "collection"}
    for f in ("data/catalog.json", "data/collection.json"):
        for lk in _links(project / f):
            if lk["rel"] in internal:
                assert lk["href"].startswith("./"), lk
    items = [
        lk["href"]
        for lk in _links(project / "data/collection.json")
        if lk["rel"] == "item"
    ]
    assert items == ["./processed/TST/tst_admin.stac-item.json"]
    rels = {lk["rel"]: lk["href"] for lk in d["links"]}
    assert rels["collection"] == "../../collection.json"
    assert rels["root"] == "../../catalog.json"
    assert rels["about"] == f"{REPO}/blob/v9.9.9/docs/sources.md#tst-testland"
    assert d["assets"]["data"]["href"] == "tst_admin.parquet"
    assert (
        d["assets"]["manifest-tst-spc"]["href"] == "../../raw/TST/tst-spc/manifest.json"
    )
    # pystac walks the local tree and resolves the assets locally
    cat_obj = pystac.Catalog.from_file(str(project / "data/catalog.json"))
    (item,) = list(cat_obj.get_items(recursive=True))
    assert item.assets["data"].get_absolute_href() == str(
        project / "data/processed/TST/tst_admin.parquet"
    )


def test_stac_base_url_gives_absolute_assets_and_s3_alternate(project: Path) -> None:
    d = _build(HTTPS)
    data = d["assets"]["data"]
    assert data["href"] == f"{HTTPS}/processed/TST/tst_admin.parquet"
    assert (
        data["alternate"]["s3"]["href"]
        == "s3://bucket/prefix/processed/TST/tst_admin.parquet"
    )
    assert stac.ALTERNATE_EXT in d["stac_extensions"]
    assert d["assets"]["manifest-tst-open"]["href"] == (
        "https://raw.githubusercontent.com/example-org/example-repo/v9.9.9/"
        "data/raw/TST/tst-open/manifest.json"
    )
    # links stay relative
    assert {lk["href"] for lk in d["links"] if lk["rel"] == "root"} == {
        "../../catalog.json"
    }


def test_stac_items_carry_provenance(project: Path) -> None:
    d = _build()
    assert stac.check_item(d) == []
    p = d["properties"]
    assert p["pab:source_ids"] == ["tst-open", "tst-spc"]
    assert p["pab:licenses"] == ["CC-BY-NC-SA-4.0", "CC-BY-4.0"]
    assert p["pab:license_agreements"] == ["CSDR-SPC data use agreement"]
    assert "Test Statistics Office" in p["description"]
    assert "CSDR-SPC data use agreement" in p["description"]
    assert {pr["name"] for pr in p["providers"]} >= {
        "Test Statistics Office",
        "Pacific Community (SPC)",
        "Amazon Web Services (S3)",
    }
    assert "pab:git_commit" in p and p["processing:software"]["pab"]
    assert {lk["href"] for lk in d["links"] if lk["rel"] == "via"} == {
        "https://example.org/open",
        "https://example.org/spc",
    }
    assert p["license"] == "other"  # two licences
    assert stac.check_root() == {"data/catalog.json": [], "data/collection.json": []}
    coll = json.loads((project / "data/collection.json").read_text())
    assert coll["summaries"]["license_agreement"] == ["CSDR-SPC data use agreement"]
    first_created = p["created"]
    again = _build()  # re-run keeps `created`
    assert again["properties"]["created"] == first_created


def test_check_reports_missing_fields() -> None:
    assert "link:via" in stac.check_item({"properties": {}, "links": [], "assets": {}})


def test_publish_dry_run_plan(project: Path) -> None:
    _build(HTTPS)
    objs = pub.plan()
    keys = [o.key for o in objs]
    assert keys == [
        "catalog.json",
        "collection.json",
        "combined/partition_checks.json",
        "processed/TST/provenance.json",
        "processed/TST/tst_admin.parquet",
        "processed/TST/tst_admin.stac-item.json",
    ]
    types = {o.key: o.content_type for o in objs}
    assert types["processed/TST/tst_admin.parquet"] == "application/vnd.apache.parquet"
    assert types["processed/TST/tst_admin.stac-item.json"] == "application/geo+json"
    assert types["catalog.json"] == "application/json"
    sizes = {o.key: o.size for o in objs}
    assert sizes["processed/TST/tst_admin.parquet"] == os.path.getsize(
        project / "data/processed/TST/tst_admin.parquet"
    )
    report = pub.dryrun_report(objs)
    assert "s3://bucket/prefix/" in report
    assert all(f"`{k}`" in report for k in keys)
    assert "tst_admin_restricted.parquet" in report  # listed as excluded
    assert "data/processed/TST/tst_admin_restricted.parquet" in pub.excluded_files()
    with pytest.raises(ValueError):
        pub.published_key("data/raw/TST/tst-open/original.shp")
    with pytest.raises(ValueError):
        pub.published_key("config/publish.yml")


def test_licence_agreement_accepted_and_required() -> None:
    spc = SOURCES["tst-spc"]
    assert licenses.resolve(spc) == (
        "CC-BY-NC-SA-4.0",
        "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    )
    assert licenses.agreement(spc) == "CSDR-SPC data use agreement"
    assert licenses.redistributable(spc)
    licenses.check(spc)  # agreement present: accepted, not restricted
    assert licenses.agreement(SOURCES["tst-open"]) is None
    # a level override inherits the source's agreement
    lvl = {"license": {"name": "CC-BY-NC-SA-4.0"}}
    assert licenses.agreement(spc, lvl) == "CSDR-SPC data use agreement"
    no_agreement = {
        "source_id": "x",
        "license": {"name": "CC-BY-NC-SA-4.0", "redistribution_ok": True},
    }
    with pytest.raises(ValueError, match="agreement"):
        licenses.check(no_agreement)
    restricted = {
        "source_id": "y",
        "license": {"name": "CC-BY-NC-SA-4.0", "redistribution_ok": False},
    }
    licenses.check(restricted)  # restricted rows need no agreement
    assert not licenses.redistributable(restricted)


def test_finest_licence_columns_join_distinct_values() -> None:
    from pab import combine

    assert "license_agreement" in combine.FINEST_COLUMNS
    assert (
        combine._joined(["CC-BY-4.0", None, "CC-BY-4.0", "LO-2.0"])
        == "CC-BY-4.0;LO-2.0"
    )
    assert combine._joined([None, float("nan")]) is None


def test_long_schema_has_license_agreement() -> None:
    from pab import process

    cols = process.LONG_COLUMNS
    assert cols.index("license_agreement") == cols.index("license_url") + 1


def test_eez_selection_reads_layer_and_source_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pab import eez

    monkeypatch.setattr(pio, "ROOT", str(tmp_path))
    reg = {
        "iso3": "EEZ",
        "sources": [
            {
                "source_id": "spc-eez",
                "status": "selected",
                "levels": [{"layer": "extracted/<xx>_eez_pol.shp"}],
            },
            {
                "source_id": "mr-eez",
                "status": "alternative",
                "levels": [{"layer": "extracted/eez.shp"}],
            },
        ],
    }
    _write(
        tmp_path,
        "config/eez_polygons.csv",
        "mrgid,geoname,pol_type,relevance,pab_iso3,source_id,layer\n"
        "8325.0,Fiji EEZ,200 NM,pict,FJI,spc-eez,fj_eez_pol\n"
        "21798,Torres Strait,Joint regime,shared,PNG;AUS,mr-eez,\n"
        "999,Elsewhere,200NM,neighbour,AUS,spc-eez,au_eez_pol\n",
    )
    sel = eez.selection(reg)
    assert list(sel["mrgid"]) == ["8325", "21798"]
    assert list(sel["source_id"]) == ["spc-eez", "mr-eez"]
    assert list(sel["layer"]) == ["fj_eez_pol", "extracted/eez.shp"]
    assert sel["claimants"].iloc[1] == ["PNG", "AUS"]
    # legacy Marine Regions CSV (upper-case, no layer/source_id): selected source's layer
    _write(
        tmp_path,
        "config/eez_polygons.csv",
        "MRGID,GEONAME,POL_TYPE,relevance,pab_iso3\n8325,Fiji,200NM,pict,FJI\n",
    )
    reg["sources"][0]["levels"][0]["layer"] = "extracted/eez.shp"
    legacy = eez.selection(reg)
    assert list(legacy[["source_id", "layer"]].iloc[0]) == [
        "spc-eez",
        "extracted/eez.shp",
    ]
    assert eez._pol_type("200 NM") == "200NM"
    assert eez._published_area("2051516407742.0") == pytest.approx(2051516.4)
    assert eez._published_area("1255288") == 1255288.0


def test_publish_upload_skips_existing_unless_overwrite(
    project: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    from obstore.store import LocalStore

    _build(HTTPS)
    dest = tmp_path_factory.mktemp("bucket")
    store = LocalStore(str(dest))
    objs = pub.plan()
    first = pub.upload(objs, store=store)
    assert first["uploaded"] == len(objs) and first["skipped"] == 0
    assert (dest / "processed/TST/tst_admin.parquet").stat().st_size == os.path.getsize(
        project / "data/processed/TST/tst_admin.parquet"
    )
    assert not (dest / "processed/TST/tst_admin_restricted.parquet").exists()
    again = pub.upload(objs, store=store)
    assert again["uploaded"] == 0 and again["skipped"] == len(objs)
    assert pub.upload(objs, overwrite=True, store=store)["uploaded"] == len(objs)


def test_agreement_texts_with_semicolons_are_not_split() -> None:
    from pab import combine

    a = "LINZ Data Service licence CC BY 4.0; NZ data agreement"
    joined = combine._joined([a, "CSDR-SPC agreement", a], combine.AGREEMENT_SEP)
    assert stac._split([joined, None], " | ") == [a, "CSDR-SPC agreement"]
