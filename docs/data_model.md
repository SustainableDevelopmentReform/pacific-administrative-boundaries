# Data model and pipeline specification

This document is the contract that every stage of the pipeline (and every
contributor, human or agent) follows. If a stage needs something not covered
here, add it here first.

## 1. Scope

22 Pacific Island countries and territories (PICTs). See `config/countries.yml`
for the registry (ISO 3166-1 alpha-3 codes are the primary key everywhere).

For each PICT we capture **every publicly available jurisdictional boundary
layer**, from the Exclusive Economic Zone (EEZ) down to the finest level that is
published (wards, villages, enumeration areas where openly licensed).

## 2. Repository layout

```
pacific_administrative_boundaries/
  README.md                 overview, quick start, citation
  LICENSE                   Apache-2.0 for code; data licences are per source
  pyproject.toml            uv/hatchling project, CLI `pab`
  Makefile                  stage targets (cache / process / combine / stac / publish)
  pab/                      python package (typer CLI + library)
  config/
    countries.yml           registry of PICTs (iso3, names, status, sovereign)
    levels.yml              harmonised level vocabulary (section 4)
    sources/<ISO3>.yml      per-country source register (section 5)
    sources/EEZ.yml         EEZ source register
  data/                     published root (maps to s3://<bucket>/<prefix>/)
    catalog.json            STAC root Catalog
    collection.json         STAC Collection linking all items
    raw/<ISO3>/<source_id>/ original downloads, untouched, + manifest.json (never mirrored to S3)
    raw/EEZ/<source_id>/
    processed/<ISO3>/       harmonised per-country GeoParquet + STAC item
    processed/EEZ/
    combined/               pacific-wide GeoParquet + STAC items
  docs/                     published documentation
  scripts/                  one-off helpers (not part of the CLI)
  tests/
  _private/                 local working notes (gitignored, never published)
  reports/                  local build/QA reports (gitignored)
```

`data/` is gitignored except `manifest.json` and STAC/provenance `*.json` files, so the
repository carries full provenance without carrying the bytes. `pab publish` mirrors the
published part of `data/` to AWS S3 (`config/publish.yml`) with the same relative paths below
`data/`, so `s3://<bucket>/<prefix>/processed/FJI/...` == `data/processed/FJI/...`. Nothing
under `data/raw/` is mirrored; the raw manifests are published in the GitHub repository.

## 3. Products

| Product | Path | Description |
|---|---|---|
| Per-country long table | `data/processed/<ISO3>/<iso3>_admin.parquet` | One row per unit per level, all levels stacked (EEZ, admin0 .. adminN, plus non-nesting layers). |
| Restricted companion (local only) | `data/processed/<ISO3>/<iso3>_admin_restricted.parquet` | Same schema; only rows with `license_restricted = true` (currently COK, 42 rows). No STAC item, not published; the country Item notes it in `pab:restricted_rows_file`. `<iso3>_admin.parquet` never holds restricted rows. |
| EEZ | `data/processed/EEZ/pacific_eez.parquet` | EEZ polygons for the 22 PICTs, including joint regimes and overlapping claims, flagged. |
| Pacific long table | `data/combined/pacific_admin.parquet` | Concatenation of all per-country long tables. Group by `level_code` or `level_type` to get any level across the region. |
| Pacific finest partition | `data/combined/pacific_admin_finest.parquet` | Planar partition of every EEZ: each polygon is the finest nesting unit available at that location, carrying the names/codes of all ancestor levels as columns. The marine remainder of each EEZ (EEZ minus land units) is one row with admin columns null and `is_marine = true`. Dissolve on any ancestor column to rebuild that level. |
| STAC | `data/catalog.json`, `data/collection.json`, `data/**/*.stac-item.json` | One STAC Item per GeoParquet file, one Collection, one Catalog (section 10). |

All products: GeoParquet 1.1, WKB geometry, `bbox` covering column, zstd
compression, CRS EPSG:4326, geometry type MultiPolygon (promoted).

## 4. Harmonised levels

Each row in a long table carries three level descriptors:

| Column | Meaning |
|---|---|
| `level_rank` (int) | Position in the nesting hierarchy. 0 = EEZ, 1 = admin0 (country/territory land), 2 = admin1, 3 = admin2, 4 = admin3, 5 = admin4, 6 = admin5. Non-nesting layers use rank 99. |
| `level_code` (str) | `eez`, `admin0`, `admin1`, `admin2`, `admin3`, `admin4`, `admin5`, or `other` for non-nesting layers. |
| `level_type` (str) | Harmonised **category** so users can compare like with like across countries. Vocabulary in `config/levels.yml`: `eez`, `country`, `region`, `state_province`, `district`, `local_government`, `ward_village`, `island`, `statistical`, `electoral`, `customary`. |
| `level_name_local` (str) | What the country calls it: "Province", "Tikina", "Local Level Government", "Commune", "Nu'u", "Kaupule", ... |
| `nests` (bool) | True when the layer is a strict subdivision of the level above it and participates in the finest partition. False for overlapping/non-nesting layers (e.g. municipal councils in Fiji, customary areas in New Caledonia), which are kept in the long tables but excluded from the finest partition. |

Rules:
* `level_rank`/`level_code` are assigned **per country** from the top down, so `admin1` is always the first subdivision below the national boundary even if it is called a State, Province, Division, Region or Island.
* `level_type` is assigned per layer by the processing stage using `config/sources/<ISO3>.yml`; it is the field to use for cross-country comparison ("all local-government units").
* admin0 is the land boundary of the country/territory (derived from the admin1 union when the source does not ship an admin0 layer; recorded in `geometry_method`).

## 5. Source register (`config/sources/<ISO3>.yml`)

Filled in by the retrieval stage, read by the processing stage.

```yaml
iso3: FJI
country_name: Fiji
sources:
  - source_id: fji-fbos-admin-2017        # kebab-case, unique across repo
    title: "Fiji administrative boundaries (Tikina) 2017"
    publisher: "Fiji Bureau of Statistics"
    publisher_type: national | regional_body | un_ocha | academic | osm | commercial | other
    landing_url: https://...
    download_urls:
      - https://...
    retrieval_method: http | api | portal_export | manual   # manual = clicked through a portal; record steps in notes
    license:
      name: CC-BY-4.0            # SPDX id where possible; else free text
      url: https://...
      redistribution_ok: true    # can we republish the derived GeoParquet?
      notes: ""
    publication_date: 2017-06-01  # ISO date of the data (best available)
    version: "v1"
    format: shapefile | geojson | gpkg | kml | pdf | other
    crs: EPSG:4326
    levels:                        # which harmonised levels this source provides
      - level_code: admin1
        level_type: state_province
        level_name_local: Division
        layer: fji_admbnda_adm1   # layer or file inside the raw folder
        name_field: ADM1_EN
        code_field: ADM1_PCODE
        parent_field: ADM0_PCODE
        nests: true
    status: selected | alternative | rejected | reference
    raw_path: data/raw/FJI/fji-fbos-admin-2017/
    notes: ""
decisions:                          # clashes between sources for the same level
  - level_code: admin2
    chosen: fji-fbos-admin-2017
    alternatives: [fji-geoboundaries-adm2]
    reason: "Official national source; more recent."
    escalated: false
```

Optional processing keys (owned by the processing stage): a source-level `land_mask: {layer,
filter}` clips every level of that source to land from one of its own layers
(`clipped_to_land`); a level-level `clip_to: {source_id, layer, filter?, exclude?}` clips that
level to the land of *another* source in the same register (`clipped_to_coastline`; e.g. Niue
census villages clipped to the LINZ outline, D-023). The clip source is read and cached like
any other used source.

Source preference order (highest first); the most recent publication wins
within a tier; ties or unclear cases are escalated to the orchestrator and
recorded in the register's `decisions` block and summarised in `docs/decisions.md`:

1. Official national/territorial agency (statistics office, lands/survey
   department, electoral commission), including copies hosted on SPC Pacific
   Data Hub / PacGeo, with an open licence.
2. UN OCHA Common Operational Datasets (COD-AB on HDX), which are usually
   endorsed national datasets.
3. geoBoundaries (CC BY 4.0).
4. Sovereign-state official sources for territories: US Census TIGER/Line
   (ASM, GUM, MNP); IGN Admin Express / data.gouv.fr (PYF, NCL, WLF);
   Stats NZ / LINZ (COK, NIU, TKL); UK sources (PCN).
5. OpenStreetMap administrative relations (ODbL: share-alike, flag it).
6. GADM 4.1: **reference/fallback only**. Its licence prohibits redistribution
   and commercial use, so GADM-derived rows carry `license_restricted = true`
   and are excluded from the published combined product unless no alternative
   exists (in which case the exclusion is documented).
7. Natural Earth (public domain, coarse) for admin0 only as a last resort.

Every candidate that was seriously considered stays in the register with
`status: alternative` or `rejected` and a reason, and its raw download is kept
when it was downloaded.

## 6. Raw manifest (`data/raw/<ISO3>/<source_id>/manifest.json`)

Written at download time, one per source folder.

```json
{
  "source_id": "fji-fbos-admin-2017",
  "iso3": "FJI",
  "retrieved_at": "2026-11-20T02:15:00Z",
  "retrieved_by": "pab cache | manual",
  "retrieval_method": "http",
  "landing_url": "...",
  "download_urls": ["..."],
  "license": {"name": "CC-BY-4.0", "url": "..."},
  "files": [{"path": "fji_admbnda.zip", "bytes": 1234, "sha256": "..."}],
  "extracted_files": [{"path": "fji_admbnda_adm1.shp", "bytes": 1234, "sha256": "..."}],
  "notes": ""
}
```

## 7. Long-table schema (per-country and pacific)

| Column | Type | Notes |
|---|---|---|
| `uid` | string | `{iso3}:{level_code}:{unit_code}`; stable across releases where the source code is stable. |
| `iso3` | string | ISO 3166-1 alpha-3 of the PICT. |
| `country_name` | string | Short English name from `config/countries.yml`. |
| `sovereign_iso3` | string | Sovereign/administering state (same as iso3 for independent states). |
| `political_status` | string | `independent`, `free_association`, `territory`. |
| `level_rank` | int16 | Section 4. |
| `level_code` | string | Section 4. |
| `level_type` | string | Section 4. |
| `level_name_local` | string | Section 4. |
| `nests` | bool | Section 4. |
| `unit_name` | string | Primary (English or official) name. |
| `unit_name_alt` | string, nullable | Local-language / alternate name. |
| `unit_code` | string | Source code (P-code, INSEE, FIPS, geoBoundaries shapeID) or generated `gen-<n>` when the source has none. |
| `code_scheme` | string | e.g. `pcode`, `insee`, `fips`, `geoboundaries`, `generated`. |
| `parent_uid` | string, nullable | `uid` of the containing unit one rank up. Null for EEZ and admin0. For non-nesting layers (`nests = false`) it is the parent assigned by largest area overlap where one exists, else null. |
| `eez_uid` | string, nullable | `uid` of the EEZ polygon the unit sits in (by majority area). |
| `source_id` | string | Matches the source register and raw manifest. |
| `source_publisher` | string | |
| `source_url` | string | Landing URL. |
| `source_version` | string, nullable | |
| `source_date` | date, nullable | Publication date of the source data. |
| `retrieved_at` | timestamp (UTC) | |
| `license` | string | Exactly one licence per row, resolved for the level the row came from: SPDX id where one exists (`CC-BY-4.0`, `CC-BY-3.0-IGO`, `CC-BY-SA-3.0`, `ODbL-1.0`), `LO-2.0` (Licence Ouverte 2.0), else a short name (`Public domain (US Government work)`, `Public domain`, `PacIOOS data use (free redistribution, not for legal use)`, `unspecified`). |
| `license_url` | string, nullable | URL of that licence (canonical URL for SPDX ids, else the register's licence URL). |
| `license_agreement` | string, nullable | Data-use agreement under which this project uses and redistributes the row although its public licence alone would not allow it (register `license.agreement`, e.g. `CSDR-SPC data use agreement (user-confirmed 2026-11-20)`). Null for rows used under their public licence. |
| `license_restricted` | bool | True for sources that cannot be freely redistributed (GADM, ODbL share-alike flagged separately in `license`). |
| `geometry_method` | string | `as_published`, `dissolved_from_children`, `clipped_to_land`, `clipped_to_coastline` (clipped to another source's land outline, register `clip_to`), `split_from_admin0_by_atoll`, `supplemented_from_natural_earth`, `made_valid`, ... (semicolon-separated if several). |
| `area_km2` | float64 | Geodesic-equivalent area computed in an equal-area projection (EPSG:6933). |
| `bbox` | struct | GeoParquet 1.1 covering column. |
| `geometry` | MultiPolygon, EPSG:4326 | |

Rows are ordered by `iso3`, `level_rank`, `unit_code`.

Licences and agreements (decisions D-016, D-019, D-020):
* `license` is always the source's *public* licence. A source used under a data-use
  agreement (SPC Pacific Maritime Boundaries EEZ polygons; SPC PCRAFI and LINZ layers for
  COK, NIU, TKL) keeps its public licence, e.g. `license = CC-BY-NC-SA-4.0`, and carries
  the agreement in `license_agreement`. Its register entry sets
  `license: {name: CC-BY-NC-SA-4.0, redistribution_ok: true, agreement: "<text>"}`, so its
  rows are *not* restricted and appear in the published and combined products.
* Register validation rejects a non-open licence (`CC-BY-NC-SA-4.0`, `GADM licence`,
  `unspecified`) with `redistribution_ok: true` but no `agreement`.
* Downstream users are bound by the row's public licence (for SPC data, CC BY-NC-SA 4.0:
  non-commercial, share-alike, attribution) unless they hold their own agreement. EEZ-derived
  geometry (EEZ rows, `eez_uid` assignment, the marine rows and EEZ clipping in the finest
  partition) is SPC data used under the CSDR-SPC agreement.
* STAC items summarise the distinct values in `pab:licenses` and `pab:license_agreements`
  (section 10).

Conventions added by the processing stage (2026-11-20):
* `admin0` rows always use the ISO3 code as `unit_code` (`code_scheme = iso3166-1-alpha-3`), so
  `uid = {iso3}:admin0:{iso3}` is stable whatever source the outline comes from.
* `other` (non-nesting) layers carry a layer key so several can coexist in one country:
  `uid = {iso3}:other-{layer_key}:{unit_code}` (e.g. `ASM:other-census-tract:60010950100`).
* EEZ rows use the Marine Regions MRGID: `uid = {iso3}:eez:{mrgid}`. Overlapping-claim and
  joint-regime polygons appear in every PICT claimant's table (so they occur once per claimant
  in `pacific_admin.parquet`) with `nests = false`; only `200NM` polygons have `nests = true`
  and are used to stamp `eez_uid` on land units.
* A level may hold a licence-restricted *parallel* layer next to the open one (Cook Islands,
  ruling): only the open one is a parent for the next level; the restricted rows live in
  the local-only `<iso3>_admin_restricted.parquet` companion, never in `<iso3>_admin.parquet` or
  the combined products.
* Codes that the source does not provide are `gen-<n>` (numbered in name order) or, where the
  processing stage derives the unit, a name slug (`code_scheme = name-slug`).
* Rows are ordered by `iso3`, `level_rank`, `unit_code` (then `uid` to break ties). Parquet row
  groups never span two countries and hold at most 5,000 rows, so readers can prune by
  `iso3` using row-group statistics.

## 8. Finest-partition schema (`pacific_admin_finest.parquet`)

| Column | Type | Notes |
|---|---|---|
| `uid` | string | uid of the finest nesting unit, or `{iso3}:marine:{eez_uid}` for the marine remainder. |
| `iso3`, `country_name`, `sovereign_iso3`, `political_status` | | as above |
| `eez_uid`, `eez_name` | string | |
| `is_marine` | bool | True for the EEZ remainder polygon. |
| `finest_level_code`, `finest_level_type` | string | Level of the row's unit. |
| `admin0_uid`, `admin0_name` | string, nullable | |
| `admin1_uid`, `admin1_name`, `admin1_type` | string, nullable | |
| `admin2_uid`, `admin2_name`, `admin2_type` | ... | up to `admin5_*` |
| `source_ids` | string | Semicolon-separated source ids contributing to the row. |
| `license` | string | Semicolon-separated distinct licences of those sources (section 7). |
| `license_agreement` | string, nullable | Distinct data-use agreements of those sources, separated by ` \| ` (agreement texts may contain `;`); null when none. |
| `area_km2`, `bbox`, `geometry` | | as above |

Construction: for each PICT, take the finest `nests = true` layer; where a
country has partial coverage at the finest level (e.g. wards only for some
provinces), fall back to the next level up for the uncovered area so the
partition is complete. Clip the land units to their EEZ (units straddling an
EEZ boundary are split and flagged in `geometry_method`). Marine remainder =
EEZ minus union of land units. Every polygon in an EEZ is covered exactly once.
Overlapping-claim and joint-regime EEZ polygons are included as their own rows
with `is_marine = true` and the claimants recorded in `eez_name`.

Partition domain (D-024): the EEZ base is the SPC Pacific Maritime Boundaries set, whose zone
polygons are solid (land inside, no land holes). The domain of each 200NM zone is simply the SPC
polygon as published (halves split at the antimeridian are merged in EPSG:3832); an interior
ring is a real gap and is kept (the high-seas pocket inside French Polynesia). For Marine
Regions polygons (used for the Torres Strait joint regime and the Wake/Enenkio claim, and as
the fallback reader) land is cut out as holes, so their domain is the outline with holes
filled. Any land of the country beyond the domain is attached to its zone and flagged
`land_outside_eez_outline` (none with the SPC base). The area check compares the sum of parts
with this domain. The EEZ rows themselves are never reduced by our land layers: `area_km2` is
the whole zone as SPC publishes it. A land unit split by an EEZ line keeps its `uid` in each part (unique on
`uid` + `eez_uid`), flagged `clipped_to_eez`; partial-coverage fallbacks are flagged
`no_<level>_coverage`. `pacific_admin_finest.parquet` also carries `geometry_method`.
`data/processed/EEZ/pacific_eez.parquet` uses the long-table columns (including
`license_agreement`) plus `mrgid`, `pol_type`, `claimants`, `mrgid_eez`, `area_km2_published`,
`boundary_source`, `attribute_notes`, `land_km2` and `marine_km2`. `land_km2` and `marine_km2`
are written by `pab combine` from the finest partition: land = the country's land units in the
zone, marine = zone minus their union (the marine remainder row); `area_km2` = land + marine
within the 0.01 % area check. `attribute_notes` records the SPC attribute faults corrected in
processing (D-025; raw files are never edited): `area_km2` in m2 (GUM, MHL, MNP), `iso_ter1`
`FIJ`/`Palau`, MHL `mrgid_eez` 8319 (swapped with Wake) corrected to 8318, `pol_type` `200 NM`.
SPC's Wake zone (area attribute 0) is a non-PICT neighbour and is not used; the Wake/Enenkio
overlapping claim (8319) and the Torres Strait joint regime (21798) come from Marine Regions
v12 with their own `source_id` and CC BY 4.0 licence. Boundary differences versus Marine
Regions (SPC follows the national deposits): the Fiji/Wallis and Futuna line (about 12,000 km2
of Marine Regions' Fiji zone is in SPC's Wallis and Futuna zone) and the Niue/Tonga line (about
3,200 km2 of Marine Regions' Tonga zone is in SPC's Niue zone). Minerva Reefs are in SPC's
Fiji zone.

EEZ polygon selection (`config/eez_polygons.csv`, column names case-insensitive): one row per
polygon with `mrgid`, `relevance` (`pict`/`shared` rows are used), `pab_iso3` (claimants,
`;`-separated) and, optionally, `source_id` (a source in `config/sources/EEZ.yml`) and `layer`
(a file below that source's `raw_path`; a bare name such as `fj_eez_pol` means
`extracted/fj_eez_pol.shp`). Rows without them use the register's `selected` source and its
level `layer` (the Marine Regions single-layer reader, kept as a fallback). Both the SPC Pacific
Maritime Boundaries layers and Marine Regions use the Marine Regions attribute schema (lower
case `mrgid`, `geoname`, `pol_type`, `territory1`, `iso_ter1`, `sovereign1`, `iso_sov1`,
`mrgid_eez`, `area_km2`); `pol_type` spellings are normalised (`200 NM` -> `200NM`), published
areas above 10^8 are read as m2 and converted, and the SPC `source` field (the legal instrument
the limits are built from) is kept as `boundary_source` (null for Marine Regions).

## 9. Geometry processing rules

* Storage CRS EPSG:4326. Geometries crossing the antimeridian are split at
  180° (RFC 7946 style); planar overlay operations run in EPSG:3832 (PDC
  Mercator) or an equal-area local projection, never in 4326.
* `shapely.make_valid` on every input; record in `geometry_method`.
* Promote Polygon to MultiPolygon; drop empty geometries with a logged warning.
* No simplification of published geometries. Simplified/tiled derivatives
  (PMTiles) are optional extras, not substitutes.
* Coordinate precision: round to 7 decimal places (approximately 1 cm).
* Topology between levels is **as published**; we do not snap child units to
  parent outlines. Where a child union differs materially from the parent
  polygon this is reported in the per-country QA report.

## 10. STAC

Decision D-022: the root Catalog sits at the top of the published tree, so
`data/catalog.json` (root Catalog `pab`) and `data/collection.json` (Collection
`pacific-admin-boundaries`) live in `data/`, which maps to the S3 prefix root
(`s3://<bucket>/<prefix>/catalog.json`). There is no `stac/` folder.

* STAC 1.1.0. One Item per published GeoParquet file, written next to the file as
  `<name>.stac-item.json`. Extensions: `proj` (EPSG:4326, bbox), `table` (column list, row
  count), `version`, `scientific` (`sci:citation` of every source), `processing`
  (`processing:software` with the `pab` version and, once the repository has commits, the
  git commit), plus `alternate-assets` when built with a base URL.
* **Links: relative published catalog.** Every link is relative (`./collection.json`,
  `./processed/FJI/fji_admin.stac-item.json`, `../../collection.json`), except the root
  Catalog's `self` link, which is absolute: `<https_base>/catalog.json` from
  `config/publish.yml` (or the `--base-url` given).
* **Assets.** `data` (role `data`, `application/vnd.apache.parquet`), `provenance` (the step
  records beside the file) and one `manifest-<source_id>` per source (the raw download
  manifest). Without `--base-url` (local use) all asset hrefs are relative. With `pab stac
  --base-url <https_base>` (what `make stac` does), assets below `data/` get absolute HTTPS
  hrefs plus an `alternate.s3.href` (`s3://<bucket>/<prefix>/...`), and the manifest assets
  point to the GitHub repository at the release tag (raw files under `data/raw/` are never
  mirrored to S3).
* **Provenance on every Item (D-021).** Properties: `pab:iso3`, `pab:levels`,
  `pab:source_ids`, `pab:licenses`, `pab:license_agreements`, a `description` naming the
  sources and licences (and the agreement terms when one applies), `providers` (one per
  source publisher as `licensor`/`producer`, then this project as `producer`/`processor` with
  the GitHub `repo_url`, then AWS S3 as `host`), `sci:citation`, `processing:software`,
  `pab:git_commit` (null before the first commit), `version`, `created` (kept across
  rebuilds) and `updated`. `license` is the SPDX id when the table has a single SPDX licence,
  else `other` with one `license` link per licence. Links: `via` to each source's landing
  page, `about` to the dataset's section of `docs/sources.md` on GitHub, `license`,
  `collection`, `parent`, `root`.
* **Catalog and Collection** carry `providers`, `about` (GitHub repository), `documentation`
  (`docs/usage.md` on GitHub), `describedby` (`docs/sources.md`) and `license` links for every
  licence present. The Collection summarises `pab:iso3`, `level_code`, `license` and
  `license_agreement`.
* `pab stac --check` asserts these fields on every item and on the catalog/collection and
  prints a table; `pab stac` validates every object with pystac. `make stac` runs both.
* `pab publish` mirrors `data/processed/**` (except `*_restricted.parquet`),
  `data/combined/**`, `data/catalog.json` and `data/collection.json` to
  `s3://<bucket>/<prefix>/` with content types `application/vnd.apache.parquet`
  (GeoParquet), `application/geo+json` (Items) and `application/json` (Catalog, Collection,
  provenance). `pab publish --verify` reads the catalog back over HTTPS (see
  `docs/publishing.md`).

## 11. Provenance

Every CLI stage writes a step record (`inputs`, `outputs`, `completed_at`,
software versions, git commit) to `data/processed/<ISO3>/provenance.json`
(appended) and the STAC Item's `processing:*` fields. The chain is
raw manifest -> source register -> per-country item -> combined item.

## 12. Versioning

Data products carry `version` in STAC (`v0.1.0` initially). Paths are not
versioned, in the repo or on S3 (`s3://<bucket>/<prefix>/` from `config/publish.yml`); a
versioned prefix can be configured there if a release needs one. Releases are git tags, and
STAC links to GitHub files use the release tag (`git_ref`, default `version`).
