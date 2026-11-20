# Methods

This page describes how the v0.1.0 products were built: the pipeline stages, the
geometry rules, the derived units, and how provenance is recorded. The pipeline is the
`pab` Python package in `pab/`. The technical contract it follows is in
[data_model.md](data_model.md); this page explains how that contract is implemented.

## Overview

```
config/sources/<ISO3>.yml  ──►  pab cache  ──►  data/raw/<ISO3>/<source_id>/  (+ manifest.json)
config/eez_polygons.csv                               │
                                                      ▼
                     pab process EEZ  ──►  data/processed/EEZ/pacific_eez.parquet
                     pab process XXX  ──►  data/processed/<ISO3>/<iso3>_admin.parquet
                     pab assign-eez   ──►  (eez_uid stamped, EEZ rows added)
                     pab combine      ──►  data/combined/pacific_admin.parquet
                                           data/combined/pacific_admin_finest.parquet
                     pab stac         ──►  *.stac-item.json, data/collection.json, data/catalog.json
                     pab publish      ──►  s3://<bucket>/<prefix>/ (data/processed, data/combined, STAC)
                     pab qa           ──►  QA summaries (not published)
```

Each stage reads the outputs of the stage before it. The stages can be re-run on their
own, and each one records what it did in a `provenance.json` file (see
[Provenance](#provenance)).

## Stages

| Stage | Command | Make target | What it does |
|---|---|---|---|
| validate | `pab validate` | `make validate` | Checks every source register against a JSON schema, then lists the levels that will be processed. |
| cache | `pab cache <ISO3>`, `pab cache EEZ`, `pab cache --all` | `make cache`, `make cache-eez`, `make cache-all` | Downloads every source the process stage reads for that country, and writes `manifest.json`. These are the selected sources, sources chosen in the `decisions` block, `use: true` entries, and supplements named inside `derive` blocks. Use `--source <id>` to fetch any other source. |
| process EEZ | `pab process EEZ` | `make process-eez` | Reads the EEZ polygons listed in `config/eez_polygons.csv` (SPC Pacific Maritime Boundaries, plus two Marine Regions polygons), corrects known attribute faults, and writes `pacific_eez.parquet`. |
| process | `pab process <ISO3>`, `pab process --all` | `make process`, `make process-all` | Turns raw files into the per-country long table, then writes a STAC item and a provenance record. |
| assign-eez | `pab assign-eez --all` | `make assign-eez` | Stamps `eez_uid` on the land units of every per-country table and adds that country's EEZ rows. Re-run it whenever the EEZ product changes. |
| combine | `pab combine` | `make combine` | Concatenates the per-country tables to make `pacific_admin.parquet`. Builds the finest partition, runs its area check, and writes `land_km2` and `marine_km2` back to the EEZ file. |
| stac | `pab stac --base-url <https_base> --check` | `make stac` (`make stac-local` for relative asset hrefs) | Writes one STAC item beside each GeoParquet file, plus `data/collection.json` and `data/catalog.json`, validates them, and checks that every required field is present. |
| publish | `pab publish` (`--dry-run`, `--verify`) | `make publish-dryrun`, `make publish`, `make publish-verify` | Uploads `data/processed`, `data/combined` and the STAC root to S3, and verifies the result over HTTPS. See [publishing.md](publishing.md). |
| qa | `pab qa --all` | `make qa` | Runs per-country QA: counts, validity, nesting and EEZ coverage. |

`make all` runs process-eez, process-all, assign-eez, combine, stac and qa in that
order. `pab process` skips any output that already exists unless you pass `--overwrite`.

### cache

The source register entry is the single place where a source is described: its landing
URL, download URLs, licence, publication date, version and layers. `pab cache` follows
these steps:

1. Downloads each direct URL to a temporary directory. A file is rejected if its size
   does not match the HTTP `Content-Length`.
2. Tests each zip archive. Members are extracted with path checks; nothing downloaded is
   ever executed.
3. Computes the sha256 of every downloaded and extracted file.
4. Copies the files into `data/raw/<ISO3>/<source_id>/` and checks the sha256 again after
   the copy.
5. Writes `manifest.json`, which records the time, URLs, HTTP status, content type, byte
   size and sha256 of each file.

The download goes through a temporary directory because writing straight into a synced
folder was seen to truncate files while the server still reported success.

The v0.1.0 raw files were retrieved on 2026-11-19 and 2026-11-20 (UTC) with the same
checks. There are 128 raw manifests. The integrity sweep (`scripts/raw_integrity_check.py`)
tests archives, opens geodata files and compares sizes with the manifests; it found no
problems.

The LINZ Data Service layers (Cook Islands, Niue, Tokelau) need an API key, which LINZ
issues free to registered users. The key was sent as the HTTP header
`Authorization: key <LINZ_API_KEY>`, read from a local `.env` file. It is never written
to registers, manifests or any published file; the manifests record the request with a
`<LINZ_API_KEY>` placeholder. `pab cache` sends this header itself (the registers declare
an `auth` block), reading the key from the `LINZ_API_KEY` environment variable or `.env`.

### process

`pab process <ISO3>` is driven entirely by the register `config/sources/<ISO3>.yml`. The
register decides which level entries are built:

* every level of a source with `status: selected` is built, unless the `decisions` block
  chooses another source for that level;
* a level entry with `use: true` is built even when its source is an alternative. This
  is how the Marshall Islands villages are built;
* a level entry with `use: false` is skipped.

For each level entry, the stage then does the following:

1. **Read** the layer from the raw folder, with an optional attribute `filter` or
   `exclude`.
2. **Map attributes** with field specs. A spec can be a plain column name, or a column
   with transforms (integer division, slicing, zero-padding, value maps, regex, case),
   a format template over several columns, or a constant. The results are `unit_code`,
   `unit_name`, `unit_name_alt` and the parent code.
3. **Normalise geometry**. See [Geometry rules](#geometry-rules).
4. **Resolve codes**:
   * features that share a code are dissolved into one unit when the register asks for a
     dissolve, or when they have the same name;
   * codes shared by units with different names get the suffixes `-1`, `-2` and so on;
   * missing codes are generated as `gen-<n>`, numbered in name order.
5. **Correct names** where the register gives a `name_map` (Palau). If a unit has no
   name, its code is used as the name.
6. **Derive** the units that no source publishes directly. See
   [Derived units](#derived-units-and-geometry_method-tokens).
7. **Clip to land** when the source declares a land mask (US TIGER/Line), or to another
   source's coastline when the level declares `clip_to: {source_id, layer}` (Niue
   villages, clipped to the LINZ outline).
8. **Build admin0**. It comes from an admin0 layer if one is used; otherwise it is the
   union of admin1. Its `unit_code` is always the ISO3 code.
9. **Assign parents** and check nesting. See [Parent assignment](#parent-assignment).
10. **Assemble** the long table. Source metadata (publisher, landing URL, version,
    publication date, licence) comes from the register. `retrieved_at` comes from the raw
    manifest. `area_km2` is computed, and the rows are written with a provenance record
    and a STAC item.

### assign-eez

Each land unit gets the `eez_uid` of the country's 200 NM zone that it overlaps most,
computed in EPSG:3832. The SPC zone polygons are solid, with land inside, so they are
used as they are. The two Marine Regions polygons cut land out as holes, so for them
the holes are filled first; that matters only if a Marine Regions polygon is ever used
as a 200 NM zone. A unit that overlaps no zone would get the nearest zone of its own
country; no unit needs this in v0.1.0.

Overlapping-claim and joint-regime polygons are added as rows with `nests = false`. They
are never used for `eez_uid`.

### process EEZ

`config/eez_polygons.csv` lists the polygons to use. For each row it gives the MRGID, the
claimants (`pab_iso3`), and the source and layer to read it from. The 24 200 NM zones and
the Matthew and Hunter overlapping claim come from the SPC Pacific Maritime Boundaries
layers. The Wake Island / Enenkio overlapping claim and the Torres Strait joint regime
come from Marine Regions v12, because SPC does not represent them as separate polygons
(see [sources.md](sources.md#eez)). Geometry is kept as published, apart from the
standard normalisation.

Known faults in the SPC attributes are corrected in the output, and each correction is
recorded in `attribute_notes`. The raw files are never edited. The faults are:

* area attributes stored in m² instead of km² (GUM, MHL, MNP);
* a zero area on the Wake polygon;
* `iso_ter1` values `FIJ` and `Palau` (read as FJI and PLW);
* swapped `mrgid_eez` values between the Marshall Islands and Wake polygons;
* `pol_type` written `200 NM` (normalised to `200NM`).

### combine

The combine stage reads the 22 per-country tables and writes the long table. It then
builds the finest partition from the same rows (see [Finest partition](#finest-partition)).
Finally it writes `land_km2` and `marine_km2` for each zone back into
`pacific_eez.parquet`. Any row with `license_restricted = true` would be dropped from
both products; there are none in v0.1.0.

### stac and qa

See [STAC layout](data_structure.md#stac-layout) for what the STAC stage writes.

The QA stage checks every per-country table for:

* counts per level, invalid or empty geometries, null names and generated codes;
* licence-restricted rows (none in v0.1.0);
* land units without an `eez_uid`, and admin0 area outside the country's EEZ;
* for each parent unit, how the union of its children compares with it: the area of the
  children outside the parent, and the area of the parent that no child covers. A parent
  is flagged when either is more than 1% of the parent's area.

The QA results feed the per-country notes in [caveats.md](caveats.md).

## Geometry rules

| Rule | Implementation |
|---|---|
| Storage CRS | EPSG:4326, longitude/latitude order. |
| Antimeridian | Every part that crosses 180° is split there, RFC 7946 style. A part is detected when it lies beyond ±180 or spans more than 180° of longitude. The split runs before repair, because repairing a wrapped polygon first damages it. Affected rows get `antimeridian_split`. Fiji, the Kiribati Gilbert zone and the Tuvalu EEZ cross 180°. The source EEZ polygons were already split there. |
| Validity | Only invalid inputs are repaired, with `shapely.make_valid` ("structure" method, keeping polygonal output only). Repaired rows get `made_valid`. Every output is checked: there are 0 invalid geometries in v0.1.0. |
| Geometry type | Promoted to MultiPolygon. Non-polygonal parts and empty geometries are dropped and logged (2 empty Fiji enumeration areas). |
| Precision | Coordinates are rounded to 7 decimal places (about 1 cm) with `shapely.set_precision(..., mode="valid_output")`, then re-checked for validity. |
| Simplification | None. Geometry is kept at the resolution the source published. |
| Overlays | Unions, intersections, differences and overlap tests run in EPSG:3832 (PDC Mercator, centred on 150°E). In that projection the whole region is continuous across the antimeridian. Results are projected back to 4326, split at 180° and normalised again. |
| Area | `area_km2` is the planar area in EPSG:6933 (WGS 84 / NSIDC EASE-Grid 2.0, equal-area). For units of this size it is within a fraction of a percent of the geodesic area. |
| Topology between levels | As published. Child units are not snapped to their parents. Differences are measured by QA and reported in [caveats.md](caveats.md). |

## Derived units and `geometry_method` tokens

`geometry_method` records what happened to each row's geometry. It is a semicolon-separated
list of tokens, and `as_published` means nothing was done. The tokens that occur in
v0.1.0 are:

| Token | Meaning | Where |
|---|---|---|
| `as_published` | The geometry is as in the source, apart from the storage normalisation. | many |
| `made_valid` | An invalid source geometry was repaired. | FJI, KIR, PLW, PYF, SLB, VUT, WLF, WSM |
| `antimeridian_split` | The geometry was split at 180°. | FJI |
| `dissolved_by_code` | Several source features with the same code were merged into one unit, either because the register asked for a dissolve or because one unit was stored as several features. | FJI divisions (from tikina), PYF subdivisions, communes and communes associees, WLF circonscriptions, WSM villages (from enumeration areas) |
| `dissolved_from_children` | The unit is the union of its child units. | admin0 of most countries (from admin1); COK groups (from the LINZ islands, with PCRAFI names and codes); PNG regions (from provinces) |
| `split_from_land_by_island`, `split_from_land_by_atoll` | A land layer with many islet polygons was split into islands or atolls by assigning each polygon to the nearest named island point. | COK islands (329 LINZ polygons into 15 islands), TKL atolls (177 LINZ islets into 3 atolls) |
| `clipped_to_coastline` | The unit was clipped to another source's coastline (`clip_to` in the register). | NIU villages, clipped to the LINZ outline (they agree to an IoU of 0.995) |
| `supplemented_from_natural_earth` | Islands missing from the main source were added from Natural Earth 10m. | PCN admin0 |
| `clipped_to_land` | The unit was clipped to land: the union of the 2020 census blocks with land area greater than zero, from the same TIGER/Line release. | every TIGER/Line level in ASM, GUM, MNP |
| `split_by_parent` | A unit that lies in two parents was split into one piece per parent. A second parent must hold at least 1% of the unit and 0.01 km² for a split to happen. | NCL: Poya, split between Province Nord and Province Sud |
| `name_corrected` | A wrong name in the source was replaced. | PLW: two states |
| `parent_by_code`, `parent_by_overlap` | How the parent was assigned. See below. | all nesting levels |

The pipeline can also write `dissolved_by_name`, `dissolved_multipart`,
`dissolved_from_parts` and `supplemented_from_alternative_source`, but none of these
occur in v0.1.0. The EEZ rows are all `as_published`; corrections to their attributes are
in `attribute_notes`.

The finest partition has its own tokens; see below.

## Parent assignment

`parent_uid` links each unit of a nesting level to a unit one level up.

* **Which level is the parent.** The nearest admin level above that exists for the
  country. Only nesting layers can be parents. If a level ever holds two parallel
  variants, the register marks which one is the parent (`parent_candidate`).
* **By code.** If the register names a parent field and the code matches a unit one
  level up, that unit is the parent (`parent_by_code`).
* **By overlap.** Otherwise the parent is the unit holding the largest share of the
  child's area, computed in EPSG:3832 (`parent_by_overlap`). For admin1, admin0 is
  always the parent.
* **Disagreements.** When the coded parent differs from the parent by overlap, the code
  is kept and the unit is counted in the processing notes. In v0.1.0 this happens for 7
  Vanuatu enumeration areas.
* **Nest check.** A level can carry a nest check, for which the default threshold is
  95%. If less than that share of the level's area lies inside the assigned parents, the
  level is marked `nests = false`. Its parent link is kept as information, but it is
  left out of the finest partition. In v0.1.0 this happens to the French Polynesia
  quartiers: only 93.6% of their area falls inside the assigned parents.
* **Non-nesting layers.** Layers with level `other` have `parent_uid = null`. A
  nesting-level layer that fails its nest check keeps its largest-overlap parent, as
  information only.

## Finest partition

`pacific_admin_finest.parquet` is built per country, in EPSG:3832, from the open
`nests = true` rows only.

1. **Start from admin0**, as one piece.
2. **Descend level by level.** At each admin level from admin1 to admin5, every current
   piece is replaced by its children. Each child is clipped to the piece. Where siblings
   overlap, the sibling with the lower `unit_code` keeps the shared area. Any part of a
   piece that no child covers stays as the coarser unit and is flagged
   `no_<level>_coverage`, for example `no_admin3_coverage`. This is how partial-coverage
   levels work, such as census units that cover populated land only, or quartiers that
   exist only in Noumea. A piece whose unit has no children at all stays at its own
   level unflagged. Pieces smaller than 1 m² are dropped.
3. **Clip to the EEZ.** Each land piece is clipped to the country's 200 NM zones (the
   SPC polygons as published). A unit that falls in more than one zone would be split
   and flagged `clipped_to_eez`; no unit does in v0.1.0. Land beyond every zone is kept,
   attached to its unit's zone, and flagged `land_outside_eez_outline`. In v0.1.0 that is
   130.6 km² of PNG enumeration-area slivers along the Indonesian land border, in 10
   pieces; the border is digitised differently in the two sources.
4. **Add the marine remainder.** For each 200 NM zone, the zone minus all land pieces
   becomes one row: `uid = {iso3}:marine:{eez_uid}`, `is_marine = true`,
   `geometry_method = eez_minus_land`.
5. **Add the shared polygons.** Each overlapping-claim and joint-regime polygon is added
   once, as a marine row under its first PICT claimant. Its `geometry_method` is
   `as_published;overlapping_claim` or `as_published;joint_regime`.
6. **Copy the ancestors.** Every land row carries the uid, name and `level_type` of each
   ancestor (`admin1_*` to `admin5_*`), the admin0 uid and name, and `source_ids`,
   `license` and `license_agreement` (joined over every level in its chain). Marine rows
   carry the EEZ source and licence.

**Area check.** For each 200 NM zone, the summed `area_km2` of its rows is compared with
the zone's domain. The domain is the SPC zone polygon plus any attached land beyond it
(130.6 km² for PNG, none elsewhere). The tolerance is 0.01%. All 24 zones pass, with a
difference of less than 0.00001%. The results are in `data/combined/partition_checks.json`.

The partition has no gaps or overlaps within a zone. However, a land piece is the part of
a unit that survived clipping to its parents, so its area can be smaller than the
unit's own `area_km2` in the long table. For example, the Vanuatu enumeration areas that
lie outside their coded area council are clipped away. Use the long table when you need
a unit's full published polygon, and the finest partition when you need a clean
partition.

## Licence handling

* Each source's licence is recorded in its register entry: name, URL,
  `redistribution_ok`, an optional `agreement`, and notes. Rows inherit `license`,
  `license_url` and `license_agreement` from their source.
* **Agreements.** The SPC Pacific Maritime Boundaries polygons and the Cook Islands SPC
  PCRAFI layers are published by SPC under CC BY-NC-SA 4.0. This project uses and
  redistributes them under a data use agreement between CSDR and SPC. Their register
  entries carry `redistribution_ok: true` and the agreement, so their rows are published
  with `license = CC-BY-NC-SA-4.0` and the agreement named in `license_agreement`. The
  agreement covers this project only; downstream users are bound by CC BY-NC-SA 4.0
  unless they hold their own agreement. The LINZ layers are CC BY 4.0 and need no
  agreement.
* `license_restricted = true` when a source's `redistribution_ok` is anything other than
  `true`, including unknown. Such rows would be written only to a local
  `<iso3>_admin_restricted.parquet` and never published. There are none in v0.1.0.
* Sources whose licence forbids redistribution (GADM), and non-commercial sources without
  an agreement, were not processed. They appear only as `reference`, `alternative` or
  `rejected` entries in the registers.
* Share-alike sources (ODbL-1.0, CC-BY-SA-3.0, CC-BY-NC-SA-4.0) can be found through
  `license`. Redistributing those rows brings the share-alike terms with them.
* The STAC items list the licences (`pab:licenses`, `license` links) and agreements
  (`pab:license_agreements`) of each file.

## Provenance

The chain from a published row back to the original bytes is:

1. **The row**: `source_id`, `source_url`, `source_version`, `source_date`,
   `retrieved_at`, `license`, `license_url`, `license_agreement`, `geometry_method`, and
   in the EEZ file `boundary_source` and `attribute_notes`.
2. **The source register** (`config/sources/<ISO3>.yml`): the full description of the
   source, including the alternatives considered and the decision for each level.
3. **The raw manifest** (`data/raw/<ISO3>/<source_id>/manifest.json`): the retrieval time,
   URLs, and the size and sha256 of every downloaded and extracted file.
4. **`provenance.json`**, in each `data/processed/<ISO3>/`, `data/processed/EEZ/` and
   `data/combined/`, holds one record per stage (`process`, `assign-eez`, `process-eez`,
   `combine`). Each record lists:
   * the command run, its inputs (register, raw manifests, upstream tables) and outputs
     (paths, row counts);
   * the completion time;
   * the software versions (pab, Python, GeoPandas, Shapely, pyogrio, GDAL, pyproj,
     PROJ, pyarrow, pystac);
   * the git commit.

   Re-running a stage replaces its record.
5. **The STAC item** next to each file. It links the data asset, its `provenance.json`,
   the raw manifests of every contributing source (on GitHub, as `metadata` assets), the
   source landing pages (`via` links), the source licences (`license` links) and the
   country's section of [sources.md](sources.md) on GitHub (`about`). It also carries
   `sci:citation`, `providers`, `processing:software`, `processing:lineage`,
   `table:columns`, `table:row_count`, `pab:source_ids`, `pab:licenses`,
   `pab:license_agreements` and `version`.

v0.1.0 was built before the first git commit, so `git_commit` is null in its provenance
records. Later releases will carry the commit hash.

## Reproducing the build

```bash
uv sync
uv run pab validate

# 1. raw data: pab cache fetches exactly the sources the process stage reads.
#    The manifests are tracked in git, so on a fresh clone pab cache would skip every
#    source; pass --overwrite to download again.
uv run pab cache EEZ --overwrite
uv run pab cache --all --overwrite   # the 3 LINZ sources need LINZ_API_KEY (below)
git diff -- data/raw    # changed sha256 values mean a source has changed since v0.1.0

# 2. build
uv run pab process EEZ --overwrite
uv run pab process --all --overwrite
uv run pab assign-eez --all
uv run pab combine
make stac           # pab stac --base-url <https_base> --check
uv run pab qa --all
```

Notes:

* **LINZ layers need an API key.** Get a free key from the LINZ Data Service and set
  `LINZ_API_KEY` in the environment or in a local `.env` file (gitignored); `pab cache`
  sends it as the `Authorization` header and fails with a clear message if it is missing.
* **Raw data are not published.** To rebuild, re-download from the sources. Sources can
  change after retrieval; the geoBoundaries API, for example, serves the "current"
  release. Compare the new sha256 values with the manifests in git to see what changed.
* `make cache`, `make cache-eez` and `make cache-all` run `pab cache` without
  `--overwrite`, so they only fill in sources that have no manifest yet.
* Rebuilt files should match v0.1.0 in rows, codes and geometry. They will differ in
  timestamps such as `processing:datetime` and `completed_at`.
* Sources marked `retrieval_method: manual` in a register cannot be fetched by
  `pab cache`; none of them is used in v0.1.0.
