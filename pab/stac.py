"""STAC 1.1.0 metadata (spec section 10, decisions D-021/D-022).

One Item beside each GeoParquet file (``<name>.stac-item.json``), plus the
``pacific-admin-boundaries`` Collection (``data/collection.json``) under the root Catalog
(``data/catalog.json``). ``data/`` is the published root: it maps to the S3 prefix root.

The tree is a *relative published catalog*: every link is relative except the root Catalog's
``self`` link, which is absolute (``https_base`` from config/publish.yml, or ``--base-url``).
Asset hrefs are relative by default (local use); with a base URL they become absolute HTTPS
URLs with an ``s3://`` alternate (Alternate Assets extension), and raw-manifest assets point to
the GitHub repository (``data/raw`` is never mirrored to S3).
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from functools import cache
from typing import Any

import geopandas as gpd
import numpy as np
import pystac
from shapely.geometry import box, mapping

from pab import __version__, licenses, registry
from pab import io as pio
from pab import publish as pub
from pab.provenance import git_commit

PRODUCT_VERSION = "v0.1.0"
EXTENSIONS = [
    "https://stac-extensions.github.io/projection/v2.0.0/schema.json",
    "https://stac-extensions.github.io/table/v1.2.0/schema.json",
    "https://stac-extensions.github.io/version/v1.2.0/schema.json",
    "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
    "https://stac-extensions.github.io/processing/v1.2.0/schema.json",
]
ALTERNATE_EXT = "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json"
PARQUET = pub.PARQUET
COLLECTION_ID = "pacific-admin-boundaries"
STAC_ROOT = pub.STAC_ROOT
CATALOG_PATH = f"{STAC_ROOT}/catalog.json"
COLLECTION_PATH = f"{STAC_ROOT}/collection.json"
SOURCES_DOC = "docs/sources.md"
#: licence values that are SPDX ids (or have one) and may go in the STAC ``license`` field
SPDX = {
    "CC-BY-4.0": "CC-BY-4.0",
    "CC-BY-3.0-IGO": "CC-BY-3.0-IGO",
    "CC-BY-SA-3.0": "CC-BY-SA-3.0",
    "ODbL-1.0": "ODbL-1.0",
    "CC-BY-NC-SA-4.0": "CC-BY-NC-SA-4.0",
    "LO-2.0": "etalab-2.0",
}
#: every item must carry these (``pab stac --check``)
REQUIRED_PROPS = (
    "pab:iso3",
    "pab:levels",
    "pab:source_ids",
    "description",
    "providers",
    "sci:citation",
    "processing:software",
    "version",
    "created",
    "updated",
    "pab:licenses",
)


def item_path(parquet_path: str) -> str:
    """``<name>.stac-item.json`` beside the parquet file."""
    return parquet_path[: -len(".parquet")] + ".stac-item.json"


def pacific_bbox(gdf: gpd.GeoDataFrame) -> list[float]:
    """Bounding box; west > east when the data straddle the antimeridian (STAC/GeoJSON rule)."""
    b = gdf.geometry.bounds
    west, south, east, north = (
        float(b.minx.min()),
        float(b.miny.min()),
        float(b.maxx.max()),
        float(b.maxy.max()),
    )
    if west < -170 and east > 170:
        lons = np.concatenate([b.minx.to_numpy(), b.maxx.to_numpy()])
        shifted = np.where(lons < 0, lons + 360, lons)
        if shifted.max() - shifted.min() < east - west:
            w = float(np.where(b.minx < 0, b.minx + 360, b.minx).min())
            e = float(np.where(b.maxx < 0, b.maxx + 360, b.maxx).max())
            west, east = (w - 360 if w > 180 else w), (e - 360 if e > 180 else e)
    return [round(west, 6), round(south, 6), round(east, 6), round(north, 6)]


def bbox_geometry(bb: list[float]) -> dict[str, Any]:
    """GeoJSON geometry for a bbox (MultiPolygon split at 180 when west > east)."""
    w, s, e, n = bb
    if w > e:
        return {
            "type": "MultiPolygon",
            "coordinates": [
                mapping(box(w, s, 180, n))["coordinates"],
                mapping(box(-180, s, e, n))["coordinates"],
            ],
        }
    return mapping(box(w, s, e, n))


def _columns(path: str) -> list[dict[str, str]]:
    import pyarrow.parquet as pq

    if pio.is_remote(path):
        return []
    return [
        {"name": f.name, "type": str(f.type)}
        for f in pq.read_schema(pio.gdal_path(path))
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------------------------
# sources, licences, providers


@cache
def _all_sources() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for iso3 in [*registry.all_iso3(), "EEZ"]:
        if pio.exists(f"config/sources/{iso3}.yml"):
            for s in registry.load_register(iso3)["sources"]:
                out[s["source_id"]] = s
    return out


def _sources(ids: list[str]) -> dict[str, dict[str, Any]]:
    allsrc = _all_sources()
    return {i: allsrc[i] for i in ids if i in allsrc}


def _citations(ids: list[str]) -> list[str]:
    out = []
    for sid, s in _sources(ids).items():
        year = str(s.get("publication_date") or "")[:4]
        out.append(
            f"{s.get('publisher', sid)} ({year or 'n.d.'}). {s.get('title', sid)}. {s.get('landing_url', '')}".strip()
        )
    return out


def _source_ids(gdf: gpd.GeoDataFrame) -> list[str]:
    if "source_id" in gdf:
        return sorted(set(gdf["source_id"].dropna()))
    if "source_ids" in gdf:
        return sorted({s for v in gdf["source_ids"].dropna() for s in v.split(";")})
    return []


def _split(values: Any, sep: str = ";") -> list[str]:  # noqa: ANN401 - Series or list
    """Distinct values of a column whose cells may join several values with ``sep``."""
    out: list[str] = []
    for v in values:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        out.extend(x for x in str(v).split(sep) if x and x not in out)
    return out


def licence_summary(gdf: gpd.GeoDataFrame) -> list[dict[str, str | None]]:
    """Distinct (license, license_url) pairs in a table, in first-seen order."""
    if "license" not in gdf:
        return []
    if "license_url" in gdf:
        pairs = dict.fromkeys(
            zip(
                gdf["license"],
                gdf["license_url"].where(gdf["license_url"].notna(), None),
                strict=True,
            )
        )
        return [{"license": lic, "url": url} for lic, url in pairs]
    return [
        {"license": lic, "url": licenses.CANONICAL.get(lic)}
        for lic in _split(gdf["license"])
    ]


def register_licences(ids: list[str]) -> list[dict[str, str | None]]:
    """Source-level licences from the registers (for tables without licence columns)."""
    out: dict[tuple[str, str | None], None] = {}
    for s in _sources(ids).values():
        try:
            out[licenses.resolve(s)] = None
        except ValueError:  # composite source licence: per-level overrides apply
            for lvl in s.get("levels") or []:
                if lvl.get("license"):
                    out[licenses.resolve(s, lvl)] = None
    return [{"license": lic, "url": url} for lic, url in out]


def stac_license(values: list[str]) -> str:
    """STAC ``license``: the SPDX id when the table has a single SPDX licence, else ``other``."""
    return SPDX.get(values[0], "other") if len(values) == 1 else "other"


def project_providers() -> list[dict[str, Any]]:
    """Producer/processor (this project, linked to the GitHub repository) and host (S3)."""
    cfg = pub.config()
    return [
        {
            "name": cfg["project_name"],
            "description": "Harmonised the source boundaries; code, documentation and full "
            "provenance in the GitHub repository.",
            "roles": ["producer", "processor"],
            "url": cfg["repo_url"],
        },
        {
            "name": "Amazon Web Services (S3)",
            "description": f"Public bucket {pub.s3_root(cfg)}/",
            "roles": ["host"],
            "url": cfg["https_base"],
        },
    ]


def source_providers(ids: list[str]) -> list[dict[str, Any]]:
    """One provider per source publisher (licensor + producer), linked to a landing page."""
    out: dict[str, dict[str, Any]] = {}
    for sid, s in _sources(ids).items():
        name = s.get("publisher") or sid
        p = out.setdefault(
            name,
            {
                "name": name,
                "roles": ["licensor", "producer"],
                "url": s.get("landing_url"),
            },
        )
        p.setdefault("pab:source_ids", []).append(sid)
    return [
        {k: v for k, v in p.items() if v is not None and not k.startswith("pab:")}
        for p in out.values()
    ]


@cache
def _doc_anchors() -> dict[str, str]:
    """GitHub heading anchors of docs/sources.md keyed by ISO3 / ``EEZ`` / ``Summary``."""
    if not pio.exists(SOURCES_DOC):
        return {}
    out = {}
    for line in pio.read_bytes(SOURCES_DOC).decode("utf-8").splitlines():
        m = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if not m:
            continue
        heading = m[1]
        key = heading.split(":")[0].strip()
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        out.setdefault(key, slug)
    return out


def sources_doc_url(key: str) -> str:
    """GitHub URL of the docs/sources.md section for ``key`` (ISO3, ``EEZ`` or ``Summary``)."""
    return pub.github_blob(SOURCES_DOC, _doc_anchors().get(key))


def describe_sources(ids: list[str], limit: int = 6) -> str:
    """Human-readable sentence naming the sources of a table."""
    srcs = _sources(ids)
    if not srcs:
        return ""
    if len(srcs) <= limit:
        named = "; ".join(
            f'{s.get("publisher", sid)}, "{s.get("title", sid)}" ({sid})'
            for sid, s in srcs.items()
        )
        return f"Sources: {named}."
    pubs = list(dict.fromkeys(s.get("publisher", sid) for sid, s in srcs.items()))
    return (
        f"Built from {len(srcs)} sources (listed in pab:source_ids, with citations in "
        f"sci:citation) published by: {'; '.join(pubs)}."
    )


def describe_licences(lics: list[dict[str, Any]], agreements: list[str]) -> str:
    """Sentence on licences and data-use agreements (D-019/D-020)."""
    names = ", ".join(dict.fromkeys(str(x["license"]) for x in lics))
    text = f" Licences (per row in the `license` column): {names}." if names else ""
    if agreements:
        text += (
            " Some rows are used and redistributed by this project under a data-use agreement "
            f"({'; '.join(agreements)}); downstream users are bound by the row's public "
            "licence (e.g. CC BY-NC-SA 4.0) unless they hold their own agreement."
        )
    return text


# --------------------------------------------------------------------------------------------
# items


def make_item(
    item_id: str,
    parquet_path: str,
    gdf: gpd.GeoDataFrame,
    title: str,
    description: str,
    extra_props: dict[str, Any] | None = None,
    docs_key: str = "Summary",
) -> pystac.Item:
    """Build a STAC Item for a GeoParquet product (asset hrefs are absolute local paths here;
    :func:`write_item` makes them relative or published URLs)."""
    bb = pacific_bbox(gdf)
    dates = [
        d
        for d in gdf.get("source_date", [])
        if d is not None and not (isinstance(d, float) and np.isnan(d))
    ]
    start = min(dates) if dates else None
    end = max(dates) if dates else None
    source_ids = _source_ids(gdf)
    lics = licence_summary(gdf) or register_licences(source_ids)
    agreements = (
        _split(gdf["license_agreement"], " | ") if "license_agreement" in gdf else []
    )
    lic_values = list(dict.fromkeys(str(x["license"]) for x in lics))
    commit = git_commit()
    software = {"pab": __version__}
    if commit:
        software["pab-git-commit"] = commit
    now = _now()
    props: dict[str, Any] = {
        "title": title,
        "description": " ".join(
            t
            for t in (
                description,
                describe_sources(source_ids),
                describe_licences(lics, agreements).strip(),
                (f"Full provenance and source notes: {sources_doc_url(docs_key)}."),
            )
            if t
        ),
        "start_datetime": f"{start}T00:00:00Z" if start else None,
        "end_datetime": f"{end}T00:00:00Z" if end else None,
        "created": now,
        "updated": now,
        "providers": [*source_providers(source_ids), *project_providers()],
        "license": stac_license(lic_values),
        "proj:code": "EPSG:4326",
        "proj:bbox": bb,
        "table:columns": _columns(parquet_path),
        "table:row_count": len(gdf),
        "table:primary_geometry": "geometry",
        "version": PRODUCT_VERSION,
        "processing:software": software,
        "processing:lineage": "raw manifest -> config/sources register -> pab process/combine",
        "processing:datetime": now,
        "pab:levels": sorted(set(gdf["level_code"]))
        if "level_code" in gdf
        else sorted(set(gdf.get("finest_level_code", []))),
        "pab:source_ids": source_ids,
        "pab:licenses": lic_values,
        "pab:license_agreements": agreements,
        **(extra_props or {}),
    }
    citations = _citations(source_ids)
    if citations:
        props["sci:citation"] = "; ".join(citations)
    props = {k: v for k, v in props.items() if v is not None}
    props["pab:git_commit"] = commit  # always present; null before the first commit
    item = pystac.Item(
        id=item_id,
        geometry=bbox_geometry(bb),
        bbox=bb,
        datetime=None if start else datetime.now(UTC),
        properties=props,
        stac_extensions=list(EXTENSIONS),
    )
    item.set_self_href(pio.resolve(item_path(parquet_path)))
    item.add_asset(
        "data",
        pystac.Asset(
            href=pio.resolve(parquet_path),
            media_type=PARQUET,
            roles=["data"],
            title=title,
        ),
    )
    prov = f"{os.path.dirname(parquet_path)}/provenance.json"
    if pio.exists(prov):
        item.add_asset(
            "provenance",
            pystac.Asset(
                href=pio.resolve(prov),
                media_type="application/json",
                roles=["metadata"],
                title="Processing provenance (step records)",
            ),
        )
    item.add_link(
        pystac.Link(
            rel="about",
            target=sources_doc_url(docs_key),
            media_type="text/html",
            title="Sources, licences and processing notes (GitHub)",
        )
    )
    for sid, src in _sources(source_ids).items():
        if src.get("raw_path"):
            man = f"{src['raw_path'].rstrip('/')}/manifest.json"
            if pio.exists(man):
                item.add_asset(
                    f"manifest-{sid}",
                    pystac.Asset(
                        href=pio.resolve(man),
                        media_type="application/json",
                        roles=["metadata"],
                        title=f"Raw download manifest {sid} (checksums, retrieval date)",
                    ),
                )
        if src.get("landing_url"):
            item.add_link(
                pystac.Link(
                    rel="via",
                    target=src["landing_url"],
                    media_type="text/html",
                    title=f"Source: {src.get('title', sid)}",
                )
            )
    for lic in lics:
        if lic.get("url"):
            item.add_link(
                pystac.Link(
                    rel="license",
                    target=str(lic["url"]),
                    title=str(lic["license"]),
                )
            )
    return item


def _published_href(path: str, base_url: str | None) -> str:
    return f"{base_url.rstrip('/')}/{pub.published_key(path)}" if base_url else path


def write_item(item: pystac.Item, base_url: str | None = None) -> dict[str, Any]:
    """Write an item beside its parquet file; return the written dict.

    Links to the collection/root are relative. Asset hrefs are relative unless ``base_url``
    is given: then files below ``data/`` get absolute HTTPS hrefs plus an ``s3://`` alternate
    and raw manifests point to the GitHub repository. ``created`` is kept from an existing file.
    """
    here = item.get_self_href()
    base = os.path.dirname(here)
    d = item.to_dict(include_self_link=False, transform_hrefs=False)
    for a in d["assets"].values():
        href = a["href"]
        if href.startswith(("http://", "https://", "s3://")):
            continue
        rel = pub.project_path(href)
        if not base_url:
            a["href"] = os.path.relpath(href, base)
        elif rel.startswith("data/raw/"):
            a["href"] = pub.github_raw(rel)
        else:
            a["href"] = _published_href(rel, base_url)
            a["alternate"] = {
                "s3": {
                    "href": f"{pub.s3_root()}/{pub.published_key(rel)}",
                    "alternate:name": "S3",
                }
            }
    if base_url and ALTERNATE_EXT not in d["stac_extensions"]:
        d["stac_extensions"].append(ALTERNATE_EXT)
    d["collection"] = COLLECTION_ID
    coll = os.path.relpath(pio.resolve(COLLECTION_PATH), base)
    root = os.path.relpath(pio.resolve(CATALOG_PATH), base)
    d["links"] = [
        lk for lk in d["links"] if lk["rel"] not in ("collection", "root", "parent")
    ] + [
        {"rel": "collection", "href": coll, "type": "application/json"},
        {"rel": "parent", "href": coll, "type": "application/json"},
        {"rel": "root", "href": root, "type": "application/json"},
    ]
    if pio.exists(here):
        try:
            old = pio.read_json(here).get("properties", {})
            if old.get("created"):
                d["properties"]["created"] = old["created"]
        except ValueError:
            pass
    pio.write_json(here, d)
    return d


def write_country_item(
    iso3: str, gdf: gpd.GeoDataFrame, base_url: str | None = None
) -> dict[str, Any]:
    """Item for data/processed/<ISO3>/<iso3>_admin.parquet."""
    from pab import process

    meta = registry.country_meta(iso3)
    path = process.admin_path(iso3)
    extra: dict[str, Any] = {"pab:iso3": iso3}
    rpath = process.restricted_path(iso3)
    if pio.exists(rpath):
        import pyarrow.parquet as pq

        rmeta = (
            pq.read_table(pio.gdal_path(rpath), columns=["source_id"])
            .column("source_id")
            .to_pylist()
        )
        extra["pab:restricted_rows_file"] = os.path.basename(rpath)
        extra["pab:restricted_rows"] = len(rmeta)
        extra["pab:restricted_source_ids"] = sorted(set(rmeta))
        extra["pab:restricted_note"] = (
            "Rows from sources that may not be redistributed are kept in a local-only companion "
            "file next to this one; it has no STAC item and is not published."
        )
    item = make_item(
        f"pab-{iso3.lower()}-admin",
        path,
        gdf,
        f"{meta['name']} administrative and jurisdictional boundaries (long table)",
        f"All boundary levels for {meta['name']}, from the EEZ to the finest published level, "
        "stacked in one table (one row per unit per level).",
        extra,
        docs_key=iso3,
    )
    return write_item(item, base_url)


# --------------------------------------------------------------------------------------------
# catalog + collection


def _repo_links() -> list[dict[str, Any]]:
    cfg = pub.config()
    return [
        {
            "rel": "about",
            "href": cfg["repo_url"],
            "type": "text/html",
            "title": "GitHub repository: code, documentation, licence and full provenance",
        },
        {
            "rel": "documentation",
            "href": pub.github_blob("docs/usage.md"),
            "type": "text/html",
            "title": "Usage guide",
        },
        {
            "rel": "describedby",
            "href": sources_doc_url("Summary"),
            "type": "text/html",
            "title": "Sources and licences",
        },
    ]


def _licence_links(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for it in items:
        for lk in it["links"]:
            if lk["rel"] == "license" and lk["href"] not in seen:
                seen[lk["href"]] = {
                    "rel": "license",
                    "href": lk["href"],
                    "title": lk.get("title"),
                }
    return list(seen.values())


def write_catalog(
    written: list[tuple[str, dict[str, Any]]], base_url: str | None = None
) -> None:
    """Write data/catalog.json (root, absolute self link) and data/collection.json.

    ``written`` holds (project-relative item path, item dict) pairs.
    """
    cfg = pub.config()
    items = [d for _, d in written]
    self_href = f"{(base_url or cfg['https_base']).rstrip('/')}/catalog.json"
    lic_links = _licence_links(items)
    licence_values = sorted(
        {v for it in items for v in it["properties"].get("pab:licenses", [])}
    )
    agreements = sorted(
        {v for it in items for v in it["properties"].get("pab:license_agreements", [])}
    )
    bbs = [it["bbox"] for it in items]
    starts = [it["properties"].get("start_datetime") for it in items]
    ends = [it["properties"].get("end_datetime") for it in items]
    starts = [s for s in starts if s]
    ends = [e for e in ends if e]
    agreement_note = (
        f" Some sources are redistributed under data-use agreements ({'; '.join(agreements)}); "
        "their rows keep their public licence (e.g. CC BY-NC-SA 4.0), which binds downstream "
        "users unless they hold their own agreement."
        if agreements
        else ""
    )
    coll = pystac.Collection(
        id=COLLECTION_ID,
        title="Pacific administrative boundaries",
        description=(
            "Harmonised administrative and jurisdictional boundaries (EEZ to finest public "
            "level) for 22 Pacific Island countries and territories, as GeoParquet. Each row "
            f"carries its source, licence and dates.{agreement_note} Code, documentation and "
            f"full provenance: {cfg['repo_url']}"
        ),
        extent=pystac.Extent(
            pystac.SpatialExtent(
                [
                    [
                        min(b[0] for b in bbs),
                        min(b[1] for b in bbs),
                        max(b[2] for b in bbs),
                        max(b[3] for b in bbs),
                    ]
                ]
                if bbs
                else [[-180, -90, 180, 90]]
            ),
            pystac.TemporalExtent(
                [
                    [
                        datetime.fromisoformat(min(starts)) if starts else None,
                        datetime.fromisoformat(max(ends)) if ends else None,
                    ]
                ]
            ),
        ),
        license="other",
        providers=[pystac.Provider.from_dict(p) for p in project_providers()],
        summaries=pystac.Summaries(
            {
                "pab:iso3": sorted(
                    {
                        i
                        for it in items
                        for i in (
                            [it["properties"]["pab:iso3"]]
                            if isinstance(it["properties"].get("pab:iso3"), str)
                            else it["properties"].get("pab:iso3", [])
                        )
                    }
                ),
                "level_code": sorted(
                    {
                        lv
                        for it in items
                        for lv in it["properties"].get("pab:levels", [])
                    }
                ),
                "license": licence_values,
                **({"license_agreement": agreements} if agreements else {}),
            }
        ),
        stac_extensions=[
            "https://stac-extensions.github.io/version/v1.2.0/schema.json"
        ],
    )
    coll.extra_fields["version"] = PRODUCT_VERSION
    cd = coll.to_dict(include_self_link=False, transform_hrefs=False)
    coll_dir = os.path.dirname(pio.resolve(COLLECTION_PATH))
    cd["links"] = [
        {"rel": "root", "href": "./catalog.json", "type": "application/json", "title": "Pacific administrative boundaries"},
        {"rel": "parent", "href": "./catalog.json", "type": "application/json", "title": "Pacific administrative boundaries"},
        *[
            {
                "rel": "item",
                "href": "./"
                + os.path.relpath(pio.resolve(path), coll_dir).replace(os.sep, "/"),
                "type": "application/geo+json",
                "title": it["properties"].get("title"),
            }
            for path, it in written
        ],
        *_repo_links(),
        *lic_links,
    ]  # fmt: skip
    pio.write_json(COLLECTION_PATH, cd)
    cat = {
        "type": "Catalog",
        "id": "pab",
        "stac_version": pystac.get_stac_version(),
        "title": "Pacific administrative boundaries",
        "description": (
            "Pacific administrative and jurisdictional boundaries: harmonised GeoParquet for "
            "22 Pacific Island countries and territories. Data on AWS S3; code, documentation "
            f"and provenance on GitHub ({cfg['repo_url']})."
        ),
        "providers": project_providers(),
        "links": [
            {"rel": "self", "href": self_href, "type": "application/json"},
            {"rel": "root", "href": "./catalog.json", "type": "application/json", "title": "Pacific administrative boundaries"},
            {"rel": "child", "href": "./collection.json", "type": "application/json", "title": "Pacific administrative boundaries"},
            *_repo_links(),
            *lic_links,
        ],
    }  # fmt: skip
    pio.write_json(CATALOG_PATH, cat)


def build_catalog(base_url: str | None = None) -> list[dict[str, Any]]:
    """(Re)write every item, data/collection.json and data/catalog.json. Returns the items."""
    from pab import combine, eez, process

    items: list[tuple[str, dict[str, Any]]] = []
    for iso3 in registry.all_iso3():
        p = process.admin_path(iso3)
        if pio.exists(p):
            g = process.load_country(iso3, include_restricted=False)
            items.append((item_path(p), write_country_item(iso3, g, base_url)))
    if eez.eez_available():
        g = eez.load_eez()
        it = make_item(
            "pab-pacific-eez",
            eez.EEZ_PATH,
            g,
            "Pacific EEZ polygons",
            "200 NM Exclusive Economic Zones of the 22 Pacific Island countries and "
            "territories, plus flagged overlapping claims and joint regimes (nests = false). "
            "Boundaries are not legally authoritative.",
            {"pab:iso3": sorted(set(g["iso3"]))},
            docs_key="EEZ",
        )
        items.append((item_path(eez.EEZ_PATH), write_item(it, base_url)))
    for path, iid, title, desc in (
        (
            combine.LONG_PATH,
            "pab-pacific-admin",
            "Pacific administrative boundaries (long table)",
            (
                "Concatenation of the per-country long tables (one row per unit per level), "
                "licence-restricted rows excluded."
            ),
        ),
        (
            combine.FINEST_PATH,
            "pab-pacific-admin-finest",
            "Pacific finest partition",
            (
                "Planar partition of every Pacific Island EEZ into the finest land units "
                "available plus the marine remainder, each row carrying its ancestor units."
            ),
        ),
    ):
        if pio.exists(path):
            g = pio.read_geoparquet(path)
            it = make_item(
                iid, path, g, title, desc, {"pab:iso3": sorted(set(g["iso3"]))}
            )
            items.append((item_path(path), write_item(it, base_url)))
    write_catalog(items, base_url)
    return [d for _, d in items]


# --------------------------------------------------------------------------------------------
# checks


def item_paths() -> list[str]:
    """Project-relative paths of every item linked from data/collection.json."""
    coll = pio.read_json(COLLECTION_PATH)
    return [
        os.path.normpath(os.path.join(STAC_ROOT, lk["href"])).replace(os.sep, "/")
        for lk in coll["links"]
        if lk["rel"] == "item"
    ]


def check_item(d: dict[str, Any]) -> list[str]:
    """Missing provenance fields of one item dict (empty when complete)."""
    p = d.get("properties", {})
    rels = [lk["rel"] for lk in d.get("links", [])]
    missing = [k for k in REQUIRED_PROPS if p.get(k) in (None, "", [])]
    if "pab:git_commit" not in p:
        missing.append("pab:git_commit")
    if "pab" not in (p.get("processing:software") or {}):
        missing.append("processing:software.pab")
    for rel in ("via", "about", "license", "collection", "root"):
        if rel not in rels:
            missing.append(f"link:{rel}")
    if "data" not in d.get("assets", {}):
        missing.append("asset:data")
    srcs = set(p.get("pab:source_ids") or [])
    vias = sum(1 for r in rels if r == "via")
    if srcs and vias < len(_sources(sorted(srcs))):
        missing.append(f"link:via({vias}/{len(srcs)})")
    return missing


def check_root() -> dict[str, list[str]]:
    """Missing fields on the catalog and collection (links to the repo, providers, licences)."""
    out = {}
    for path in (CATALOG_PATH, COLLECTION_PATH):
        d = pio.read_json(path)
        rels = [lk["rel"] for lk in d["links"]]
        miss = [
            r for r in ("about", "documentation", "license", "root") if r not in rels
        ]
        if not d.get("providers"):
            miss.append("providers")
        if path == CATALOG_PATH:
            selfs = [lk["href"] for lk in d["links"] if lk["rel"] == "self"]
            if not selfs or not selfs[0].startswith("https://"):
                miss.append("absolute self link")
        out[path] = miss
    return out


def check_all() -> list[dict[str, Any]]:
    """One row per item: id, counts of sources/levels/providers/links and missing fields."""
    rows = []
    for path in item_paths():
        d = pio.read_json(path)
        p = d["properties"]
        iso = p.get("pab:iso3")
        rows.append(
            {
                "item": d["id"],
                "iso3": iso if isinstance(iso, str) else f"{len(iso or [])} PICTs",
                "levels": len(p.get("pab:levels") or []),
                "sources": len(p.get("pab:source_ids") or []),
                "providers": len(p.get("providers") or []),
                "via": sum(1 for lk in d["links"] if lk["rel"] == "via"),
                "licences": ", ".join(p.get("pab:licenses") or []),
                "agreements": len(p.get("pab:license_agreements") or []),
                "git_commit": (p.get("pab:git_commit") or "null")[:8],
                "missing": check_item(d),
            }
        )
    return rows


def validate_all() -> dict[str, str]:
    """Validate every written STAC object with pystac (fetches extension schemas)."""
    results = {}
    for p in [CATALOG_PATH, COLLECTION_PATH, *item_paths()]:
        try:
            obj = pystac.read_file(pio.resolve(p))
            obj.validate()
            results[p] = "valid"
        except Exception as exc:  # noqa: BLE001 - validation errors are reported, not fatal
            results[p] = f"INVALID: {str(exc).splitlines()[0][:300]}"
    return results
