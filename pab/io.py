"""Path helpers: one place that understands local paths and ``s3://`` URLs (via obstore).

Everything in the pipeline addresses files by a *URL-like string* relative to a project root.
Local paths are used today; the same relative layout is mirrored to S3 later, so
``s3://bucket/prefix/data/processed/FJI/fji_admin.parquet`` == ``data/processed/FJI/fji_admin.parquet``.
"""

from __future__ import annotations

import itertools
import json
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import geopandas as gpd
from obstore.store import ObjectStore, from_url

#: Repository root (the directory holding ``pyproject.toml``). Overridable for tests / S3 runs.
ROOT = os.environ.get("PAB_ROOT", str(Path(__file__).resolve().parent.parent))


def resolve(path: str) -> str:
    """Return an absolute local path or an ``s3://`` URL for a project-relative ``path``."""
    if path.startswith(("s3://", "http://", "https://", "file://")) or os.path.isabs(
        path
    ):
        return path
    if ROOT.startswith("s3://"):
        return f"{ROOT.rstrip('/')}/{path}"
    return str(Path(ROOT) / path)


def is_remote(path: str) -> bool:
    """True for object-store URLs."""
    return resolve(path).startswith(("s3://", "http://", "https://"))


def _split(url: str) -> tuple[ObjectStore, str]:
    """Split a URL into (store rooted at its parent, file name)."""
    parent, _, name = url.rstrip("/").rpartition("/")
    if url.startswith(("s3://", "http://", "https://")):
        return from_url(parent), name
    Path(parent).mkdir(parents=True, exist_ok=True)
    return from_url(f"file://{os.path.abspath(parent)}"), name


def exists(path: str) -> bool:
    """Whether a file exists (local or remote)."""
    url = resolve(path)
    if not is_remote(url):
        return Path(url).exists()
    store, name = _split(url)
    try:
        store.head(name)
    except FileNotFoundError:
        return False
    return True


def read_bytes(path: str) -> bytes:
    """Read a whole file."""
    url = resolve(path)
    if not is_remote(url):
        return Path(url).read_bytes()
    store, name = _split(url)
    return bytes(store.get(name).bytes())


def write_bytes(path: str, data: bytes) -> None:
    """Write a whole file atomically (local: temp file + rename)."""
    url = resolve(path)
    if not is_remote(url):
        target = Path(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
        return
    store, name = _split(url)
    store.put(name, data)


def read_json(path: str) -> Any:  # noqa: ANN401 - arbitrary JSON
    """Read a JSON document."""
    return json.loads(read_bytes(path))


def write_json(path: str, data: object) -> None:
    """Write a JSON document (UTF-8, indented, stable key order as given)."""
    write_bytes(
        path,
        (json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n").encode(
            "utf-8"
        ),
    )


def write_text(path: str, text: str) -> None:
    """Write a UTF-8 text file."""
    write_bytes(path, text.encode("utf-8"))


ROW_GROUP_ROWS = 5000  # ruling D-016


def write_geoparquet(
    gdf: gpd.GeoDataFrame,
    path: str,
    partition_col: str = "iso3",
    max_rows: int = ROW_GROUP_ROWS,
) -> None:
    """Write GeoParquet 1.1 (WKB, bbox covering column, zstd) with prunable row groups.

    Rows must already be sorted so ``partition_col`` values are contiguous; row groups never
    span two values of ``partition_col`` and hold at most ``max_rows`` rows, so readers can
    prune by country via row-group statistics.
    """
    import pyarrow.parquet as pq

    staged = BytesIO()
    gdf.to_parquet(
        staged,
        compression="zstd",
        write_covering_bbox=True,
        schema_version="1.1.0",
        index=False,
    )
    staged.seek(0)
    table = pq.read_table(staged)
    keys = gdf[partition_col].to_numpy() if partition_col in gdf.columns else None
    if (
        keys is not None
        and len(keys)
        and len(set(keys))
        != sum(1 for i in range(len(keys)) if i == 0 or keys[i] != keys[i - 1])
    ):
        raise ValueError(
            f"rows are not grouped by {partition_col}; sort before writing"
        )
    out = BytesIO()
    with pq.ParquetWriter(
        out, table.schema, compression="zstd", write_statistics=True
    ) as writer:
        if keys is None or not len(keys):
            writer.write_table(table, row_group_size=max_rows)
        else:
            starts = [
                0,
                *[i for i in range(1, len(keys)) if keys[i] != keys[i - 1]],
                len(keys),
            ]
            for a, b in itertools.pairwise(starts):
                writer.write_table(table.slice(a, b - a), row_group_size=max_rows)
    write_bytes(path, out.getvalue())


def read_geoparquet(path: str) -> gpd.GeoDataFrame:
    """Read a GeoParquet file written by :func:`write_geoparquet` (drops the bbox column)."""
    gdf = gpd.read_parquet(BytesIO(read_bytes(path)))
    return gdf.drop(columns=["bbox"], errors="ignore")


def gdal_path(path: str) -> str:
    """Path usable by GDAL/pyogrio (``/vsis3/`` for S3)."""
    url = resolve(path)
    if url.startswith("s3://"):
        return "/vsis3/" + url[len("s3://") :]
    return url
