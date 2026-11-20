# Changelog

This project follows [Semantic Versioning](https://semver.org/). Data are published on S3
at `s3://csdr-public-datasets/pacific-administrative-boundaries/`. Each release is a git
tag, and the release version is recorded in every STAC item (see
[docs/publishing.md](docs/publishing.md)).

## v0.1.0 (2026-11-20)

First release.

### Data

* Boundaries for all 22 Pacific Island countries and territories (ASM, COK, FJI, FSM,
  GUM, KIR, MHL, MNP, NCL, NIU, NRU, PCN, PLW, PNG, PYF, SLB, TKL, TON, TUV, VUT, WLF,
  WSM). Each has its EEZ, its admin0, and every open subnational layer found. The
  deepest is admin5 (Tonga census units).
* EEZ base layer: the SPC Pacific Maritime Boundaries polygons (CC BY-NC-SA 4.0, used
  under a CSDR-SPC data use agreement). They are the full 200 NM zones, with land inside.
  The Torres Strait joint regime and the Wake Island / Enenkio overlapping claim come from
  Marine Regions v12 (CC BY 4.0).
* Cook Islands, Niue and Tokelau land outlines come from the LINZ Data Service Topo50
  layers (CC BY 4.0). The Cook Islands 2010 electoral constituencies (SPC PCRAFI) are
  published under the SPC agreement.
* 22 per-country long tables, `data/processed/<ISO3>/<iso3>_admin.parquet`, with 14,231
  rows in total.
* EEZ polygons, `data/processed/EEZ/pacific_eez.parquet`, with 27 rows and `land_km2`,
  `marine_km2`, `boundary_source` and `attribute_notes` columns.
* Pacific long table, `data/combined/pacific_admin.parquet`, with 14,231 rows.
* Pacific finest partition, `data/combined/pacific_admin_finest.parquet`, with 8,199
  rows. All 24 EEZ zones pass the area check, against a 0.01% tolerance.
* Harmonised level model: `level_code`, `level_type`, `level_name_local` and `nests`.
* Per-row provenance (`source_*`, `retrieved_at`, `license`, `license_url`,
  `license_agreement`, `license_restricted`, `geometry_method`), with one licence value
  per row. No row is licence-restricted.
* Files are GeoParquet 1.1 with zstd compression and a bbox covering column. Row groups
  are split by country.
* STAC 1.1.0 catalog with 25 items. The root `catalog.json` and `collection.json` are at
  the top of the published tree. Items link to GitHub for full provenance.
* Raw manifests with sha256 checksums for 128 source folders. Raw data are not
  published.

### Code

* `pab` pipeline and CLI: `validate`, `cache`, `process`, `assign-eez`, `combine`,
  `stac` (with `--base-url` and `--check`), `publish` (with `--dry-run` and `--verify`),
  and `qa`. Make targets wrap each stage.
* `pab cache` fetches exactly the sources that processing reads.
* Register option `clip_to` clips a level to another source's coastline.
* 42 tests (`pytest`), plus CI running ruff and pytest.

### Known limitations

See [docs/caveats.md](docs/caveats.md). The main ones:

* SPC EEZ rows are CC BY-NC-SA 4.0 for downstream users without their own agreement
  with SPC.
* Census vintages range from 2009 to 2021.
* The finest levels in COK, KIR, TUV and WLF cover populated land only.
* `pab cache` cannot re-download the LINZ layers, which need an API key.
* `git_commit` is null in the v0.1.0 provenance records, because the build ran before
  the first commit.
* The GitHub repository URL in `config/publish.yml` is provisional.
