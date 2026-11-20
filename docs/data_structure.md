# Data structure

This page covers the folder layout, file naming, the column dictionaries of each product,
the STAC layout and the S3 mirror. The normative specification is
[data_model.md](data_model.md). Everything here was checked against the v0.1.0 files.

## Folder layout

```
pacific_administrative_boundaries/
├── README.md, CHANGELOG.md, CITATION.cff, LICENSE
├── pyproject.toml, uv.lock, Makefile
├── pab/                         pipeline package (CLI: `pab`)
├── scripts/                     one-off helpers (raw integrity check)
├── tests/
├── config/
│   ├── countries.yml            the 22 PICTs: ISO codes, names, political status, sovereign, EEZ MRGIDs
│   ├── levels.yml               level_type vocabulary and level_code list
│   ├── eez_polygons.csv         EEZ polygons selected per PICT (source, layer, MRGID), with notes
│   ├── publish.yml              GitHub URL, S3 bucket/prefix, HTTPS base, version
│   └── sources/<ISO3>.yml       source register per country (plus EEZ.yml)
├── data/                        published root (= s3://<bucket>/<prefix>/)
│   ├── catalog.json             STAC root Catalog
│   ├── collection.json          STAC Collection
│   ├── raw/<ISO3>/<source_id>/  original downloads, untouched, plus manifest.json (not on S3)
│   ├── raw/EEZ/<source_id>/
│   ├── processed/<ISO3>/        <iso3>_admin.parquet, <iso3>_admin.stac-item.json, provenance.json
│   ├── processed/EEZ/           pacific_eez.parquet, pacific_eez.stac-item.json, provenance.json
│   └── combined/                pacific_admin.parquet, pacific_admin_finest.parquet,
│                                their .stac-item.json, partition_checks.json, provenance.json
└── docs/
```

Git tracks the code, the configuration, the docs, and every JSON file under `data/`: the
STAC catalog, collection and items, the raw manifests, `provenance.json` and
`partition_checks.json`. The GeoParquet files and the raw downloads are not in git. The
GeoParquet files and the STAC JSON are published on S3 under the same paths relative to
`data/`; see [S3 mirror](#s3-mirror).

## File naming

| Pattern | Example |
|---|---|
| `data/processed/<ISO3>/<iso3>_admin.parquet` | `data/processed/FJI/fji_admin.parquet` |
| `data/processed/EEZ/pacific_eez.parquet` | |
| `data/combined/pacific_admin.parquet` | |
| `data/combined/pacific_admin_finest.parquet` | |
| `<same name>.stac-item.json` next to each parquet file | `data/processed/FJI/fji_admin.stac-item.json` |
| `data/raw/<ISO3>/<source_id>/manifest.json` | `data/raw/FJI/fji-sdd-phc2017-boundaries/manifest.json` |

`source_id` is a unique kebab-case id across the repository. It is the same in the
register, the raw folder, the manifest, the `source_id` column and the STAC item.

## Products

| File | Rows | Size (MB) | Contents |
|---|---|---|---|
| `data/processed/<ISO3>/<iso3>_admin.parquet` (22 files) | 14,231 in total | 0.1 to 100 | Every level for one country, stacked, including the country's EEZ rows. |
| `data/processed/EEZ/pacific_eez.parquet` | 27 | 1.2 | One row per selected EEZ polygon: 24 200 NM zones and the Matthew and Hunter overlapping claim (SPC), plus the Wake Island / Enenkio overlapping claim and the Torres Strait joint regime (Marine Regions). |
| `data/combined/pacific_admin.parquet` | 14,231 | 224.2 | All per-country tables, concatenated. |
| `data/combined/pacific_admin_finest.parquet` | 8,199 | 106.1 | Planar partition of every EEZ: 8,172 land pieces and 27 marine rows. |

Rows per country in the per-country files are: ASM 583, COK 222, FJI 2,087, FSM 475,
GUM 2,097, KIR 617, MHL 229, MNP 1,041, NCL 85, NIU 16, NRU 63, PCN 2, PLW 243, PNG 442,
PYF 469, SLB 1,589, TKL 5, TON 1,446, TUV 115, VUT 1,095, WLF 44 and WSM 1,266.

Rows per level in `pacific_admin.parquet`:

| eez | admin0 | admin1 | admin2 | admin3 | admin4 | admin5 | other |
|---|---|---|---|---|---|---|---|
| 28 | 22 | 163 | 719 | 3,013 | 5,610 | 843 | 3,833 |

There are 28 EEZ rows but only 27 EEZ polygons. The Matthew and Hunter overlapping claim
is claimed by both New Caledonia and Vanuatu, so it appears once under each, with uids
`NCL:eez:48948` and `VUT:eez:48948`.

Every published row is redistributable (`license_restricted` is false everywhere). 50
rows of the long table carry `license = CC-BY-NC-SA-4.0` with a `license_agreement`: the
26 SPC EEZ rows and the 24 Cook Islands electoral constituencies. See
[sources.md](sources.md) and the licence notes in [caveats.md](caveats.md#licences).

### File format

All four products share the same format:

* GeoParquet 1.1, with WKB geometry in the `geometry` column, of type MultiPolygon.
* CRS EPSG:4326 (longitude, latitude), declared in the GeoParquet metadata.
* A `bbox` covering column (struct of `xmin`, `ymin`, `xmax`, `ymax`) on every row, so
  readers can filter on bounding boxes without decoding geometry.
* zstd compression.
* Sort order: rows are sorted by `iso3`, `level_rank`, `unit_code`. In the finest
  partition they are sorted by `iso3`, `is_marine`, `uid`.
* Row groups never span two countries. Each combined file has 22 row groups, one per
  country, with at most 2,097 rows each. Readers that push down filters (pyarrow,
  geopandas `filters=`, DuckDB, GDAL) can skip every other country when you filter on
  `iso3`.
* Geometries that cross the antimeridian are split at ±180°. Such a row's `bbox` spans
  -180 to 180 (21 rows in the combined long table). See [usage.md](usage.md#antimeridian).

## Long table columns

These columns are in `pacific_admin.parquet` and in every `<iso3>_admin.parquet`.

| Column | Type | Description |
|---|---|---|
| `uid` | string | Unique id: `{iso3}:{level_code}:{unit_code}`, for example `FJI:admin3:1001`. Non-nesting layers use `{iso3}:other-{layer_key}:{unit_code}`, for example `ASM:other-census-tract:60010950100`. EEZ rows use `{iso3}:eez:{MRGID}`. The uid is stable across releases as long as the source code is stable. |
| `iso3` | string | ISO 3166-1 alpha-3 code of the PICT. |
| `country_name` | string | Short English name from `config/countries.yml`. |
| `sovereign_iso3` | string | Sovereign or administering state: USA, FRA, NZL, GBR, or the iso3 itself for independent states. |
| `political_status` | string | `independent`, `free_association` (COK, NIU) or `territory`. |
| `level_rank` | int16 | Position in the hierarchy: 0 = eez, 1 = admin0, 2 = admin1 ... 6 = admin5, 99 = other. |
| `level_code` | string | `eez`, `admin0` to `admin5`, or `other`. Assigned per country, from the top down. |
| `level_type` | string | Harmonised category for comparing across countries: `eez`, `country`, `region`, `state_province`, `district`, `local_government`, `ward_village`, `island`, `statistical`, `electoral`, `customary`. Definitions are in `config/levels.yml`. `state_province` occurs at most once per country. `statistical` can repeat at successive levels in one country by design, for example COK census districts and enumeration areas, or TON census blocks and census units. |
| `level_name_local` | string | The level's own name in the country, for example "Tikina", "Area Council / Municipality", "Census unit". |
| `nests` | bool | True if the layer is a strict subdivision of the level above and is used in the finest partition. False for `other` layers, overlapping-claim and joint-regime EEZ rows, and the French Polynesia quartiers. |
| `unit_name` | string | Primary name (English or official), as in the source, except for the two corrected Palau state names. |
| `unit_name_alt` | string, nullable | Alternative or official long name, where the source has one (32 rows). |
| `unit_code` | string | The source's own code: P-code, INSEE, FIPS/GEOID, census id, geoBoundaries shapeID or MRGID. Where the source has none, it is a generated `gen-<n>` or a name slug. |
| `code_scheme` | string | What kind of code `unit_code` is, for example `pcode`, `insee`, `fips`, `sdd-census`, `tsd-census`, `geoboundaries`, `iso3166-1-alpha-3` (admin0), `iso3166-2`, `mrgid` (EEZ), `name-slug`, `generated`. |
| `parent_uid` | string, nullable | uid of the containing unit one level up. Null for eez, admin0 and `other` rows. A nesting-level layer that fails its nest check (`nests = false`, the French Polynesia quartiers) keeps a parent by largest overlap, for information. |
| `eez_uid` | string, nullable | uid of the 200 NM EEZ polygon the unit lies in, by largest area. Null only on EEZ rows. |
| `source_id` | string | Source id, matching the register, the raw folder and the manifest. |
| `source_publisher` | string | Publisher, from the register. |
| `source_url` | string | Landing page of the source. |
| `source_version` | string, nullable | Version or edition label of the source, for example "2017 PHC", "TIGER/Line 2025" or an LDS version id. |
| `source_date` | date | Publication date of the source data (best available). |
| `retrieved_at` | timestamp (UTC) | When the raw files were downloaded, from the manifest. |
| `license` | string | Exactly one licence per row: `CC-BY-4.0`, `CC-BY-3.0-IGO`, `CC-BY-NC-SA-4.0`, `CC-BY-SA-3.0`, `ODbL-1.0`, `LO-2.0`, `Public domain (US Government work)`, `Public domain` or `PacIOOS data use (free redistribution, not for legal use)`. This is the source's public licence, the one that binds you. See [sources.md](sources.md). |
| `license_url` | string | URL of that licence. |
| `license_agreement` | string, nullable | The data use agreement under which this project uses and redistributes the row, where the public licence alone would not allow it: `CSDR-SPC data use agreement (user-confirmed 2026-11-20)` on the SPC rows (EEZ, Cook Islands electoral). Null elsewhere. It does not extend to downstream users. |
| `license_restricted` | bool | True if the source may not be redistributed. False on every row in v0.1.0; restricted rows would be kept out of the published files. Share-alike and non-commercial licences are not "restricted"; find them through `license`. |
| `geometry_method` | string | Semicolon-separated processing tokens, for example `as_published`, `made_valid`, `dissolved_from_children;parent_by_code`. See [methods.md](methods.md#derived-units-and-geometry_method-tokens). |
| `area_km2` | float64 | Area in km², computed in EPSG:6933 (equal area). |
| `geometry` | MultiPolygon, EPSG:4326 | |
| `bbox` | struct | GeoParquet covering column. |

## Finest partition columns

`pacific_admin_finest.parquet` has one row per piece. A land piece is the part of a
finest-level unit inside its parents and its EEZ. A marine row is the rest of an EEZ.

| Column | Type | Description |
|---|---|---|
| `uid` | string | uid of the finest unit at this location, or `{iso3}:marine:{eez_uid}` for marine rows, for example `FJI:marine:FJI:eez:8325`. Unique in v0.1.0, because no unit is split across two EEZs. In general, `uid` + `eez_uid` is the unique key. |
| `iso3`, `country_name`, `sovereign_iso3`, `political_status` | string | As in the long table. |
| `eez_uid` | string | The 200 NM zone the piece belongs to. For the shared polygons, this is that polygon's own uid. |
| `eez_name` | string | Name of the zone as published (SPC, or Marine Regions for the two Marine Regions rows). For shared polygons, the name is followed by the type and claimants in brackets. |
| `is_marine` | bool | True for the EEZ remainder and the shared polygons (27 rows). |
| `finest_level_code`, `finest_level_type` | string | Level of the unit this piece belongs to: `admin0` to `admin5`, or `eez` for marine rows. |
| `admin0_uid`, `admin0_name` | string, nullable | The country's land unit. Null on marine rows. |
| `admin1_uid`, `admin1_name`, `admin1_type` ... `admin5_uid`, `admin5_name`, `admin5_type` | string, nullable | uid, name and `level_type` of the ancestor (or of the unit itself) at each level. Null below the piece's finest level and on marine rows. |
| `source_ids` | string | Semicolon-separated `source_id`s of every level in the piece's chain. On marine rows, the EEZ source. |
| `license` | string | Licences of every level in the piece's chain, semicolon-separated and de-duplicated, for example `CC-BY-3.0-IGO;CC-BY-4.0`. On marine rows, the EEZ licence (`CC-BY-NC-SA-4.0` for SPC zones). |
| `license_agreement` | string, nullable | As in the long table, joined over the chain. Set on the SPC marine rows. |
| `geometry_method` | string | Partition token: `as_published` (a whole child, or a clipped piece of one), `no_<level>_coverage` (a parent area with no child at that level), `land_outside_eez_outline` (PNG land-border slivers, 130.6 km²), `eez_minus_land` (marine remainder), `as_published;overlapping_claim`, `as_published;joint_regime`, `clipped_to_eez` (does not occur in v0.1.0). |
| `area_km2` | float64 | Area of the piece (EPSG:6933). |
| `geometry`, `bbox` | | As in the long table. |

Finest rows by level: admin0 2 (Pitcairn, and a 0.6 km² piece of Niue outside its
villages), admin1 59, admin2 261, admin3 1,956, admin4 5,051, admin5 843, eez 27.

## EEZ file columns

`pacific_eez.parquet` has all the long-table columns, plus:

| Column | Type | Description |
|---|---|---|
| `mrgid` | string | Marine Regions MRGID of the polygon (also in `unit_code`). SPC layers carry the same MRGIDs. |
| `pol_type` | string | `200NM`, `Overlapping claim` or `Joint regime`. |
| `claimants` | string | Semicolon-separated claimants as assigned in `config/eez_polygons.csv`, for example `NCL;VUT`, `MHL;USA`. |
| `mrgid_eez` | string | `MRGID_EEZ` attribute (corrected where SPC swapped it; see `attribute_notes`). |
| `area_km2_published` | float64 | Area attribute as published by the source, for comparison with `area_km2`. Corrected to km² where SPC stored it in m² (GUM, MHL, MNP). |
| `boundary_source` | string, nullable | For SPC rows: the legal instrument the limits are built from, as cited by SPC (usually a UN DOALOS deposit or national act, as a URL). Null for Marine Regions rows. |
| `attribute_notes` | string, nullable | Attribute faults in the source that were corrected in processing, for example `area_km2 attribute ... is in m2; converted to km2` or `iso_ter1 'FIJ' read as FJI`. Geometry is never changed. |
| `land_km2` | float64 | Area of the country's land units inside the zone, from the finest partition. 0 for overlapping claims and joint regimes. |
| `marine_km2` | float64 | `area_km2` minus the land: the marine area of the zone. |

The SPC zone polygons are solid: land is inside them, not cut out. So `area_km2` is the
full 200 NM zone, and `land_km2 + marine_km2 = area_km2` for every zone except PNG. There,
130.6 km² of enumeration-area slivers along the Indonesian land border lie outside the
SPC polygon, so the sum exceeds the zone area by that amount.

In this file, `iso3` is the first PICT claimant (MHL for Wake/Enenkio, NCL for Matthew
and Hunter). `nests` is true only for the 200 NM zones. `parent_uid` and `eez_uid` are
null.

## STAC layout

```
data/catalog.json                  Catalog "pab" (root)
└── data/collection.json           Collection "pacific-admin-boundaries" (version v0.1.0)
    ├── processed/<ISO3>/<iso3>_admin.stac-item.json     22 items: pab-<iso3>-admin
    ├── processed/EEZ/pacific_eez.stac-item.json         pab-pacific-eez
    ├── combined/pacific_admin.stac-item.json            pab-pacific-admin
    └── combined/pacific_admin_finest.stac-item.json     pab-pacific-admin-finest
```

* STAC 1.1.0, as a *relative published catalog*: every link is relative, except the root
  catalog's `self` link, which is the published URL (`<https_base>/catalog.json`). The
  tree works unchanged on a local disk, in git and on S3.
* Asset hrefs are absolute HTTPS URLs in the published build (`make stac`, which runs
  `pab stac --base-url <https_base>`), each with an `s3://` alternate; `make stac-local`
  writes relative asset hrefs instead. Raw manifests are linked on GitHub.
* Each item has:
  * geometry and bbox. These are split into two boxes, with west > east, when the data
    cross the antimeridian;
  * `start_datetime` and `end_datetime`: the span of the sources' publication dates;
  * `version` (v0.1.0);
  * `proj:code` (EPSG:4326);
  * `table:columns`, `table:row_count`, `table:primary_geometry`;
  * `processing:software`, `processing:lineage`, `processing:datetime`;
  * `sci:citation`: a citation for each source;
  * `description` naming the sources and licences; `providers` (each source publisher,
    this project with its GitHub URL, and AWS S3 as host); `created` and `updated`;
  * `pab:iso3`, `pab:levels`, `pab:source_ids`, `pab:licenses`,
    `pab:license_agreements`, `pab:git_commit`;
* Assets: `data`, the parquet file, of type `application/vnd.apache.parquet`;
  `provenance`, the step records; and one `manifest-<source_id>` per contributing source,
  which points to its raw manifest (role `metadata`).
* Links: `via` to each source's landing page, `about` to the dataset's section of
  `docs/sources.md` on GitHub, and `license` to each licence. The item-level `license` is
  the SPDX id when the file has a single SPDX licence, else `other`. In v0.1.0 every
  item is `other`, because every file mixes the SPC EEZ licence with land licences.
* The catalog and collection link to the GitHub repository (`about`, `documentation`,
  `describedby`) and list the providers and licences. The collection summarises
  `pab:iso3`, `level_code`, `license` and `license_agreement`.
* `pab stac --check` prints a table of these fields per item and fails if any is missing.

## S3 mirror

`data/` is the published root. `pab publish` mirrors it to
`s3://csdr-public-datasets/pacific-administrative-boundaries/` (from `config/publish.yml`),
with the same paths relative to `data/`:

```
s3://<bucket>/<prefix>/catalog.json
s3://<bucket>/<prefix>/collection.json
s3://<bucket>/<prefix>/processed/<ISO3>/<iso3>_admin.parquet (+ .stac-item.json, provenance.json)
s3://<bucket>/<prefix>/processed/EEZ/pacific_eez.parquet
s3://<bucket>/<prefix>/combined/pacific_admin.parquet
s3://<bucket>/<prefix>/combined/pacific_admin_finest.parquet
```

So `s3://<bucket>/<prefix>/processed/FJI/fji_admin.parquet` is the same file as
`data/processed/FJI/fji_admin.parquet`. Over HTTPS the same objects are under
`https://csdr-public-datasets.s3.ap-southeast-2.amazonaws.com/pacific-administrative-boundaries/`.
Nothing under `data/raw/` is mirrored. The release version is recorded in each item's
`version` and in the git tag. In v0.1.0 the upload is 77 objects, 530.6 MB. What is
published, and the commands, are in [publishing.md](publishing.md).

## Sizes (v0.1.0)

| Item | Size |
|---|---|
| `data/combined/` | about 330 MB (long table 224.2 MB, finest 106.1 MB) |
| `data/processed/` (22 countries + EEZ) | about 226 MB. The largest are PYF (100.1 MB) and NCL (61.8 MB), which come from detailed cadastral geometry. Most countries are under 10 MB. |
| Published to S3 | 77 objects, 530.6 MB (all GeoParquet, STAC JSON and provenance) |
| `data/raw/` (local only; never published) | about 2.2 GB, 128 source folders with manifests |
| Git-tracked JSON (raw manifests, STAC, provenance) | about 1.6 MB |
