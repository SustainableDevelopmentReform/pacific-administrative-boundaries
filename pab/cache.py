"""Re-download a source from its register entry and write/verify its manifest (spec section 6).

Downloads go to a temporary directory first (OneDrive truncation, rulings D-011/D-012):
the HTTP Content-Length is checked, archives are tested and extracted, sha256 is computed,
and only then are files moved into ``data/raw/<ISO3>/<source_id>/``. Archive members are
extracted with path checks; nothing from the download is ever executed.

Authenticated sources: a register entry may declare
``auth: {type: header, name: Authorization, value_env: LINZ_API_KEY, prefix: "key "}``; URLs on
``data.linz.govt.nz`` get that LINZ default even without it. The secret is read from the
environment (or a local ``.env`` file) at request time and is never logged or written to a
manifest; a missing variable fails with a clear message.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

from pab import io as pio
from pab import registry

logger = logging.getLogger(__name__)
CHUNK = 1 << 20
LINZ_HOST = "data.linz.govt.nz"
#: header auth used for LINZ Data Service URLs when the register declares none
LINZ_AUTH = {
    "type": "header",
    "name": "Authorization",
    "value_env": "LINZ_API_KEY",
    "prefix": "key ",
}


def _dotenv() -> dict[str, str]:
    """``KEY=VALUE`` pairs from the repository's ``.env`` (absent file: empty)."""
    path = Path(pio.ROOT) / ".env"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def auth_config(source: dict[str, Any], url: str) -> dict[str, Any] | None:
    """The auth block for a download URL: the register's ``auth``, else LINZ's default."""
    if source.get("auth"):
        return source["auth"]
    if urlparse(url).hostname == LINZ_HOST:
        return LINZ_AUTH
    return None


def auth_headers(source: dict[str, Any], url: str) -> dict[str, str]:
    """HTTP headers carrying the secret for ``url`` (empty when no auth applies).

    The value comes from the environment variable named by ``value_env`` (or ``.env``);
    it is never logged. Raises ``RuntimeError`` naming the variable when it is missing.
    """
    cfg = auth_config(source, url)
    if not cfg:
        return {}
    if cfg.get("type", "header") != "header":
        raise ValueError(
            f"{source.get('source_id')}: unsupported auth type {cfg.get('type')!r}"
        )
    var = cfg["value_env"]
    value = os.environ.get(var) or _dotenv().get(var)
    if not value:
        raise RuntimeError(
            f"{source.get('source_id')}: {urlparse(url).hostname} needs an API key in the "
            f"environment variable {var} (export it or add `{var}=...` to .env)"
        )
    return {cfg.get("name", "Authorization"): f"{cfg.get('prefix', '')}{value}"}


def _file_name(url: str) -> str:
    """Local file name for a URL; WFS GetFeature URLs are named after their feature type."""
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name or "download"
    if "." not in name:
        q = {k.lower(): v[0] for k, v in parse_qs(parsed.query).items()}
        layer = q.get("typenames") or q.get("typename")
        if layer:
            fmt = q.get("outputformat", "").lower()
            ext = "geojson" if "json" in fmt else "zip" if "zip" in fmt else "gml"
            name = f"{layer.split(':')[-1]}.{ext}"
    return name


def sha256(path: Path) -> str:
    """sha256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _download(
    url: str, folder: Path, headers: dict[str, str] | None = None
) -> tuple[Path, dict[str, Any]]:
    target = folder / _file_name(url)
    with requests.get(
        url,
        stream=True,
        timeout=120,
        headers={"User-Agent": "pab-cache/0.1", **(headers or {})},
    ) as r:
        r.raise_for_status()
        expected = int(r.headers.get("Content-Length", 0) or 0)
        with target.open("wb") as fh:
            for block in r.iter_content(CHUNK):
                fh.write(block)
        info = {"status": r.status_code, "content_type": r.headers.get("Content-Type")}
    size = target.stat().st_size
    if expected and size != expected:
        raise OSError(f"{url}: got {size} bytes, Content-Length {expected}")
    return target, info


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> list[Path]:
    out = []
    root = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(root)):
            raise OSError(f"unsafe path in archive: {member.filename}")
        if member.is_dir():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        out.append(target)
    return out


def cache_source(iso3: str, source_id: str, overwrite: bool = False) -> str:
    """Download one source into data/raw and write its manifest. Returns the manifest path."""
    reg = registry.load_register(iso3)
    src = next(s for s in reg["sources"] if s["source_id"] == source_id)
    raw = src.get("raw_path") or f"data/raw/{iso3}/{source_id}/"
    manifest = f"{raw.rstrip('/')}/manifest.json"
    if pio.exists(manifest) and not overwrite:
        logger.info("%s exists; use --overwrite to re-download", manifest)
        return manifest
    urls = [
        u
        for u in src.get("download_urls") or []
        if u.startswith("http") and "<" not in u
    ]
    if not urls:
        raise ValueError(
            f"{source_id}: no direct download URLs (retrieval_method={src.get('retrieval_method')})"
        )
    dest = Path(pio.resolve(raw))
    files, extracted = [], []
    with tempfile.TemporaryDirectory(prefix="pab-cache-") as tmp:
        stage = Path(tmp)
        for url in urls:
            path, info = _download(url, stage, auth_headers(src, url))
            files.append(
                {
                    "path": path.name,
                    "url": url,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                    **info,
                }
            )
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as zf:
                    bad = zf.testzip()
                    if bad:
                        raise OSError(f"{url}: corrupt member {bad}")
                    sub = stage / path.stem
                    for p in _safe_extract(zf, sub):
                        extracted.append(
                            {
                                "path": str(p.relative_to(stage)),
                                "bytes": p.stat().st_size,
                                "sha256": sha256(p),
                            }
                        )
        dest.mkdir(parents=True, exist_ok=True)
        for p in stage.rglob("*"):
            if p.is_file():
                t = dest / p.relative_to(stage)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, t)
                if sha256(t) != sha256(p):
                    raise OSError(f"copy verification failed for {t}")
    pio.write_json(
        manifest,
        {
            "source_id": source_id,
            "iso3": iso3,
            "retrieved_at": datetime.now(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "retrieved_by": "pab cache",
            "retrieval_method": src.get("retrieval_method"),
            "landing_url": src.get("landing_url"),
            "download_urls": urls,
            **(
                {
                    "auth": "HTTP header {name}: {prefix}<{value_env}> (value from the "
                    "environment, never recorded)".format(**{**LINZ_AUTH, **cfg})
                }
                if (cfg := auth_config(src, urls[0]))
                else {}
            ),
            "license": {k: src["license"].get(k) for k in ("name", "url")},
            "files": files,
            "extracted_files": extracted,
            "notes": "",
        },
    )
    return manifest


def verify_manifest(manifest_path: str) -> list[str]:
    """Check sizes and sha256 of every file listed in a manifest. Returns problems found."""
    man = pio.read_json(manifest_path)
    base = Path(pio.resolve(manifest_path)).parent
    problems = []
    for entry in [*man.get("files", []), *man.get("extracted_files", [])]:
        p = base / entry["path"]
        if not p.exists():
            problems.append(f"missing {entry['path']}")
            continue
        if entry.get("bytes") is not None and p.stat().st_size != entry["bytes"]:
            problems.append(f"size mismatch {entry['path']}")
        elif entry.get("sha256") and sha256(p) != entry["sha256"]:
            problems.append(f"sha256 mismatch {entry['path']}")
    return problems
