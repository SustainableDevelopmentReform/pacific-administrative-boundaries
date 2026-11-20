"""Provenance step records (spec section 11).

Each CLI stage appends a step record to ``data/processed/<ISO3>/provenance.json`` (or the
product's own provenance file) with inputs, outputs, completion time, software versions and
the git commit, so the chain raw manifest -> register -> per-country item -> combined item is
reconstructable.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import UTC, datetime
from functools import cache
from typing import Any

from pab import __version__
from pab import io as pio


@cache
def git_commit() -> str | None:
    """Current git commit of the repository (None if unavailable or no commits yet)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=pio.ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = out.stdout.strip()
    return commit if out.returncode == 0 and commit else None


@cache
def software_versions() -> dict[str, str]:
    """Versions of the pipeline and its key geospatial dependencies."""
    import geopandas
    import pyarrow
    import pyogrio
    import pyproj
    import pystac
    import shapely

    return {
        "pab": __version__,
        "python": platform.python_version(),
        "geopandas": geopandas.__version__,
        "shapely": shapely.__version__,
        "pyogrio": pyogrio.__version__,
        "gdal": pyogrio.__gdal_version_string__,
        "pyproj": pyproj.__version__,
        "proj": pyproj.proj_version_str,
        "pyarrow": pyarrow.__version__,
        "pystac": pystac.__version__,
    }


def step_record(
    label: str, inputs: dict[str, Any], outputs: dict[str, Any], **extra: object
) -> dict[str, Any]:
    """Build a provenance step record."""
    return {
        "label": label,
        "command": " ".join(["pab", *sys.argv[1:]])
        if sys.argv and sys.argv[0].endswith("pab")
        else None,
        "inputs": inputs,
        "outputs": outputs,
        "completed_at": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "software": software_versions(),
        "git_commit": git_commit(),
        **extra,
    }


def append_step(path: str, record: dict[str, Any], replace_label: bool = True) -> None:
    """Append ``record`` to the provenance file at ``path``.

    With ``replace_label`` (default), earlier records with the same label are dropped so
    re-running a stage keeps one record per stage (idempotent re-runs).
    """
    doc: dict[str, Any] = pio.read_json(path) if pio.exists(path) else {"steps": []}
    steps = [
        s
        for s in doc.get("steps", [])
        if not (replace_label and s.get("label") == record["label"])
    ]
    steps.append(record)
    doc["steps"] = steps
    pio.write_json(path, doc)
