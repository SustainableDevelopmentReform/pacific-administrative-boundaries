"""Register schema, level selection rules and field-spec evaluation."""

import jsonschema
import pandas as pd
import pytest

from pab import fields, registry


def _reg(**over: object) -> dict:
    base = {
        "iso3": "XXX",
        "sources": [
            {
                "source_id": "xxx-a",
                "status": "selected",
                "license": {"name": "CC-BY-4.0", "redistribution_ok": True},
                "raw_path": "data/raw/XXX/xxx-a/",
                "levels": [
                    {
                        "level_code": "admin1",
                        "level_type": "state_province",
                        "layer": "a.geojson",
                        "nests": True,
                    },
                    {
                        "level_code": "admin2",
                        "level_type": "district",
                        "layer": "b.geojson",
                        "nests": True,
                    },
                    {
                        "level_code": "admin0",
                        "level_type": "country",
                        "layer": "c.geojson",
                        "nests": True,
                        "use": False,
                    },
                ],
            },
            {
                "source_id": "xxx-b",
                "status": "alternative",
                "license": {"name": "GADM", "redistribution_ok": False},
                "raw_path": "data/raw/XXX/xxx-b/",
                "levels": [
                    {
                        "level_code": "admin2",
                        "level_type": "district",
                        "layer": "d.gpkg::L2",
                        "nests": True,
                    }
                ],
            },
        ],
        "decisions": [{"level_code": "admin2", "chosen": "xxx-a"}],
    }
    base.update(over)
    return base


def test_countries_registry_has_22() -> None:
    assert len(registry.all_iso3()) == 22
    assert registry.country_meta("FJI")["political_status"] == "independent"


def test_all_registers_validate() -> None:
    for iso3 in [*registry.all_iso3(), "EEZ"]:
        registry.load_register(iso3)


def test_used_levels_rules() -> None:
    specs = registry.used_levels(_reg())
    assert [(s.source_id, s.level_code) for s in specs] == [
        ("xxx-a", "admin1"),
        ("xxx-a", "admin2"),
    ]


def test_decision_overrides_selected_source() -> None:
    reg = _reg(decisions=[{"level_code": "admin2", "chosen": "xxx-b"}])
    used = {(s.source_id, s.level_code) for s in registry.used_levels(reg)}
    assert ("xxx-a", "admin2") not in used
    assert (
        "xxx-b",
        "admin2",
    ) in used  # alternative chosen by decision: processed, with a note
    spec = next(s for s in registry.used_levels(reg) if s.source_id == "xxx-b")
    assert spec.restricted and spec.notes


def test_schema_rejects_bad_level_code() -> None:
    reg = _reg()
    reg["sources"][0]["levels"][0]["level_code"] = "admin9"
    with pytest.raises(jsonschema.ValidationError):
        registry.validate_register(reg)


def test_schema_rejects_string_filter() -> None:
    reg = _reg()
    reg["sources"][0]["levels"][0]["filter"] = "STATEFP == '66'"
    with pytest.raises(jsonschema.ValidationError):
        registry.validate_register(reg)


def test_duplicate_source_ids_rejected() -> None:
    reg = _reg()
    reg["sources"][1]["source_id"] = "xxx-a"
    with pytest.raises(ValueError, match="duplicate"):
        registry.validate_register(reg)


def test_field_specs() -> None:
    df = pd.DataFrame(
        {
            "eaid": [10101, 10102.0, 20301],
            "name": ["Laulii 1", "Laulii 2", "x 3"],
            "s": ["60", "60", "60"],
            "c": ["010", "020", "030"],
        }
    )
    assert fields.evaluate(df, {"field": "eaid", "floordiv": 100}).tolist() == [
        "101",
        "101",
        "203",
    ]
    assert fields.evaluate(
        df, {"field": "name", "regex_sub": [r"\s*\d+$", ""]}
    ).tolist() == ["Laulii", "Laulii", "x"]
    assert fields.evaluate(df, {"template": "{s}{c}"}).tolist() == [
        "60010",
        "60020",
        "60030",
    ]
    assert fields.evaluate(df, {"field": "c", "slice": [0, 2]}).tolist() == [
        "01",
        "02",
        "03",
    ]
    assert fields.evaluate(df, {"field": "eaid", "map": {10101: "a"}}).tolist() == [
        "a",
        "10102",
        "20301",
    ]
    assert fields.evaluate(df, "eaid").tolist() == [
        "10101",
        "10102",
        "20301",
    ]  # 10102.0 -> '10102'
    assert fields.evaluate(df, None) is None
    with pytest.raises(KeyError):
        fields.evaluate(df, "missing")


def test_title_case_keeps_okina() -> None:
    df = pd.DataFrame({"n": ["ta'u village", "ngatiarua-atiu"]})
    assert fields.evaluate(df, {"field": "n", "case": "title"}).tolist() == [
        "Ta'u Village",
        "Ngatiarua-Atiu",
    ]


def test_filters() -> None:
    df = pd.DataFrame(
        {
            "STATEFP": ["60", "66", "60"],
            "COUSUBFP": ["00000", "1", "2"],
            "ALAND20": [0, 5, 3],
        }
    )
    assert len(fields.apply_filter(df, {"STATEFP": "60"}, None)) == 2
    assert len(fields.apply_filter(df, None, {"COUSUBFP": "00000"})) == 2
    assert len(fields.apply_filter(df, {"ALAND20": {"gt": 0}}, None)) == 2


def test_licence_normalisation() -> None:
    from pab import licenses

    assert (
        licenses.normalize(
            "CC-BY (Creative Commons Attribution; version unstated on PDH)"
        )
        == "CC-BY-4.0"
    )
    assert licenses.normalize("Licence Ouverte v2.0 (Etalab)") == "LO-2.0"
    assert (
        licenses.normalize("Public domain (US Government work, 17 U.S.C. 105)")
        == "Public domain (US Government work)"
    )
    with pytest.raises(ValueError):
        licenses.normalize("ADM1: Public Domain; ADM0: ODbL-1.0")
    src = {"license": {"name": "ADM1: Public Domain; ADM0: ODbL-1.0", "url": "u"}}
    assert licenses.resolve(
        src, {"license": {"name": "Public Domain", "url": "x"}}
    ) == ("Public domain", "x")


def test_sources_used_cover_processed_outputs() -> None:
    """Every source_id in the processed parquet files is in sources_used for that country."""
    import glob

    import pyarrow.parquet as pq

    eez_sources = set(registry.sources_used("EEZ"))
    checked = 0
    for iso3 in registry.all_iso3():
        used = set(registry.sources_used(iso3))
        for path in glob.glob(f"data/processed/{iso3}/*.parquet"):
            t = pq.read_table(path, columns=["source_id", "level_code"]).to_pandas()
            land = set(t.loc[t["level_code"] != "eez", "source_id"])
            assert land <= used, (iso3, land - used)
            assert set(t.loc[t["level_code"] == "eez", "source_id"]) <= eez_sources
            checked += 1
    if checked == 0:
        pytest.skip("no processed outputs present")


def test_sources_used_includes_supplementary_sources() -> None:
    assert "pcn-naturalearth-10m-admin0" in registry.sources_used("PCN")
    assert "mhl-usaid-pacioos-lga-2017" in registry.sources_used("MHL")
    # D-023: LINZ island geometry, SDD census districts/EAs, PCRAFI electoral (and names)
    assert {
        "cok-linz-island-polygons-topo",
        "cok-spc-sdd-phc2011-boundaries",
        "cok-spc-pcrafi-2010-exposure-boundaries",
    } <= set(registry.sources_used("COK"))
    assert "cok-geoboundaries-gbopen" not in registry.sources_used("COK")
    # clip_to sources are read too
    assert "niu-linz-island-polygons-topo" in registry.sources_used("NIU")
    assert "nru-gadm-41" not in registry.sources_used("NRU")
