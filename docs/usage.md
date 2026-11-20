# Usage

These are worked examples for the v0.1.0 files. Paths are relative to the repository
root. Every Python, SQL and R snippet on this page was run against the local v0.1.0
files, except the ones marked **template** in [Reading from S3 or HTTP](#reading-from-s3-or-http).

The examples were tested with GeoPandas 1.2, pyarrow 26, DuckDB 1.4 with its `spatial`
extension, and R 4 with `arrow` and `dplyr`. All the Python dependencies are in the uv
environment (`uv sync`). Run the Python examples with `uv run python`.

Choosing a file:

| You want | Read |
|---|---|
| Any level, for one country or across the Pacific, as published | `data/combined/pacific_admin.parquet` |
| Everything for one country, in one small file | `data/processed/<ISO3>/<iso3>_admin.parquet` |
| A gap-free tiling of land and sea, to aggregate or rebuild levels | `data/combined/pacific_admin_finest.parquet` |
| EEZ polygons only, with their legal sources, land and marine areas | `data/processed/EEZ/pacific_eez.parquet` |

## Load one country

```python
import geopandas as gpd

# Option A: the per-country file (all levels of one country)
fji = gpd.read_parquet("data/processed/FJI/fji_admin.parquet")
print(fji.groupby(["level_code", "level_name_local"]).size())

# Option B: one country from the combined table, filtered while reading
fji = gpd.read_parquet(
    "data/combined/pacific_admin.parquet",
    filters=[("iso3", "==", "FJI")],
)
tikina = fji[fji["level_code"] == "admin3"]
print(len(tikina), tikina.crs.to_epsg())  # 86 4326
```

Each country has its own row groups, so a filter on `iso3` reads only that country's
part of the file.

To select by area instead, use the `bbox` covering column:

```python
import geopandas as gpd

# Everything whose bounding box intersects Viti Levu (uses the bbox covering column)
viti = gpd.read_parquet(
    "data/combined/pacific_admin.parquet", bbox=(177.2, -18.3, 178.8, -17.2)
)
print(viti.groupby(["iso3", "level_code"]).size())
```

A bbox filter tests bounding boxes, not geometries. Units that cross the antimeridian,
such as the Fiji admin0 and EEZ, have a bbox from -180 to 180, so they match any query
at their latitude.

## All local-government units across the Pacific

Use `level_type`, not `level_code`, to compare across countries. The same category sits
at different levels in different countries.

```python
import geopandas as gpd

lg = gpd.read_parquet(
    "data/combined/pacific_admin.parquet",
    columns=[
        "uid",
        "iso3",
        "level_code",
        "level_name_local",
        "unit_name",
        "level_type",
        "geometry",
    ],
    filters=[("level_type", "==", "local_government")],
)
print(lg.groupby(["iso3", "level_code", "level_name_local"]).size())
```

This returns 572 units in 7 countries: FSM municipalities (admin2), GUM villages (admin1),
MNP municipalities (admin1), NCL communes (admin2), PNG LLGs (admin4), PYF communes
(admin2), and VUT area councils and municipalities (admin2).

Several countries have local governments under another `level_type`:

* the island councils of Kiribati, Tuvalu and the Marshall Islands are `island`;
* the Niue villages are `ward_village`.

Check `level_name_local`, and the [summary table in sources.md](sources.md#summary),
before you draw conclusions from a single category.

The same query in DuckDB, plus a count by `level_type`:

```sql
SELECT level_type, count(*) AS units, count(DISTINCT iso3) AS countries
FROM 'data/combined/pacific_admin.parquet'
GROUP BY level_type
ORDER BY units DESC;

SELECT iso3, level_code, level_name_local, count(*) AS units
FROM 'data/combined/pacific_admin.parquet'
WHERE level_type = 'local_government'
GROUP BY ALL
ORDER BY iso3, level_code;
```

The same filter in R, with `arrow`. This reads attributes only, without geometry:

```r
library(arrow)
library(dplyr)

ds <- open_dataset("data/combined/pacific_admin.parquet")
lg <- ds |>
  filter(level_type == "local_government") |>
  select(uid, iso3, level_code, level_name_local, unit_name, unit_code, area_km2) |>
  collect()
count(lg, iso3, level_name_local)
```

For geometry in R, `sf::st_read()` can read GeoParquet if your GDAL (3.8 or later) was
built with the Parquet driver. That route was not tested for this release.

## Rebuild a level by dissolving the finest partition

Every land row in the finest partition carries its ancestors, so dissolving on an
ancestor column gives that level, without gaps or overlaps:

```python
import geopandas as gpd

fin = gpd.read_parquet(
    "data/combined/pacific_admin_finest.parquet",
    filters=[("iso3", "==", "VUT")],
)
land = fin[~fin["is_marine"]]

# Rebuild admin1 (provinces) by dissolving the finest units on the admin1 columns
prov = land.dissolve(by=["admin1_uid", "admin1_name"], as_index=False)
prov["area_km2"] = prov.to_crs("EPSG:6933").area / 1e6
print(prov[["admin1_uid", "admin1_name", "area_km2"]])

# Compare with the published admin1 rows of the long table
long = gpd.read_parquet(
    "data/combined/pacific_admin.parquet",
    filters=[("iso3", "==", "VUT"), ("level_code", "==", "admin1")],
)
print(long[["uid", "unit_name", "area_km2"]])
```

The two areas match for the Vanuatu provinces.

For the whole region at once, use `dropna=False`. Two land pieces have no admin1, and
would otherwise be dropped: Pitcairn, and 0.6 km² of Niue that lies outside its villages.
`dropna=False` keeps them, as two null-admin1 rows:

```python
import geopandas as gpd

fin = gpd.read_parquet("data/combined/pacific_admin_finest.parquet")
land = fin[~fin["is_marine"]]
admin1 = land.dissolve(by=["iso3", "admin1_uid"], as_index=False, dropna=False)
print(len(admin1), admin1["admin1_uid"].isna().sum())  # 165 2
```

Pieces split at the antimeridian remain separate parts after a dissolve in EPSG:4326.
That is the correct storage form; see [Antimeridian](#antimeridian) for plotting.

The same dissolve in DuckDB, with summed areas:

```sql
INSTALL spatial;
LOAD spatial;
SELECT iso3, admin1_name, round(sum(area_km2), 1) AS km2, ST_Union_Agg(geometry) AS geometry
FROM 'data/combined/pacific_admin_finest.parquet'
WHERE iso3 = 'SLB' AND NOT is_marine
GROUP BY ALL
ORDER BY admin1_name;
```

To see which finest level each country reaches, and where the partition falls back to a
coarser level:

```sql
SELECT iso3, finest_level_code, count(*) AS pieces, round(sum(area_km2), 1) AS land_km2
FROM 'data/combined/pacific_admin_finest.parquet'
WHERE NOT is_marine
GROUP BY ALL
ORDER BY iso3, finest_level_code;
```

## Join your own tables

Join on `uid` when you can. It is unique across the whole dataset. If your table has the
source's codes, either build the uid from them or join on `unit_code` within one country
and level. Codes are only unique within a level of a country.

```python
import geopandas as gpd
import pandas as pd

# Your own table, keyed by the source codes of Tonga's villages (admin3)
pop = pd.DataFrame({"village_code": ["1101", "1102"], "households": [120, 85]})

ton = gpd.read_parquet(
    "data/combined/pacific_admin.parquet",
    filters=[("iso3", "==", "TON"), ("level_code", "==", "admin3")],
)
# Either build the uid ...
pop["uid"] = "TON:admin3:" + pop["village_code"]
joined = ton.merge(pop, on="uid", how="left")
# ... or join on unit_code within one country and level
joined2 = ton.merge(pop, left_on="unit_code", right_on="village_code", how="left")
print(joined.loc[joined["households"].notna(), ["uid", "unit_name", "households"]])
```

Points to check before joining:

* `unit_code` is a string. Keep leading zeros in your own codes.
* `code_scheme` tells you what the codes are, for example `pcode`, `insee`, `fips` or
  `sdd-census`. Census tables from national statistics offices usually use the same
  census codes (`sdd-census`, `tsd-census` and so on). Where a country also has an OCHA
  COD-AB with P-codes that were not used here (FJI, FSM, SLB, TON, VUT), P-codes must be
  matched by name. [sources.md](sources.md) names the alternative that carries them.
* Census geography vintages differ by country (2009 to 2021). A table from a newer census
  may not match these units; see [caveats.md](caveats.md).

## Licences: non-commercial rows

Most rows are openly licensed. The exceptions are the SPC rows, licensed CC BY-NC-SA 4.0
and redistributed by this project under a data use agreement with SPC: the EEZ polygons,
the marine rows of the finest partition, and the Cook Islands electoral constituencies.
Unless you hold your own agreement with SPC, CC BY-NC-SA 4.0 applies to them. If your use
is commercial, or you cannot accept share-alike, leave them out:

```python
import geopandas as gpd

pac = gpd.read_parquet("data/combined/pacific_admin.parquet")
print(pac.groupby(["license", "license_agreement"], dropna=False).size())

open_rows = pac[pac["license"] != "CC-BY-NC-SA-4.0"]
print(len(pac), len(open_rows))  # 14231 14181
```

The same check in DuckDB, including the finest partition, whose `license` lists the
licences of every level in a piece's chain:

```sql
SELECT license, count(*) AS rows
FROM 'data/combined/pacific_admin_finest.parquet'
GROUP BY license
ORDER BY rows DESC;
```

Share-alike rows can be found with `license IN ('ODbL-1.0', 'CC-BY-SA-3.0',
'CC-BY-NC-SA-4.0')`. No row is licence-restricted; `license_restricted` is false
everywhere.

## EEZ land and marine areas

The SPC EEZ polygons include land, so an EEZ row's `area_km2` is the whole 200 NM zone.
`pacific_eez.parquet` splits it into land and sea:

```python
import geopandas as gpd

eez = gpd.read_parquet("data/processed/EEZ/pacific_eez.parquet")
zones = eez[
    eez["pol_type"] == "200NM"
]  # leave out overlapping claims and joint regimes
print(zones[["uid", "area_km2", "land_km2", "marine_km2"]].round(1).head())
print(round(zones["marine_km2"].sum()))  # total marine area of the 24 zones, km2
print(eez.loc[eez["attribute_notes"].notna(), ["uid", "attribute_notes"]])
```

## Antimeridian

Fiji, the Kiribati Gilbert Islands EEZ and the Tuvalu EEZ cross 180°. They are stored
split at ±180°, so in plain longitude/latitude they appear at both edges of a map.
There are two ways to handle this when plotting:

* reproject to a Pacific-centred CRS, such as EPSG:3832 (PDC Mercator, centred on 150°E);
* shift negative longitudes by +360.

```python
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

eez = gpd.read_parquet("data/processed/EEZ/pacific_eez.parquet")

# EPSG:3832 (PDC Mercator, centred on 150 E) keeps the Pacific in one piece
ax = eez.to_crs("EPSG:3832").plot(
    column="iso3", edgecolor="white", linewidth=0.3, figsize=(10, 6)
)
ax.set_axis_off()
plt.savefig("pacific_eez.png", dpi=150, bbox_inches="tight")

# Alternative for lon/lat plots: shift negative longitudes by +360
import shapely


def to_0_360(geom):
    return shapely.transform(geom, lambda xy: xy + [[360, 0]] * (xy[:, :1] < 0))


fji = gpd.read_parquet(
    "data/combined/pacific_admin.parquet",
    filters=[("iso3", "==", "FJI"), ("level_code", "==", "admin2")],
)
fji_shifted = fji.set_geometry(fji.geometry.map(to_0_360))
print(fji.total_bounds, fji_shifted.total_bounds)
fji_shifted.plot()
plt.savefig("fiji_provinces.png")
```

The split stays visible as a thin line where polygon edges are drawn. To remove it,
dissolve the parts in EPSG:3832 before plotting.

Do any overlay or buffer work in a projected CRS such as EPSG:3832, not in EPSG:4326.
Area is already provided in `area_km2`.

## Reading from S3 or HTTP

The data are published at `s3://csdr-public-datasets/pacific-administrative-boundaries/`,
which is also served over HTTPS at
`https://csdr-public-datasets.s3.ap-southeast-2.amazonaws.com/pacific-administrative-boundaries/`. The
layout mirrors the repository's `data/` folder, without the `data/` prefix:
`data/combined/x.parquet` is `<prefix>/combined/x.parquet`. So any example above works
once the local path is swapped for the URL.

The remote snippets below are **templates**. They have not been run, because the bucket
was not yet public when these docs were written. The STAC example was run against the
local catalog.

**Template**, DuckDB over HTTPS:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT iso3, level_code, count(*)
FROM read_parquet('https://csdr-public-datasets.s3.ap-southeast-2.amazonaws.com/pacific-administrative-boundaries/combined/pacific_admin.parquet')
WHERE iso3 = 'WSM'
GROUP BY ALL;
```

**Template**, GeoPandas with pyarrow's S3 filesystem. The bucket is in
`ap-southeast-2`:

```python
import geopandas as gpd
from pyarrow import fs

s3 = fs.S3FileSystem(anonymous=True, region="ap-southeast-2")
wsm = gpd.read_parquet(
    "csdr-public-datasets/pacific-administrative-boundaries/combined/pacific_admin.parquet",
    filesystem=s3,
    filters=[("iso3", "==", "WSM")],
)
```

STAC with pystac. This was run on the local catalog, `data/catalog.json`; for the
published catalog, use the URL in the comment:

```python
import pystac

# published: "https://csdr-public-datasets.s3.ap-southeast-2.amazonaws.com/pacific-administrative-boundaries/catalog.json"
cat = pystac.Catalog.from_file("data/catalog.json")
items = list(cat.get_items(recursive=True))
print(len(items))  # 25
for item in items[:3]:
    print(item.id, item.properties["pab:licenses"], item.assets["data"].href)
```

In the published build, asset hrefs are absolute HTTPS URLs, with an `s3://` alternate.
Because each country has its own row groups, remote readers fetch only the byte ranges
for the countries you filter on.

## Provenance in your own workflow

To record exactly what you used, keep these:

* the file URL and the release version (`v0.1.0`);
* the STAC item id, for example `pab-pacific-admin`;
* for each row: `uid`, `source_id`, `source_version`, `source_date`, `retrieved_at`,
  `license`, `license_url`, `license_agreement` and `geometry_method`.

The `source_id` leads to the source register (`config/sources/<ISO3>.yml`) and to the raw
manifest with checksums (`data/raw/<ISO3>/<source_id>/manifest.json`). Both are in the
GitHub repository, and each STAC item links to them.
