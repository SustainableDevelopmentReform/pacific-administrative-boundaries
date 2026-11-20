"""Publishing (decisions D-021/D-022): mirror the published tree to S3 and verify it over HTTPS.

The published root is the local ``data/`` folder (it holds ``catalog.json`` and
``collection.json``) and maps to ``s3://<s3_bucket>/<s3_prefix>/`` from ``config/publish.yml``.
What is mirrored: ``data/processed/**`` (except ``*_restricted.parquet``), ``data/combined/**``,
``data/catalog.json`` and ``data/collection.json``. Nothing under ``data/raw`` is ever mirrored
(no redistribution rights for originals); raw manifests are published through the GitHub
repository instead, and STAC items link to them there.

Uploads go through obstore (as in the reference repository). Credentials come from the
standard AWS environment variables, or from boto3's credential chain (profiles, SSO) when
boto3 is installed.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from pab import io as pio

logger = logging.getLogger(__name__)

PUBLISH_CONFIG = "config/publish.yml"
STAC_ROOT = "data"  # published root (D-022)
INCLUDE_DIRS = ("data/processed", "data/combined")
ROOT_FILES = ("data/catalog.json", "data/collection.json")
EXCLUDE_SUFFIXES = ("_restricted.parquet",)
NEVER_PUBLISHED = ("data/raw/", "data/raw")

PARQUET = "application/vnd.apache.parquet"
GEOJSON = "application/geo+json"
JSON = "application/json"


@cache
def config() -> dict[str, Any]:
    """``config/publish.yml`` (repo_url, s3_bucket, s3_prefix, https_base, version, ...)."""
    cfg = yaml.safe_load(pio.read_bytes(PUBLISH_CONFIG))
    for key in ("repo_url", "s3_bucket", "s3_prefix", "https_base", "version"):
        if not cfg.get(key):
            raise ValueError(f"{PUBLISH_CONFIG}: missing {key}")
    cfg["repo_url"] = cfg["repo_url"].rstrip("/")
    cfg["https_base"] = cfg["https_base"].rstrip("/")
    cfg["s3_prefix"] = cfg["s3_prefix"].strip("/")
    cfg.setdefault("git_ref", cfg["version"])
    cfg.setdefault("project_name", "Pacific administrative boundaries")
    return cfg


def project_path(path: str) -> str:
    """Project-relative POSIX path for a project-relative or absolute local path."""
    if os.path.isabs(path):
        path = os.path.relpath(path, pio.ROOT)
    return path.replace(os.sep, "/")


def published_key(path: str) -> str:
    """Key of a local file below the published root: ``data/processed/x`` -> ``processed/x``."""
    rel = project_path(path)
    if not rel.startswith(f"{STAC_ROOT}/"):
        raise ValueError(f"{rel} is outside the published root {STAC_ROOT}/")
    if rel.startswith(NEVER_PUBLISHED[0]):
        raise ValueError(f"{rel}: data/raw is never published")
    return rel[len(STAC_ROOT) + 1 :]


def s3_root(cfg: dict[str, Any] | None = None) -> str:
    """``s3://<bucket>/<prefix>``."""
    cfg = cfg or config()
    return f"s3://{cfg['s3_bucket']}/{cfg['s3_prefix']}"


def github_blob(path: str, anchor: str | None = None) -> str:
    """Human-readable GitHub URL of a repository file at the release ref."""
    cfg = config()
    url = f"{cfg['repo_url']}/blob/{cfg['git_ref']}/{project_path(path)}"
    return f"{url}#{anchor}" if anchor else url


def github_raw(path: str) -> str:
    """Raw (machine-readable) GitHub URL of a repository file at the release ref."""
    cfg = config()
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)$", cfg["repo_url"])
    if not m:
        return github_blob(path)
    return f"https://raw.githubusercontent.com/{m[1]}/{m[2]}/{cfg['git_ref']}/{project_path(path)}"


def content_type(path: str) -> str:
    """Media type: GeoParquet, STAC Item (GeoJSON) or plain JSON (catalog, collection, others).

    STAC Catalogs and Collections are ``application/json`` per the STAC spec (they are not
    GeoJSON); Items are ``application/geo+json``.
    """
    name = os.path.basename(path)
    if name.endswith(".parquet"):
        return PARQUET
    if name.endswith(".stac-item.json"):
        return GEOJSON
    if name.endswith(".json"):
        return JSON
    if name.endswith(".md"):
        return "text/markdown"
    return "application/octet-stream"


@dataclass(frozen=True)
class PublishObject:
    """One local file to mirror."""

    path: str  # project-relative local path
    key: str  # key below the published root
    size: int
    content_type: str


def _excluded(rel: str) -> bool:
    name = os.path.basename(rel)
    return (
        name.startswith(".")
        or "/__pycache__/" in rel
        or name.endswith(EXCLUDE_SUFFIXES)
        or rel.startswith(NEVER_PUBLISHED[0])
    )


def plan() -> list[PublishObject]:
    """Every local file that ``pab publish`` mirrors, in key order."""
    rels: list[str] = []
    for d in INCLUDE_DIRS:
        base = pio.resolve(d)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(n for n in dirnames if not n.startswith("."))
            rels.extend(
                project_path(os.path.join(dirpath, f)) for f in sorted(filenames)
            )
    rels.extend(p for p in ROOT_FILES if pio.exists(p))
    missing = [p for p in ROOT_FILES if not pio.exists(p)]
    if missing:
        logger.warning("STAC root files missing (run `pab stac`): %s", missing)
    out = [
        PublishObject(
            path=r,
            key=published_key(r),
            size=os.path.getsize(pio.resolve(r)),
            content_type=content_type(r),
        )
        for r in rels
        if not _excluded(r)
    ]
    return sorted(out, key=lambda o: o.key)


def excluded_files() -> list[str]:
    """Local files under the mirrored folders that are deliberately not published."""
    out = []
    for d in INCLUDE_DIRS:
        for dirpath, _, filenames in os.walk(pio.resolve(d)):
            for f in filenames:
                r = project_path(os.path.join(dirpath, f))
                if _excluded(r) and not f.startswith("."):
                    out.append(r)
    return sorted(out)


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def dryrun_report(objs: list[PublishObject], dest: str | None = None) -> str:
    """Markdown report of a dry run: every object, its size and content type."""
    dest = dest or s3_root()
    cfg = config()
    total = sum(o.size for o in objs)
    by_type: dict[str, list[int]] = {}
    for o in objs:
        by_type.setdefault(o.content_type, []).append(o.size)
    lines = [
        "# Publish dry run",
        "",
        f"Destination: `{dest}/` (HTTPS: {cfg['https_base']}/). Version {cfg['version']}.",
        "No object was uploaded. Run `pab publish` (optionally `--overwrite`) to upload.",
        "",
        f"**{len(objs)} objects, {_human(total)}** ({total:,} bytes).",
        "",
        "| content type | objects | size |",
        "|---|---|---|",
        *[
            f"| `{t}` | {len(v)} | {_human(sum(v))} |"
            for t, v in sorted(by_type.items())
        ],
        "",
        (
            "Excluded on purpose: nothing under `data/raw/` (originals and manifests; manifests are "
            "published in the GitHub repository), and these local-only files:"
        ),
        "",
        *([f"* `{p}`" for p in excluded_files()] or ["* none in this build"]),
        "",
        "## Objects",
        "",
        "| key | size | bytes | content type |",
        "|---|---|---|---|",
        *[
            f"| `{o.key}` | {_human(o.size)} | {o.size:,} | `{o.content_type}` |"
            for o in objs
        ],
        "",
    ]
    return "\n".join(lines)


def s3_store(region: str | None = None) -> Any:  # noqa: ANN401 - obstore S3Store
    """obstore S3Store rooted at ``s3://<bucket>/<prefix>``."""
    from obstore.store import S3Store

    cfg = config()
    kwargs: dict[str, Any] = {"prefix": cfg["s3_prefix"]}
    region = region or os.environ.get("AWS_REGION") or cfg.get("s3_region")
    if region:
        kwargs["region"] = region
    try:  # boto3 credential chain (profiles, SSO), as in the reference repository
        from obstore.auth.boto3 import Boto3CredentialProvider

        kwargs["credential_provider"] = Boto3CredentialProvider()
    except ImportError:
        pass  # obstore reads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
    return S3Store(cfg["s3_bucket"], **kwargs)


def upload(
    objs: list[PublishObject],
    overwrite: bool = False,
    region: str | None = None,
    store: Any = None,  # noqa: ANN401 - any obstore store (tests pass a LocalStore)
) -> dict[str, int]:
    """Upload ``objs``; existing keys are skipped unless ``overwrite``. Returns counts."""
    import obstore
    from obstore.store import S3Store

    store = store if store is not None else s3_store(region)
    # Content-Type is an S3 object attribute; other stores do not support attributes
    with_attrs = isinstance(store, S3Store)
    counts = {"uploaded": 0, "skipped": 0, "bytes": 0}
    for o in objs:
        if not overwrite:
            try:
                head = obstore.head(store, o.key)
                if head["size"] == o.size:
                    counts["skipped"] += 1
                    continue
                logger.warning(
                    "%s exists with a different size (%s != %s); use --overwrite",
                    o.key,
                    head["size"],
                    o.size,
                )
                counts["skipped"] += 1
                continue
            except FileNotFoundError:
                pass
        obstore.put(
            store,
            o.key,
            Path(pio.resolve(o.path))
            if o.size > 8 * 1024 * 1024
            else pio.read_bytes(o.path),
            **({"attributes": {"Content-Type": o.content_type}} if with_attrs else {}),
        )
        counts["uploaded"] += 1
        counts["bytes"] += o.size
        logger.info("put %s (%s, %s)", o.key, _human(o.size), o.content_type)
    return counts


def verify(base_url: str | None = None, read_parquet: bool = True) -> dict[str, Any]:
    """Read the published catalog over HTTPS, validate every object, HEAD every asset.

    Also reads one GeoParquet asset over HTTP (DuckDB, falling back to a plain download read
    with pyarrow). Returns a summary with ``ok`` and the problems found.
    """
    import pystac
    import requests

    base = (base_url or config()["https_base"]).rstrip("/")
    problems: list[str] = []
    cat = pystac.Catalog.from_file(f"{base}/catalog.json")
    try:
        cat.validate()
    except Exception as exc:  # noqa: BLE001 - collected into the report
        problems.append(f"catalog: {str(exc).splitlines()[0][:200]}")
    colls = list(cat.get_children())
    for c in colls:
        try:
            c.validate()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{c.id}: {str(exc).splitlines()[0][:200]}")
    items = list(cat.get_items(recursive=True))
    heads = 0
    parquet_assets: list[tuple[int, str]] = []
    for it in items:
        try:
            it.validate()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{it.id}: {str(exc).splitlines()[0][:200]}")
        for key, a in it.assets.items():
            href = a.get_absolute_href() or a.href
            heads += 1
            try:
                r = requests.head(href, allow_redirects=True, timeout=30)
                if r.status_code != 200:
                    problems.append(f"{it.id}/{key}: HEAD {href} -> {r.status_code}")
            except requests.RequestException as exc:
                problems.append(f"{it.id}/{key}: HEAD {href} -> {exc}")
            if a.media_type == PARQUET:
                parquet_assets.append(
                    (int(it.properties.get("table:row_count") or 0), href)
                )
    parquet_check = None
    if read_parquet and parquet_assets:
        rows, href = min(parquet_assets)
        parquet_check = {"href": href, "expected_rows": rows}
        try:
            parquet_check["rows"] = _remote_row_count(href)
            if rows and parquet_check["rows"] != rows:
                problems.append(
                    f"{href}: {parquet_check['rows']} rows, STAC says {rows}"
                )
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{href}: parquet read failed: {exc}")
    return {
        "catalog": f"{base}/catalog.json",
        "collections": len(colls),
        "items": len(items),
        "assets_checked": heads,
        "parquet": parquet_check,
        "problems": problems,
        "ok": not problems,
    }


def _remote_row_count(href: str) -> int:
    """Row count of a remote parquet file (DuckDB httpfs; pyarrow on a download as fallback)."""
    try:
        import duckdb

        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs;")
        return int(
            con.execute("SELECT count(*) FROM read_parquet(?)", [href]).fetchone()[0]
        )  # type: ignore[index]
    except Exception:  # noqa: BLE001 - fall back to a plain HTTP read
        from io import BytesIO

        import pyarrow.parquet as pq
        import requests

        r = requests.get(href, timeout=300)
        r.raise_for_status()
        return pq.ParquetFile(BytesIO(r.content)).metadata.num_rows
