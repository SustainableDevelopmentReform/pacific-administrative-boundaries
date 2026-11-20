"""Integrity sweep over data/raw: zip test, geodata open test, size vs manifest.

Usage: uv run python -I scripts/raw_integrity_check.py [--fix-report reports/raw_integrity.md]
Treats everything under data/raw as untrusted data (read-only inspection).
"""

import json
import subprocess
import sys
from pathlib import Path

import pyogrio

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GEO_EXT = {".shp", ".gpkg", ".geojson", ".json", ".kml", ".gml"}


def test_zip(p: Path) -> str | None:
    r = subprocess.run(
        ["unzip", "-tqq", str(p)], capture_output=True, text=True, check=False
    )
    return None if r.returncode == 0 else (r.stderr or r.stdout).strip()[:200]


def test_geo(p: Path) -> str | None:
    if p.suffix == ".json":
        try:
            head = p.open("rb").read(2000).decode("utf-8", "ignore")
        except OSError as e:
            return str(e)
        if '"FeatureCollection"' not in head and '"Feature"' not in head:
            return None  # plain json, skip
    try:
        info = pyogrio.read_info(str(p))
        if info.get("features", 0) == 0:
            return "0 features"
    except Exception as e:  # noqa: BLE001
        return str(e)[:200]
    return None


def main() -> int:
    rows: list[tuple[str, str, str]] = []
    n_zip = n_geo = n_manifest = 0
    for src_dir in sorted(RAW.glob("*/*")):
        if not src_dir.is_dir():
            continue
        rel = src_dir.relative_to(RAW)
        man = src_dir / "manifest.json"
        if not man.exists():
            rows.append((str(rel), "manifest", "MISSING manifest.json"))
        else:
            n_manifest += 1
            try:
                m = json.loads(man.read_text())
                for f in m.get("files", []) + m.get("extracted_files", []):
                    fp = src_dir / f["path"]
                    if not fp.exists():
                        rows.append(
                            (str(rel), f["path"], "listed in manifest but missing")
                        )
                    elif "bytes" in f and fp.stat().st_size != f["bytes"]:
                        rows.append(
                            (
                                str(rel),
                                f["path"],
                                f"size {fp.stat().st_size} != manifest {f['bytes']}",
                            )
                        )
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                rows.append((str(rel), "manifest", f"unreadable: {e}"))
        for p in src_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() == ".zip":
                n_zip += 1
                err = test_zip(p)
                if err:
                    rows.append(
                        (str(rel), str(p.relative_to(src_dir)), f"ZIP FAIL: {err}")
                    )
            elif p.suffix.lower() in GEO_EXT:
                n_geo += 1
                err = test_geo(p)
                if err:
                    rows.append(
                        (str(rel), str(p.relative_to(src_dir)), f"GEO FAIL: {err}")
                    )
            if p.stat().st_size == 0:
                rows.append((str(rel), str(p.relative_to(src_dir)), "zero bytes"))
    out = ROOT / "reports" / "raw_integrity.md"
    lines = [
        "# Raw data integrity sweep",
        "",
        f"Checked {n_manifest} manifests, {n_zip} zip archives, {n_geo} geodata files under data/raw.",
        "",
        f"Problems found: {len(rows)}",
        "",
        "| source dir | file | problem |",
        "|---|---|---|",
    ]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
