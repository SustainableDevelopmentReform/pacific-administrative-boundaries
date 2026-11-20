"""Markdown run reports: reports/processing_<ISO3>.md and reports/processing_summary.md."""

from __future__ import annotations

from typing import Any

import geopandas as gpd

from pab import io as pio
from pab import qa


def write_processing_report(
    iso3: str,
    reg: dict[str, Any],
    built: list[Any],
    gdf: gpd.GeoDataFrame,
    qa_result: dict[str, Any],
) -> None:
    """Write the short per-country processing report."""
    sources = {s["source_id"]: s for s in reg["sources"]}
    lines = [f"# Processing report: {iso3} ({reg.get('country_name', '')})", ""]
    lines.append(
        f"Output: `data/processed/{iso3}/{iso3.lower()}_admin.parquet` ({len(gdf)} rows)."
    )
    lines += [
        "",
        "## Levels",
        "",
        "| level | type | local name | nests | units | source | licence | restricted | geometry_method |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for (lc, lt, ln, nests, sid), grp in gdf.groupby(
        ["level_rank", "level_type", "level_name_local", "nests", "source_id"],
        sort=True,
        dropna=False,
    ):
        level = grp["level_code"].iloc[0]
        methods = sorted({m for gm in grp["geometry_method"] for m in gm.split(";")})
        lic = sources.get(sid, {}).get("license", {}).get("name", "")
        lines.append(
            f"| {level} | {lt} | {ln} | {nests} | {len(grp)} | {sid} | {lic} | {bool(grp['license_restricted'].iloc[0])} | {', '.join(methods)} |"
        )
    lines += ["", "## Processing notes", ""]
    for b in built:
        if not b.notes and not b.parent_stats:
            continue
        lines.append(f"- **{b.level_code} / {b.spec.key}** ({b.spec.source_id}):")
        for n in b.notes:
            lines.append(f"  - {n}")
        if b.parent_stats:
            ps = b.parent_stats
            lines.append(
                f"  - parents ({ps['parent_level']}): {ps['by_code']} by code, {ps['by_overlap']} by largest overlap, "
                f"{ps['orphans']} orphan(s); {ps['area_weighted_share_inside_parent']:.2%} of area inside assigned parent; "
                f"{ps['units_below_90pct_inside']} unit(s) < 90% inside"
            )
    edits = [
        (s["source_id"], lv)
        for s in reg["sources"]
        for lv in (s.get("levels") or [])
        if "[processing]" in str(lv.get("notes") or "")
    ]
    if edits:
        lines += ["", "## Register mapping changes (processing stage)", ""]
        for sid, lv in edits:
            note = str(lv["notes"]).split("[processing]", 1)[1].strip()
            lines.append(
                f"- {sid} {lv['level_code']} ({lv.get('level_name_local')}): {note}"
            )
    lines += ["", qa.qa_markdown(qa_result)]
    pio.write_text(f"reports/processing_{iso3}.md", "\n".join(lines))


def write_summary(rows: list[dict[str, Any]], extra: str = "") -> None:
    """Write reports/processing_summary.md from :func:`pab.qa.summary_row` rows."""
    cols = list(rows[0].keys()) if rows else []
    lines = [
        "# Processing summary",
        "",
        "Rows per level_code and QA flags per country.",
        "",
    ]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "---|" * len(cols))
    for r in rows:
        lines.append(
            "| " + " | ".join("" if r[c] is None else str(r[c]) for c in cols) + " |"
        )
    lines += ["", extra]
    pio.write_text("reports/processing_summary.md", "\n".join(lines) + "\n")
