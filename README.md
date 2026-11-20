# Pacific administrative boundaries

Harmonised jurisdictional and administrative boundaries for the 22 Pacific Island
countries and territories (PICTs), from the Exclusive Economic Zone (EEZ) down to the
finest level that is publicly available, as GeoParquet with STAC metadata.

Every unit carries its source, licence, publication date, retrieval date and the
processing steps applied to its geometry, so the data can be used in provenance-tracked
workflows. The code that downloads, processes and packages the data is in this
repository.

**Status:** v0.1.0 (2026-11-20), first release. See [CHANGELOG.md](CHANGELOG.md).

## Scope

| ISO3 | Country or territory | ISO3 | Country or territory |
|---|---|---|---|
| ASM | American Samoa | NRU | Nauru |
| COK | Cook Islands | NCL | New Caledonia |
| FSM | Micronesia (Federated States of) | NIU | Niue |
| FJI | Fiji | MNP | Northern Mariana Islands |
| PYF | French Polynesia | PLW | Palau |
| GUM | Guam | PNG | Papua New Guinea |
| KIR | Kiribati | PCN | Pitcairn Islands |
| MHL | Marshall Islands | WSM | Samoa |
| SLB | Solomon Islands | TKL | Tokelau |
| TON | Tonga | TUV | Tuvalu |
| VUT | Vanuatu | WLF | Wallis and Futuna |

For each one the dataset holds the EEZ (SPC Pacific Maritime Boundaries), the land boundary (admin0)
and every open subnational layer that was found: provinces, districts, local
governments, villages, census enumeration areas, and non-nesting layers such as
electorates, customary areas and US census tracts. [docs/sources.md](docs/sources.md)
lists what was used for each country and what is missing.

## Products

| Product | Path | Rows | Size |
|---|---|---|---|
| Per-country long tables (22 files) | `data/processed/<ISO3>/<iso3>_admin.parquet` | 14,231 in total | 0.1 to 100 MB each |
| EEZ polygons | `data/processed/EEZ/pacific_eez.parquet` | 27 | 1.2 MB |
| Pacific long table | `data/combined/pacific_admin.parquet` | 14,231 | 224 MB |
| Pacific finest partition | `data/combined/pacific_admin_finest.parquet` | 8,199 | 106 MB |
| STAC catalog | `data/catalog.json`, `data/collection.json`, `*.stac-item.json` next to each file | 25 items | |

* The **long tables** have one row per unit per level, with all levels stacked. To get
  any level across the region, filter or group on `level_code` or `level_type`.
* The **finest partition** splits each EEZ into non-overlapping pieces. Each land piece
  is the finest nesting unit available at that location, and carries the uid and name of
  every ancestor level (`admin0_*` to `admin5_*`). Each EEZ also has one marine row: the
  EEZ minus land. To rebuild any level, dissolve on its ancestor columns.
* The EEZ rows are the full 200 NM zones as SPC publishes them, with land inside.
  `pacific_eez.parquet` gives each zone's `land_km2` and `marine_km2`.

All files are GeoParquet 1.1 in EPSG:4326, with MultiPolygon geometry, a `bbox` covering
column and zstd compression. Rows are sorted by country, and each country has its own row
groups, so readers that filter on `iso3` only read that country's part of the file.
Geometries that cross the antimeridian are split at 180°.
For the full column dictionary, see [docs/data_structure.md](docs/data_structure.md).

## Level model in brief

Each row has three level descriptors:

* `level_code`: `eez`, `admin0` to `admin5`, or `other`. These are assigned per country,
  from the top down, so `admin1` is always the first subdivision below the national
  boundary, whatever the country calls it. `other` holds layers that do not nest, such as
  electorates, customary areas, islands and census tracts.
* `level_type`: a harmonised category for comparing like with like across countries:
  `eez`, `country`, `region`, `state_province`, `district`, `local_government`,
  `ward_village`, `island`, `statistical`, `electoral`, `customary`.
* `level_name_local`: what the country calls the level, for example "Tikina",
  "Local Level Government (LLG)", "Commune associee" or "Island (Kaupule)".

`nests = true` marks layers that are strict subdivisions of the level above. Only these
layers are used in the finest partition. Each unit's `parent_uid` points to the unit one
level up. The full specification is in [docs/data_model.md](docs/data_model.md).

## Quick start

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or later. The pipeline was
built and tested with Python 3.12.

```bash
git clone <repository-url> pacific_administrative_boundaries
cd pacific_administrative_boundaries
uv sync                 # create the environment from uv.lock
uv run pab --help       # pipeline CLI
make help               # list the make targets
```

The data files are not in git; only the raw manifests, provenance and STAC JSON are.
Either read the files from S3, at `s3://csdr-public-datasets/pacific-administrative-boundaries/`
(STAC root `catalog.json`; see [docs/usage.md](docs/usage.md) and
[docs/publishing.md](docs/publishing.md)), or rebuild them. Rebuilding means re-downloading the raw
sources with `pab cache ... --overwrite` and then running `make all` (EEZ, countries, EEZ
assignment, combine, STAC, QA). The exact commands are in
[docs/methods.md](docs/methods.md#reproducing-the-build).

Three short examples follow. They were run against v0.1.0, and more are in
[docs/usage.md](docs/usage.md).

Get one country and one level with geopandas:

```python
import geopandas as gpd

fji = gpd.read_parquet(
    "data/combined/pacific_admin.parquet", filters=[("iso3", "==", "FJI")]
)
tikina = fji[fji["level_code"] == "admin3"]  # 86 tikina
```

Count units by harmonised level type with DuckDB:

```sql
SELECT level_type, count(*) AS units, count(DISTINCT iso3) AS countries
FROM 'data/combined/pacific_admin.parquet'
GROUP BY level_type
ORDER BY units DESC;
```

Rebuild admin1 by dissolving the finest partition:

```python
import geopandas as gpd

fin = gpd.read_parquet(
    "data/combined/pacific_admin_finest.parquet", filters=[("iso3", "==", "VUT")]
)
provinces = fin[~fin["is_marine"]].dissolve(
    by=["admin1_uid", "admin1_name"], as_index=False
)
```

## Documentation

| Document | Contents |
|---|---|
| [docs/sources.md](docs/sources.md) | Sources by country and level, licences, retrieval dates, alternatives considered, gaps |
| [docs/methods.md](docs/methods.md) | Pipeline stages, geometry rules, derivations, parent assignment, finest partition, provenance, how to reproduce |
| [docs/data_structure.md](docs/data_structure.md) | Folder layout, file naming, column dictionaries, STAC layout, S3 layout, file sizes |
| [docs/usage.md](docs/usage.md) | Worked examples in Python, DuckDB and R |
| [docs/caveats.md](docs/caveats.md) | Known limitations, global and by country |
| [docs/decisions.md](docs/decisions.md) | Index of the decision IDs cited in registers, code and the spec |
| [docs/data_model.md](docs/data_model.md) | Technical specification (the contract the pipeline follows) |
| [docs/publishing.md](docs/publishing.md) | What is published on GitHub and S3, and how |

## Licence

* **Code** (everything under `pab/`, `scripts/`, `tests/`, plus the Makefile and
  configuration) is licensed under Apache-2.0. See [LICENSE](LICENSE).
* **Data** keep the licence of their source. Each row records it in `license`, with
  `license_url`. Most land boundaries are CC BY 4.0, CC BY 3.0 IGO, US public domain or
  Licence Ouverte 2.0. See [docs/sources.md](docs/sources.md).
* **EEZ and other SPC layers: non-commercial.** The EEZ polygons come from the SPC Pacific
  Maritime Boundaries dataset, and the Cook Islands electoral constituencies from SPC
  PCRAFI. Both are published by SPC under CC BY-NC-SA 4.0. This project uses and
  redistributes them under a data use agreement between CSDR and SPC, and names that
  agreement in `license_agreement`. **The agreement does not extend to you.** Unless you
  hold your own agreement with SPC, CC BY-NC-SA 4.0 applies to every row with
  `license = CC-BY-NC-SA-4.0`: the 26 SPC EEZ rows, the 24 Cook Islands electoral
  constituencies, and the marine rows of the finest partition. In practice that means no
  commercial use, attribution to SPC, and share-alike for derivatives. Filter on
  `license` to work with the other rows only. The Torres Strait joint regime and the
  Wake Island / Enenkio claim come from Marine Regions (CC BY 4.0).
* **Share-alike sources:** the French Polynesia Quartiers 2000 (ODbL-1.0) and the Samoa
  itumalo (CC BY-SA 3.0).
* GADM was used for reference only and is not in any product. Raw downloads are not
  redistributed.
* If you use the data, attribute the original publishers as well as this dataset. The
  STAC items list the sources behind each file in `sci:citation`.

## Citation

Cite this dataset using [CITATION.cff](CITATION.cff) (on GitHub, use "Cite this
repository"). Also cite the sources you rely on. At minimum, cite SPC for the EEZs: Pacific
Community (SPC), Pacific Maritime Boundaries, "Global Exclusive Economic Zones (200
Nautical Miles) - Merged Dataset", Pacific Data Hub (2025). Cite Marine Regions
(https://doi.org/10.14284/632) if you use the Torres Strait or Wake Island rows.
