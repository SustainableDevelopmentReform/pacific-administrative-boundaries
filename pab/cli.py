"""Command-line entry point: ``pab cache | process | assign-eez | combine | stac | qa | publish | validate``."""

from __future__ import annotations

import logging

import typer

app = typer.Typer(
    help="Pacific administrative boundaries pipeline (cache -> process -> combine -> stac).",
    no_args_is_help=True,
)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logging.getLogger("pyogrio").setLevel(logging.WARNING)
logger = logging.getLogger("pab")


def _targets(iso3: str | None, all_: bool) -> list[str]:
    from pab import registry

    if all_:
        return registry.all_iso3()
    if not iso3:
        raise typer.BadParameter("give an ISO3 code or --all")
    return [iso3.upper()]


@app.command()
def validate() -> None:
    """Validate every source register against the schema."""
    from pab import io as pio
    from pab import registry

    bad = 0
    for iso3 in [*registry.all_iso3(), "EEZ"]:
        if not pio.exists(f"config/sources/{iso3}.yml"):
            typer.echo(f"{iso3}: no register")
            continue
        try:
            reg = registry.load_register(iso3)
            typer.echo(
                f"{iso3}: ok ({len(registry.used_levels(reg))} levels to process)"
            )
        except Exception as exc:  # noqa: BLE001 - report every bad register
            bad += 1
            typer.echo(f"{iso3}: INVALID {exc}")
    raise typer.Exit(1 if bad else 0)


@app.command()
def cache(
    iso3: str = typer.Argument(None, help="ISO3 code (or EEZ)."),
    all_: bool = typer.Option(False, "--all", help="All countries."),
    source: str = typer.Option(None, help="Only this source_id."),
    overwrite: bool = typer.Option(
        False, help="Re-download even if a manifest exists."
    ),
) -> None:
    """(Re)download every source processing reads (``registry.sources_used``) and write manifests."""
    from pab import cache as pcache
    from pab import registry

    for code in ["EEZ"] if (iso3 or "").upper() == "EEZ" else _targets(iso3, all_):
        used = set(registry.sources_used(code))
        for s in registry.load_register(code)["sources"]:
            if (source and s["source_id"] != source) or (
                not source and s["source_id"] not in used
            ):
                continue
            try:
                typer.echo(
                    pcache.cache_source(code, s["source_id"], overwrite=overwrite)
                )
            except Exception as exc:  # noqa: BLE001 - keep going over sources
                typer.echo(f"{s['source_id']}: FAILED {exc}")


@app.command()
def process(
    iso3: str = typer.Argument(None, help="ISO3 code, or EEZ for the EEZ product."),
    all_: bool = typer.Option(False, "--all", help="All countries."),
    overwrite: bool = typer.Option(False, help="Rebuild existing outputs."),
    assign_eez: bool = typer.Option(
        False, "--assign-eez", help="Only (re)stamp eez_uid on existing tables."
    ),
) -> None:
    """raw -> per-country long GeoParquet (or ``process EEZ`` -> pacific_eez.parquet)."""
    from pab import eez
    from pab import process as proc

    if (iso3 or "").upper() == "EEZ":
        eez.build_eez(overwrite=overwrite)
        return
    failed = []
    for code in _targets(iso3, all_):
        try:
            if assign_eez:
                eez.assign_eez(code)
            else:
                proc.process_country(code, overwrite=overwrite)
        except Exception:
            logger.exception("%s failed", code)
            failed.append(code)
    if failed:
        typer.echo(f"failed: {failed}")
        raise typer.Exit(1)


@app.command("assign-eez")
def assign_eez_cmd(
    iso3: str = typer.Argument(None, help="ISO3 code."),
    all_: bool = typer.Option(False, "--all", help="All processed countries."),
) -> None:
    """Re-runnable step: stamp eez_uid on existing per-country tables and add their EEZ rows."""
    from pab import eez, process
    from pab import io as pio

    for code in _targets(iso3, all_):
        if pio.exists(process.admin_path(code)):
            eez.assign_eez(code)


@app.command()
def combine(
    overwrite: bool = typer.Option(True, help="Rebuild combined products."),
) -> None:
    """Per-country tables -> data/combined/pacific_admin(.|_finest).parquet."""
    from pab import combine as comb

    res = comb.combine(overwrite=overwrite)
    for c in res.get("checks", []):
        typer.echo(
            f"{c['iso3']} {c['eez_uid']}: parts {c['parts_km2']} vs eez {c['eez_km2']} km2 ({c['diff_pct']:+.5f}%) {'ok' if c['ok'] else 'FAIL'}"
        )


@app.command()
def stac(
    validate_: bool = typer.Option(
        True, "--validate/--no-validate", help="Validate with pystac."
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Published HTTPS root (e.g. https_base from config/publish.yml): asset hrefs "
        "become absolute URLs with an s3:// alternate. Default: relative hrefs (local use).",
    ),
    check: bool = typer.Option(
        False, "--check", help="Assert provenance fields on every item; print a table."
    ),
) -> None:
    """Write STAC items beside each parquet and data/catalog.json + data/collection.json."""
    from pab import stac as pstac

    pstac.build_catalog(base_url=base_url)
    bad = 0
    if validate_:
        for p, r in pstac.validate_all().items():
            typer.echo(f"{r}: {p}")
            bad += r != "valid"
    if check:
        bad += _print_check(pstac)
    raise typer.Exit(1 if bad else 0)


def _print_check(pstac: object) -> int:
    """Print the ``--check`` table; return the number of failing objects."""
    rows = pstac.check_all()  # type: ignore[attr-defined]
    cols = ["item", "iso3", "levels", "sources", "providers", "via", "licences", "agreements", "git_commit", "missing"]  # fmt: skip
    typer.echo("| " + " | ".join(cols) + " |")
    typer.echo("|" + "---|" * len(cols))
    for r in rows:
        r = {**r, "missing": ", ".join(r["missing"]) or "ok"}
        typer.echo("| " + " | ".join(str(r[c]) for c in cols) + " |")
    bad = sum(1 for r in rows if r["missing"])
    for path, miss in pstac.check_root().items():  # type: ignore[attr-defined]
        typer.echo(f"{path}: {', '.join(miss) or 'ok'}")
        bad += bool(miss)
    typer.echo(f"check: {len(rows)} items, {bad} object(s) with missing fields")
    return bad


@app.command()
def publish(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List every object and size; upload nothing."
    ),
    overwrite: bool = typer.Option(False, help="Re-upload objects that already exist."),
    verify: bool = typer.Option(
        False,
        "--verify",
        help="Read the published catalog over HTTPS, validate, HEAD every asset, read one parquet.",
    ),
    base_url: str = typer.Option(
        None, "--base-url", help="HTTPS root to verify (default: https_base)."
    ),
    region: str = typer.Option(
        None, help="AWS region of the bucket (else AWS_REGION)."
    ),
    report: str = typer.Option(
        "reports/publish_dryrun.md", help="Where --dry-run writes its markdown report."
    ),
) -> None:
    """Mirror data/processed, data/combined and the STAC root to s3://<bucket>/<prefix>/."""
    from pab import io as pio
    from pab import publish as pub

    if verify:
        res = pub.verify(base_url)
        for k in ("catalog", "collections", "items", "assets_checked", "parquet"):
            typer.echo(f"{k}: {res[k]}")
        for p in res["problems"]:
            typer.echo(f"PROBLEM: {p}")
        typer.echo(
            "verify: ok" if res["ok"] else f"verify: {len(res['problems'])} problem(s)"
        )
        raise typer.Exit(0 if res["ok"] else 1)
    objs = pub.plan()
    if dry_run:
        for o in objs:
            typer.echo(f"{o.size:>12,}  {o.content_type:<32}  {pub.s3_root()}/{o.key}")
        typer.echo(
            f"{len(objs)} objects, {sum(o.size for o in objs):,} bytes (dry run)"
        )
        pio.write_text(report, pub.dryrun_report(objs))
        typer.echo(f"report: {report}")
        return
    counts = pub.upload(objs, overwrite=overwrite, region=region)
    typer.echo(
        f"uploaded {counts['uploaded']} ({counts['bytes']:,} bytes), skipped {counts['skipped']}"
    )


@app.command()
def qa(
    iso3: str = typer.Argument(None, help="ISO3 code."),
    all_: bool = typer.Option(False, "--all", help="All processed countries."),
) -> None:
    """Per-country QA reports (reports/qa_<ISO3>.md) and reports/processing_summary.md."""
    from pab import io as pio
    from pab import process, report
    from pab import qa as pqa

    rows = []
    for code in _targets(iso3, all_):
        if not pio.exists(process.admin_path(code)):
            continue
        gdf = process.load_country(code)  # QA covers the restricted companion rows too
        res = pqa.country_qa(gdf)
        pio.write_text(
            f"reports/qa_{code}.md", f"# QA: {code}\n\n" + pqa.qa_markdown(res)
        )
        rows.append(pqa.summary_row(code, gdf, res))
    if all_ and rows:
        extra = ""
        if pio.exists("data/combined/partition_checks.json"):
            pc = pio.read_json("data/combined/partition_checks.json")
            extra = "## Finest partition area check (sum of parts vs EEZ domain, tolerance 0.01 %)\n\n"
            extra += "| iso3 | eez_uid | domain km2 | parts km2 | diff % | ok | land beyond EEZ outline km2 |\n|---|---|---|---|---|---|---|\n"
            for c in pc["checks"]:
                extra += f"| {c['iso3']} | {c['eez_uid']} | {c['eez_km2']} | {c['parts_km2']} | {c['diff_pct']} | {c['ok']} | {c.get('land_outside_outline_km2', 0)} |\n"
            extra += (
                "\nRestricted rows excluded from data/combined/*: "
                + (
                    ", ".join(
                        f"{k} ({v})" for k, v in pc["restricted_rows_excluded"].items()
                    )
                    or "none"
                )
                + "\n"
            )
            extra += (
                "\nFinest partition rows by finest level: "
                + ", ".join(f"{k} {v}" for k, v in pc["finest_rows_by_level"].items())
                + "\n"
            )
        report.write_summary(rows, extra)


if __name__ == "__main__":
    app()
