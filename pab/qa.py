"""Per-country QA: counts per level, validity, nulls, licence flags, child-vs-parent area
differences, and EEZ coverage of land units.

Area comparisons run in EPSG:6933 (equal area); antimeridian-split parts are split identically
in parent and child, so overlays there are exact.
"""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import shapely

from pab import geom

MISMATCH_PCT = (
    1.0  # flag parents whose children differ by more than 1 % of the parent area
)


def country_qa(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    """Compute QA metrics for one per-country long table."""
    land = gdf[gdf["level_code"] != "eez"]
    res: dict[str, Any] = {
        "rows": len(gdf),
        "counts": gdf.groupby(
            ["level_rank", "level_code", "level_name_local"], dropna=False
        )
        .size()
        .reset_index(name="n")
        .to_dict("records"),
        "invalid_geometries": int((~gdf.geometry.is_valid).sum()),
        "empty_geometries": int(gdf.geometry.is_empty.sum()),
        "null_names": int(gdf["unit_name"].isna().sum()),
        "generated_codes": int((gdf["code_scheme"] == "generated").sum()),
        "restricted": land[land["license_restricted"]]
        .groupby("level_code")
        .size()
        .to_dict(),
        "nesting": nesting_checks(gdf),
    }
    eez_rows = gdf[gdf["level_code"] == "eez"]
    if len(eez_rows):
        res["eez_rows"] = len(eez_rows)
        res["land_without_eez"] = int(land["eez_uid"].isna().sum())
        res["eez_uids_used"] = sorted(land["eez_uid"].dropna().unique().tolist())
        res["admin0_outside_eez_km2"] = admin0_outside_eez(gdf)
    return res


def admin0_outside_eez(gdf: gpd.GeoDataFrame) -> float | None:
    """Area (km2) of admin0 outside the hole-filled union of the country's 200NM EEZ polygons."""
    from pab.eez import fill_holes

    zones = gdf[(gdf["level_code"] == "eez") & gdf["nests"]]
    a0 = gdf[gdf["level_code"] == "admin0"]
    if zones.empty or a0.empty:
        return None
    z = gpd.GeoSeries(
        [
            fill_holes(g, sid)
            for g, sid in zip(zones.geometry, zones["source_id"], strict=True)
        ],
        crs=geom.STORAGE_CRS,
    ).to_crs(geom.AREA_CRS)
    a = a0.geometry.to_crs(geom.AREA_CRS).iloc[0]
    return round(
        float(shapely.difference(a, shapely.union_all(z.to_numpy())).area / 1e6), 4
    )


def nesting_checks(gdf: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    """Child-union vs parent comparison per (level, layer, licence-restricted) group."""
    eq = gdf.to_crs(geom.AREA_CRS)
    by_uid = dict(zip(eq["uid"], eq.geometry, strict=True))
    out = []
    kids_all = eq[eq["parent_uid"].notna() & (eq["level_code"] != "other")]
    for (level, name, _restricted), kids in kids_all.groupby(
        ["level_code", "level_name_local", "license_restricted"], dropna=False
    ):
        source = ";".join(sorted(set(kids["source_id"])))
        parent_area = child_area = inside = 0.0
        flagged = []
        for puid, grp in kids.groupby("parent_uid"):
            pg = by_uid.get(puid)
            if pg is None:
                continue
            cu = shapely.union_all(grp.geometry.to_numpy())
            pa, ca = pg.area / 1e6, cu.area / 1e6
            ins = shapely.intersection(cu, pg).area / 1e6
            parent_area += pa
            child_area += ca
            inside += ins
            outside_pct = 100 * (ca - ins) / pa if pa else 0.0
            uncovered_pct = 100 * (pa - ins) / pa if pa else 0.0
            if outside_pct > MISMATCH_PCT or uncovered_pct > MISMATCH_PCT:
                flagged.append(
                    {
                        "parent_uid": puid,
                        "children": len(grp),
                        "outside_pct": round(outside_pct, 2),
                        "uncovered_pct": round(uncovered_pct, 2),
                    }
                )
        prow = gdf[gdf["uid"].isin(kids["parent_uid"])]
        n_parent_units = (
            int(
                (
                    gdf["level_code"].eq(prow["level_code"].iloc[0])
                    & gdf["license_restricted"].isin(set(prow["license_restricted"]))
                ).sum()
            )
            if len(prow)
            else 0
        )
        out.append(
            {
                "level_code": level,
                "level_name_local": name,
                "source_id": source,
                "units": len(kids),
                "parents_with_children": int(kids["parent_uid"].nunique()),
                "parent_level_units": n_parent_units,
                "parent_km2": round(parent_area, 3),
                "children_km2": round(child_area, 3),
                "children_outside_parent_km2": round(child_area - inside, 3) + 0.0,
                "parent_uncovered_km2": round(parent_area - inside, 3) + 0.0,
                "flagged_parents": sorted(
                    flagged, key=lambda f: -max(f["outside_pct"], f["uncovered_pct"])
                ),
            }
        )
    return out


def qa_markdown(res: dict[str, Any]) -> str:
    """Render a QA result as Markdown."""
    lines = ["## QA", ""]
    lines.append(
        f"Rows: {res['rows']}. Invalid geometries: {res['invalid_geometries']}. Empty: {res['empty_geometries']}. "
        f"Null names: {res['null_names']}. Rows with generated codes: {res['generated_codes']}."
    )
    if res.get("restricted"):
        lines.append(
            f"Licence-restricted rows (excluded from combined products): {res['restricted']}."
        )
    else:
        lines.append("Licence-restricted rows: none.")
    if "eez_rows" in res:
        lines.append(
            f"EEZ: {res['eez_rows']} EEZ row(s); land rows without eez_uid: {res['land_without_eez']}; "
            f"admin0 area outside the 200NM EEZ: {res['admin0_outside_eez_km2']} km2."
        )
    else:
        lines.append("EEZ: not yet assigned.")
    lines += ["", "### Children vs parent (area, km2)", ""]
    lines.append(
        "| level | layer | source | units | parents with children / parent units | parent km2 | children km2 | children outside parent | parent not covered | parents > 1% off |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for n in res["nesting"]:
        lines.append(
            f"| {n['level_code']} | {n['level_name_local']} | {n['source_id']} | {n['units']} | {n['parents_with_children']} / {n['parent_level_units']} | "
            f"{n['parent_km2']:.2f} | {n['children_km2']:.2f} | {n['children_outside_parent_km2']:.3f} | {n['parent_uncovered_km2']:.3f} | {len(n['flagged_parents'])} |"
        )
    worst = [
        (n["level_code"], f) for n in res["nesting"] for f in n["flagged_parents"][:3]
    ]
    if worst:
        lines += [
            "",
            "Largest mismatches (up to 3 per level): "
            + "; ".join(
                f"{lv} {f['parent_uid']} outside {f['outside_pct']}% / uncovered {f['uncovered_pct']}%"
                for lv, f in worst
            ),
        ]
    return "\n".join(lines) + "\n"


def summary_row(
    iso3: str, gdf: gpd.GeoDataFrame, res: dict[str, Any]
) -> dict[str, Any]:
    """One-line summary for the processing summary report."""
    counts = gdf.groupby("level_code").size().to_dict()
    worst = max(
        (
            max(f["outside_pct"], f["uncovered_pct"])
            for n in res["nesting"]
            for f in n["flagged_parents"]
        ),
        default=0.0,
    )
    return {
        "iso3": iso3,
        **{
            k: counts.get(k, 0)
            for k in [
                "eez",
                "admin0",
                "admin1",
                "admin2",
                "admin3",
                "admin4",
                "admin5",
                "other",
            ]
        },
        "invalid": res["invalid_geometries"],
        "restricted_rows": int(sum(res["restricted"].values()))
        if res.get("restricted")
        else 0,
        "flagged_parents": int(sum(len(n["flagged_parents"]) for n in res["nesting"])),
        "worst_mismatch_pct": round(float(worst), 1),
        "land_without_eez": res.get("land_without_eez"),
    }
