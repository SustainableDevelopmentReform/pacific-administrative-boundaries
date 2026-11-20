# Sources

This page lists, for each country and territory, which source was used for each boundary
level, under what licence, and when it was retrieved. It also lists the alternatives that
were considered, why they were not used, and the levels for which no public data were
found.

The machine-readable versions are:

* the source registers, `config/sources/<ISO3>.yml` and `config/sources/EEZ.yml`, which
  hold every candidate source with its status, licence, download URLs and notes;
* the raw manifests, `data/raw/<ISO3>/<source_id>/manifest.json`, which give the
  retrieval time, URLs, byte sizes and sha256 of every downloaded and extracted file;
* the `source_*`, `license`, `license_url`, `license_agreement` and `retrieved_at`
  columns, which are on every row of the data.

How sources were chosen, from most to least preferred:

1. the official national or territorial agency, including copies hosted by SPC on the
   Pacific Data Hub, with an open licence;
2. the UN OCHA Common Operational Datasets (COD-AB);
3. geoBoundaries;
4. official sources of the administering state (US Census TIGER/Line, French territorial
   agencies, LINZ);
5. OpenStreetMap;
6. GADM, which was used for reference only;
7. Natural Earth.

Within a tier, the most recent publication wins. Some cases were exceptions, and each
country section gives the reason.

Licences in the tables are the exact values of the `license` column. Each row has
exactly one value, and its `license_url` column gives the licence URL. The values used in
v0.1.0 are:

* `CC-BY-4.0`, `CC-BY-3.0-IGO`, `CC-BY-SA-3.0`, `ODbL-1.0` (SPDX identifiers);
* `LO-2.0` (Licence Ouverte / Open Licence 2.0, Etalab);
* `Public domain (US Government work)` (US Census TIGER/Line);
* `Public domain` (geoBoundaries Nauru districts);
* `PacIOOS data use (free redistribution, not for legal use)`;
* `CC-BY-NC-SA-4.0`: the SPC Pacific Maritime Boundaries EEZ polygons (26 rows) and the
  Cook Islands SPC PCRAFI electoral constituencies (24 rows).

**Data use agreement.** The SPC CC-BY-NC-SA-4.0 layers are used and redistributed by this
project under a data use agreement between CSDR and SPC. Their rows carry
`license_agreement = CSDR-SPC data use agreement (user-confirmed 2026-11-20)`. The
agreement covers this project only. Unless you hold your own agreement with SPC, CC BY-NC-SA
4.0 applies to those rows: attribution, no commercial use, and share-alike for
derivatives. The LINZ layers are CC BY 4.0 and need no agreement.

**Assumption:** several SPC census boundary sets on the Pacific Data Hub state only
"CC-BY" (Creative Commons Attribution), without a version. These are recorded as
`CC-BY-4.0`. They are the Fiji, Cook Islands, FSM, Kiribati, Nauru, Niue, Palau, Samoa,
Solomon Islands, Tonga, Tuvalu, Vanuatu and Wallis and Futuna census sets. If the version
matters for your use, check the dataset page.

Several kinds of source were not used in any product:

* GADM, whose licence prohibits redistribution;
* the SPC GEM / PCRAFI hazard-loss ("AAL") layers, which are derivatives of census
  geography already used here;
* layers licensed only by "direct permission".

## Summary

| ISO3 | Levels below admin0 (units) | Finest nesting level | Main sources (data vintage) | Licences |
|---|---|---|---|---|
| ASM | District (5) > County (16) > Village (77); census tracts, block groups, blocks (non-nesting) | Village | US Census TIGER/Line 2026 (2020 census blocks) | Public domain (US Government work) |
| COK | Group (3) > Island (15) > Census district (44) > Enumeration area (134); 2010 electoral constituencies (24, non-nesting) | Enumeration area (populated land only) | LINZ Topo50 islands 2022 + SPC/Cook Islands Statistics 2011 census + SPC PCRAFI 2010 electorates | CC-BY-4.0; CC-BY-NC-SA-4.0 for electorates (SPC agreement) |
| FJI | Division (4) > Province (15) > Tikina (86) > Enumeration area (1,980) | Enumeration area | SPC/Fiji Bureau of Statistics 2017 census | CC-BY-4.0 |
| FSM | State (4) > Municipality (75) > Enumeration district (394) | Enumeration district | SPC/FSM Division of Statistics 2010 census | CC-BY-4.0 |
| GUM | Village (19); census designated places, tracts, block groups, blocks (non-nesting) | Village | US Census TIGER/Line 2025 | Public domain (US Government work) |
| KIR | Island group (3) > Island (36) > Village (183) > Enumeration area (391) | Enumeration area (inhabited islands) | OCHA COD-AB 2020 + SPC/KNSO 2018 household listing | CC-BY-3.0-IGO, CC-BY-4.0 |
| MHL | Atoll/island local government (25) > Enumeration area (152); villages (49, non-nesting) | Enumeration area | OCHA COD-AB (2021 census) + USAID/PacIOOS villages | CC-BY-3.0-IGO, PacIOOS data use |
| MNP | Municipality (4) > District (8) > Village (135); census tracts, block groups, blocks (non-nesting) | Village | US Census TIGER/Line 2025 | Public domain (US Government work) |
| NCL | Province (3) > Commune (34) > Quartier (37, Noumea only); aires coutumieres (8, non-nesting) | Commune; quartier in Noumea | Gouvernement de la Nouvelle-Caledonie 2024, Ville de Noumea 2025 | LO-2.0 |
| NIU | Village (14) | Village | LINZ Topo50 outline 2022 + SPC/Niue Statistics 2011 census villages | CC-BY-4.0 |
| NRU | District (14); enumeration areas (47, non-nesting) | District | geoBoundaries 2023 + SPC/Nauru Bureau of Statistics 2011 census | Public domain, CC-BY-4.0 |
| PCN | none | admin0 | geoBoundaries 2021 + Natural Earth | CC-BY-4.0 (Natural Earth parts are public domain) |
| PLW | State (16) > Hamlet (77) > Enumeration area (141); groups of states (7, non-nesting) | Enumeration area | SPC/Palau Office of Planning and Statistics 2015 census | CC-BY-4.0 |
| PNG | Region (4) > Province (22) > District (87) > LLG (326) | Local Level Government | OCHA COD-AB 2019 (PNG NSO geometry) + NSO 2015 regions | CC-BY-3.0-IGO |
| PYF | Subdivision (5) > Commune (48) > Commune associee (116); Quartiers 2000 (170) and islands (128), non-nesting | Commune associee | DAF 2022 + ISPF 2022 | CC-BY-4.0; ODbL-1.0 for quartiers |
| SLB | Province (10) > Constituency (50) > Ward (183) > Enumeration area (1,344) | Enumeration area | SPC/Solomon Islands NSO 2009 census | CC-BY-4.0 |
| TKL | Atoll (3) | Atoll | LINZ Topo50 islets 2022 (split by atoll) | CC-BY-4.0 |
| TON | Division (5) > District (23) > Village (167) > Census block (389) > Census unit (843); constituencies (17, non-nesting) | Census unit | SPC/Tonga Statistics Department 2021 census | CC-BY-4.0 |
| TUV | Island (9) > Village (34) > Enumeration area (70) | Enumeration area | SPC/Tuvalu Central Statistics Division 2017 census | CC-BY-4.0 |
| VUT | Province (6) > Area council (66) > Enumeration area (929); islands (91, non-nesting) | Enumeration area | SPC/Vanuatu Bureau of Statistics 2016 census | CC-BY-4.0 |
| WLF | Circonscription (3) > District (5) > Village (34) | Village | SPC/STSEE 2013 census | CC-BY-4.0 |
| WSM | Region (4) > District (43) > Village (330) > Enumeration area (876); itumalo (11, non-nesting) | Enumeration area | SPC/Samoa Bureau of Statistics 2011 census + geoBoundaries itumalo | CC-BY-4.0; CC-BY-SA-3.0 for itumalo |

For every country, the EEZ comes from the SPC Pacific Maritime Boundaries polygons
(CC BY-NC-SA 4.0, used under the CSDR-SPC agreement). Where admin0 is not published as
its own layer, it is dissolved from admin1.

## EEZ

| Item | Value |
|---|---|
| Source id | `spc-gem-pacific-eez-200nm` |
| Publisher | Pacific Community (SPC), Geoscience, Energy and Maritime Division (Pacific Maritime Boundaries programme, with FFA) |
| Title | Global Exclusive Economic Zones (200 Nautical Miles) - Merged Dataset (SPC Pacific Maritime Boundaries) |
| Landing page | https://pacificdata.org/data/dataset/geonode-global-eez-200nm-split-1743 |
| Publication date, version | 2025-09-17, version 1 (dataset metadata updated 2026-11-02) |
| Licence | CC BY-NC-SA 4.0, used and redistributed under the CSDR-SPC data use agreement (`license_agreement`) |
| Retrieval | `api`: Pacific Data Hub GeoNode WFS 1.0.0, one layer per territory, retrieved 2026-11-19 UTC |
| Polygons used | 25 of 36: the 24 200 NM zones (one per PICT; three for Kiribati) and the Matthew and Hunter overlapping claim. Selection table: `config/eez_polygons.csv` |

SPC builds each zone from the limits a country has deposited with the UN or set in law.
Each polygon cites its legal instrument, which is kept in the `boundary_source` column.
For most PICTs that is a UN DOALOS deposit. For Fiji, SPC cites the Marine Regions EEZ
methodology instead and marks the polygon provisional.

How the SPC polygons differ from Marine Regions:

* **Land is included.** SPC zones are solid outer-limit polygons, with no holes for land.
  The EEZ rows are therefore the full 200 NM zone, as SPC publishes it. The land is not
  subtracted; `pacific_eez.parquet` gives `land_km2` and `marine_km2` instead.
* **Some lines differ.** The Fiji/Wallis and Futuna line follows France's deposit
  (M.Z.N.149): 11,957 km² that Marine Regions gives to Fiji are in the SPC Wallis and
  Futuna zone. On the Niue/Tonga line, 3,241 km² that Marine Regions gives to Tonga are in
  the SPC Niue zone. The Fiji marine area is 19.8 thousand km² below Marine Regions: about
  12 thousand km² from the Wallis and Futuna line, and the rest from other deposited
  lines, which were not investigated. These differences are kept as published.
* **Attribute faults** are corrected in processing and listed in `attribute_notes`:
  areas stored in m² (GUM, MHL, MNP), `iso_ter1` values `FIJ` and `Palau`, swapped
  `mrgid_eez` values between the Marshall Islands and Wake polygons, and `pol_type`
  written `200 NM`.

Shared polygons:

| MRGID | Polygon | Type | Source | Licence | Appears under |
|---|---|---|---|---|---|
| 48948 | Matthew and Hunter Islands: France / Vanuatu | Overlapping claim | SPC | CC-BY-NC-SA-4.0 | NCL and VUT |
| 8319 | Wake Island / Enenkio: United States / Marshall Islands | Overlapping claim | Marine Regions v12 | CC-BY-4.0 | MHL |
| 21798 | Torres Strait Treaty: Papua New Guinea / Australia | Joint regime | Marine Regions v12 | CC-BY-4.0 | PNG |

SPC does not represent the last two as separate polygons. It codes Wake as a plain US
zone, and the Torres Strait Protected Zone lies inside its Australian zone. So both come
from Marine Regions v12 (`marineregions-eez-v12`, Flanders Marine Institute, 2023-10-25,
CC BY 4.0, [DOI 10.14284/632](https://doi.org/10.14284/632), retrieved through the VLIZ
WFS on 2026-11-19). The shared polygons are rows with `nests = false`. They are never
used to assign `eez_uid` to land units.

Alternatives considered:

* `marineregions-eez-v12` (Marine Regions World EEZ v12, CC BY 4.0): an openly licensed,
  globally consistent alternative that cuts land out as holes. It was the EEZ base layer
  until SPC's polygons became usable under the agreement. SPC's set is the Pacific
  regional authority's own, built from national deposits, and more recent, so it was
  preferred. Marine Regions remains the source of the two shared polygons above, and the
  open fallback. Its earlier polygon assignment is kept in
  `config/eez_polygons_marineregions_v12.csv`.
* `marineregions-eez-boundaries-v12`: the Marine Regions boundary lines, recording which
  segments are treaty, median-line or unsettled. Downloaded for reference; not used in
  any product.
* `spc-ffa-maritime-boundary-treaties`: FFA/SPC treaty lines. Recorded but not
  downloaded; they are lines, not polygons.
* `un-doalos-maritime-zones`: the UN DOALOS deposits. These are the legal basis, but they
  are published as charts and coordinate lists, not GIS.

Gaps: no PICT publishes its own EEZ as open GIS. National deposits reach GIS form through
SPC.

## By country

Each section has two tables:

* the levels table: the units in the per-country file, by level, with source and licence;
* the source table: publisher, title (linked to the landing page), publication date,
  version, and retrieval method and date (UTC).

Retrieval methods are `http` (direct file download) and `api` (WFS, ArcGIS or another
data API). The EEZ rows in the levels tables come from the [EEZ](#eez) sources above.

### ASM: American Samoa

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Territory of American Samoa | country | yes | 1 | `asm-census-tiger-2026` | `Public domain (US Government work)` |
| admin1 | District | state_province | yes | 5 | `asm-census-tiger-2026` | `Public domain (US Government work)` |
| admin2 | County | district | yes | 16 | `asm-census-tiger-2026` | `Public domain (US Government work)` |
| admin3 | Village | ward_village | yes | 77 | `asm-census-tiger-2026` | `Public domain (US Government work)` |
| other | Block Group | statistical | no | 43 | `asm-census-tiger-2026` | `Public domain (US Government work)` |
| other | Census Block (2020) | statistical | no | 422 | `asm-census-tiger-2026` | `Public domain (US Government work)` |
| other | Census Tract | statistical | no | 18 | `asm-census-tiger-2026` | `Public domain (US Government work)` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `asm-census-tiger-2026` | US Census Bureau, Geography Division | [TIGER/Line Shapefiles 2026, American Samoa (COUNTY, COUSUB, PLACE, TRACT, BG, TABBLOCK20)](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | 2026-09-27 | TIGER2026 | http, 2026-11-19 |

Notes: TIGER county, county-subdivision and place polygons extend over water to the 3 nm limit. Every level is clipped to land, where land is the union of the 2020 census blocks with land area greater than zero. admin0 is the union of the clipped districts. 143 census blocks that lie entirely in water were dropped.

Alternatives considered:
- `asm-pacioos-asdoc-county-village` (PacIOOS, from American Samoa Dept of Commerce, 1981 atlas base): older, and partial (no village polygons on Tutuila).
- `asm-geoboundaries-gbopen` (ADM0 Sentinel-2 land mask; ADM3 copy of Census county subdivisions): a derived copy of TIGER.
- `asm-spc-sdd-coastal-2019-counties` (SPC SDD 2019): a copy of the Census counties.
- `asm-gadm-41` (GADM 4.1): reference only, because the licence forbids redistribution. It has a "Fofo" county that TIGER does not.
- OpenStreetMap: only the territory relation exists; no subdivisions.

Gaps: no polygons were found for the Fono (legislature) electoral districts.

### COK: Cook Islands

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Cook Islands | country | yes | 1 | `cok-linz-island-polygons-topo` | `CC-BY-4.0` |
| admin1 | Group | region | yes | 3 | `cok-linz-island-polygons-topo` | `CC-BY-4.0` |
| admin2 | Island | island | yes | 15 | `cok-linz-island-polygons-topo` | `CC-BY-4.0` |
| admin3 | Census District | statistical | yes | 44 | `cok-spc-sdd-phc2011-boundaries` | `CC-BY-4.0` |
| admin4 | Enumeration Area | statistical | yes | 134 | `cok-spc-sdd-phc2011-boundaries` | `CC-BY-4.0` |
| other | Electoral Constituency | electoral | no | 24 | `cok-spc-pcrafi-2010-exposure-boundaries` | `CC-BY-NC-SA-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `cok-linz-island-polygons-topo` | Toitu Te Whenua Land Information New Zealand (LINZ) | [Cook Islands Island Polygons (Topo50 series; 1:25k Zone4/Zone3 and 1:50k Zone4/Zone3)](https://data.linz.govt.nz/layer/52251-cook-islands-island-polygons-topo-125k-zone4/) | 2022-06-29 | LDS versions 338169 (52251), 336482 (52293), 338899 (52203), 336629 (52222) | api, 2026-11-20 |
| `cok-spc-sdd-phc2011-boundaries` | Pacific Community (SPC) Statistics for Development Division / Cook Islands Statistics Office | [2011 Cook Islands Population and Housing Census administrative boundaries (EA, census district)](https://pacificdata.org/data/dataset/2011_cok_phc_admin_boundaries) | 2020-06-26 | 2011 PHC | http, 2026-11-19 |
| `cok-spc-pcrafi-2010-exposure-boundaries` | Pacific Community (SPC) Geoscience, Energy and Maritime Division (PCRAFI); source PopGIS / Cook Islands Statistics Office | [PCRAFI 2010 population exposure geographies, Cook Islands (Group, Island, Electoral Boundary, Census District, EA)](https://geonode.pacificdata.org/catalogue/#/dataset/497) | 2020-02-03 | PCRAFI 2010 exposure | api, 2026-11-19 |

Notes: The islands (admin2) come from the LINZ Topo50 island polygons. The 329 LINZ
polygons are assigned to the 15 islands by nearest named island point
(`split_from_land_by_island`), giving 240.7 km² of land, including the uninhabited Manuae,
Takutea and Suwarrow. admin0 and the three groups (admin1) are dissolved from these
islands. The group names, membership and codes come from SPC PCRAFI. The PCRAFI island
polygons themselves are not used for geometry, because on six outer atolls (Penrhyn,
Pukapuka, Manihiki, Manuae, Rakahanga, Suwarrow) they are offset by 1.6 to 8 km from the
LINZ outlines. The 2011 census districts and enumeration areas are used as published; they
cover populated land only (145 km²), and their parents are assigned by largest overlap.
The 24 electoral constituencies (2010) are the PCRAFI layer as published, under the SPC
agreement. They do not nest and are not clipped; they include reef and lagoon and carry
the same outer-atoll offsets.

The LINZ layers were retrieved through the LINZ Data Service WFS with an API key, sent
as an HTTP header. The key is not recorded anywhere in this repository.

Alternatives considered:
- `cok-spc-pcrafi-2010-exposure-boundaries` group and island polygons: used for names and
  codes only, because of the outer-atoll offsets.
- `cok-geoboundaries-gbopen` (Sentinel-2 land, CC BY 4.0): misses six islands (Palmerston,
  Suwarrow, Nassau, Pukapuka, Rakahanga, Manihiki). It was the land source before LINZ
  was available.
- `cok-spc-pcrafi-aal-electoral` (SPC GEM, CC BY-NC-SA 4.0): a loss-attribute copy of the
  PCRAFI electoral layer.
- `cok-osm-admin-relations` (OpenStreetMap): the island polygons are sea areas, not land,
  and only 11 islands are present.
- `cok-linz-geographic-names-topo` (LINZ name points): used to check island names; no
  polygons.
- `cok-gadm-41` (GADM 4.1): reference only; 11 islands.
- `cok-spc-sdd-coastal-2019`, `cok-kontur-boundaries`: no boundary layer, or a copy of OSM.

Gaps: no polygons for the Rarotonga vaka or tapere. Post-2010 electoral boundaries were not
found. The census districts and enumeration areas cover only about 145 km² of the 241 km²
of land.

### FJI: Fiji

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Republic of Fiji | country | yes | 1 | `fji-sdd-phc2017-boundaries` | `CC-BY-4.0` |
| admin1 | Division | region | yes | 4 | `fji-sdd-phc2017-boundaries` | `CC-BY-4.0` |
| admin2 | Province (Yasana) | state_province | yes | 15 | `fji-sdd-phc2017-boundaries` | `CC-BY-4.0` |
| admin3 | Tikina | district | yes | 86 | `fji-sdd-phc2017-boundaries` | `CC-BY-4.0` |
| admin4 | Enumeration Area | statistical | yes | 1980 | `fji-sdd-phc2017-boundaries` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `fji-sdd-phc2017-boundaries` | SPC Statistics for Development Division (SDD) for Fiji Bureau of Statistics (Pacific Data Hub) | [2017 Fiji Population and Housing Census admin boundaries (Province, Tikina, Enumeration Areas)](https://pacificdata.org/data/dataset/2017_fji_phc_admin_boundaries) | 2020-06-26 | 2017 PHC | http, 2026-11-19 |

Notes: The source has no Division polygons, so the divisions (admin1) are dissolved from the tikina on their `Division` attribute. Rotuma's tikina fall in Eastern Division. The province layer has 14 provinces plus Rotuma. Two empty enumeration-area features were dropped, leaving 1,980 of the 1,982. The publisher's disclaimer applies to all Fiji levels: "Upper level administrative units may slightly differ from the official boundaries. The boundaries, codes and names shown in the datasets do not imply official endorsement or acceptance by SPC."

Alternatives considered:
- `fji-ocha-cod-ab-2017` (OCHA COD-AB, endorsed and ITOS-vetted, P-codes): comes from the same Fiji Bureau of Statistics 2017 lineage, but its geometry differs. Total tikina area differs by about 2.6%. It was not chosen because the census set is published by the national statistics office, is more recent, and provides one consistent lineage from divisions down to enumeration areas. The COD-AB is the source for P-codes.
- `fji-sdd-phc2007-boundaries` (2007 census set): superseded. Keep it for linking to 2007 enumeration areas.
- `fji-geoboundaries-adm0..adm4`: copies of the SDD 2007 or FBoS sets, a 2006 Wikimedia layer, or OSM (ODbL).
- `fji-gadm-4-1`: reference only.
- `fji-pdh-pcrafi-tikina` (SPC GEM, CC BY-NC-SA 4.0): a thematic derivative; not downloaded.

Gaps: no public polygons for municipal (city and town) councils. The 2017 enumeration-area attribute `Ward` gives an unofficial approximation of urban wards. Fiji has no electoral subdivisions (it is a single national constituency), and no Vanua or Yasana layer below the provinces.

The SPC Fiji EEZ polygon cites the Marine Regions methodology rather than a Fiji deposit, and SPC marks it provisional. Its Wallis and Futuna line differs from Marine Regions; see [EEZ](#eez).

### FSM: Micronesia (Federated States of)

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Federated States of Micronesia | country | yes | 1 | `fsm-spc-sdd-phc2010` | `CC-BY-4.0` |
| admin1 | State | state_province | yes | 4 | `fsm-spc-sdd-phc2010` | `CC-BY-4.0` |
| admin2 | Municipality | local_government | yes | 75 | `fsm-spc-sdd-phc2010` | `CC-BY-4.0` |
| admin3 | Enumeration District (2010 census) | statistical | yes | 394 | `fsm-spc-sdd-phc2010` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `fsm-spc-sdd-phc2010` | SPC Statistics for Development Division (SDD) for FSM Division of Statistics | [2010 FSM Population and Housing Census administrative boundaries (State, Municipality, Enumeration District)](https://pacificdata.org/data/dataset/2010_fsm_phc_admin_boundaries) | 2020-06-26 | 2010 PHC | http, 2026-11-19 |

Alternatives considered:
- `fsm-ocha-codab-2019` (OCHA COD-AB): the same 2010 census geometry, with P-codes and regional groupings (for example Faichuk and Namoneas in Chuuk). Use it to attach P-codes by name.
- `fsm-geoboundaries-gbopen`: a copy of the COD-AB.
- `fsm-spc-gem-municipality-aal` (SPC GEM, CC BY-NC-SA 4.0): a hazard-loss product with a non-commercial licence.
- `fsm-pacioos-states-created` (PacIOOS): three lines digitised from a Wikipedia map; not polygons.
- `fsm-gadm-41`: reference only.

Gaps: no open layer for FSM Congress election districts. The 2020 census enumeration areas are not published.

### GUM: Guam

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Territory of Guam | country | yes | 1 | `gum-uscensus-tiger2025` | `Public domain (US Government work)` |
| admin1 | Village (municipality) | local_government | yes | 19 | `gum-uscensus-tiger2025` | `Public domain (US Government work)` |
| other | Census Designated Place | statistical | no | 57 | `gum-uscensus-tiger2025` | `Public domain (US Government work)` |
| other | Census block (2020) | statistical | no | 1745 | `gum-uscensus-tiger2025` | `Public domain (US Government work)` |
| other | Census block group | statistical | no | 218 | `gum-uscensus-tiger2025` | `Public domain (US Government work)` |
| other | Census tract | statistical | no | 56 | `gum-uscensus-tiger2025` | `Public domain (US Government work)` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `gum-uscensus-tiger2025` | U.S. Census Bureau | [US Census Bureau TIGER/Line Shapefiles 2025 - Guam (state FIPS 66)](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2025.html) | 2025-09-22 | TIGER/Line 2025 | http, 2026-11-19 |

Notes: The TIGER polygons are clipped to land (the union of 2020 census blocks with land area greater than zero). Water-only tracts, block groups and blocks were dropped. admin0 is the union of the 19 clipped villages.

Alternatives considered:
- `gum-gcmp-pacioos-municipal-2001` (Government of Guam, served by PacIOOS): a territorial source, but 24 years old, without codes, and with an accuracy caveat. TIGER 2025 was chosen because it is current, coded and public domain.
- `gum-geoboundaries-gbopen`: ADM2 is an older copy of TIGER; ADM0 is a Sentinel-2 land mask.
- `gum-weri-pacioos-southern-villages`: points only.
- `gum-gadm-41`: reference only.

Gaps: none at the administrative level. The legislature is elected at large, so there are no electoral subdivisions.

### KIR: Kiribati

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 3 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Kiribati | country | yes | 1 | `kir-ocha-codab-2020` | `CC-BY-3.0-IGO` |
| admin1 | Island group | region | yes | 3 | `kir-ocha-codab-2020` | `CC-BY-3.0-IGO` |
| admin2 | Island (island council) | island | yes | 36 | `kir-ocha-codab-2020` | `CC-BY-3.0-IGO` |
| admin3 | Village | ward_village | yes | 183 | `kir-spc-sdd-hhl2018` | `CC-BY-4.0` |
| admin4 | Enumeration Area (2018 household listing) | statistical | yes | 391 | `kir-spc-sdd-hhl2018` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `kir-ocha-codab-2020` | OCHA Office of the Pacific Islands (HDX) | [Kiribati - Subnational Administrative Boundaries (COD-AB) 2020](https://data.humdata.org/dataset/cod-ab-kir) | 2020-01-13 | 2020 (reviewed Oct 2024, no update required) | http, 2026-11-19 |
| `kir-spc-sdd-hhl2018` | SPC Statistics for Development Division (SDD) for Kiribati National Statistics Office | [2018 Kiribati Household Listing administrative boundaries (Island, Village, Enumeration Area)](https://pacificdata.org/data/dataset/2018_kir_hhl_admin_boundaries) | 2020-07-10 | 2018 HHL | http, 2026-11-19 |

Notes: The island groups and islands come from the OCHA COD-AB, which is built on land polygons from the SPC census geography and includes the uninhabited islands. The 2018 villages and enumeration areas cover inhabited land only. Their parents (islands) are therefore assigned by largest overlap, and the uninhabited islands fall back to island level in the finest partition. 391 enumeration areas have no name in the source; their code is used as the name.

Alternatives considered:
- SDD island layers (2010, 2018): 25 km coastal display buffers, not land.
- `kir-spc-sdd-phc2010`: superseded; villages cover settlement footprints only (70 km²).
- `kir-geoboundaries-gbopen` (OSM, ODbL): 24 islands, and lower in the source preference order.
- `kir-spc-gem-island-aal` (CC BY-NC-SA 4.0): non-commercial.
- `kir-gadm-41`: reference only.

Gaps: the 2020 census enumeration areas and the constituencies have no published polygons.

### MHL: Marshall Islands

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Overlapping claim | eez | no | 1 | `marineregions-eez-v12` | `CC-BY-4.0` |
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Republic of the Marshall Islands | country | yes | 1 | `mhl-ocha-codab-2021` | `CC-BY-3.0-IGO` |
| admin1 | Atoll / Island (local government) | island | yes | 25 | `mhl-ocha-codab-2021` | `CC-BY-3.0-IGO` |
| admin2 | Enumeration Area (2021 census) | statistical | yes | 152 | `mhl-ocha-codab-2021` | `CC-BY-3.0-IGO` |
| other | Village | ward_village | no | 49 | `mhl-usaid-pacioos-lga-2017` | `PacIOOS data use (free redistribution, not for legal use)` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `marineregions-eez-v12` | Flanders Marine Institute (VLIZ), Marine Regions | [Maritime Boundaries Geodatabase: Maritime Boundaries and Exclusive Economic Zones (200NM), version 12](https://www.marineregions.org/downloads.php) | 2023-10-25 | v12 | api, 2026-11-19 |
| `mhl-ocha-codab-2021` | OCHA Regional Office for Asia and the Pacific (HDX) | [Marshall Islands - Subnational Administrative Boundaries (COD-AB), 2021 census geography](https://data.humdata.org/dataset/cod-ab-mhl) | 2024-11-19 | 2021 (reviewed Oct 2024) | http, 2026-11-19 |
| `mhl-usaid-pacioos-lga-2017` | PacIOOS (data provider: U.S. Agency for International Development) | [Marshall Islands Local Government Areas, Village Boundaries and Atolls (USAID, served by PacIOOS)](https://www.pacioos.hawaii.edu/metadata/mh_mgd_all_local_gov_areas.html) | 2017-04-19 |  | api, 2026-11-19 |

Notes: The village layer covers 8 atolls only. It is kept as a non-nesting `other` layer. The Wake Island / Enenkio overlapping claim (MRGID 8319, United States / Marshall Islands) is included as a flagged EEZ row from Marine Regions, because SPC codes Wake as a plain US zone; see [EEZ](#eez).

Alternatives considered:
- `mhl-spc-sdd-phc2011`, `mhl-spc-sdd-atollpop2011` (2011 census): older. The 2011 atoll layer is an 11 km display buffer.
- `mhl-geoboundaries-gbopen` (OSM, ODbL): atolls include lagoons (6,522 km²).
- The USAID/PacIOOS local-government-area layer: marine extents, not land.
- `mhl-spc-gem-atoll-aal` (CC BY-NC-SA 4.0): non-commercial.
- `mhl-gadm-41`: reference only.

Gaps: no polygons for the Ratak and Ralik chains, but they can be built by grouping atolls. The Nitijela electoral districts coincide with the atolls. Village polygons are missing for 17 of the 25 atolls. HDX notes that enumeration area MH0609 is missing from the COD-AB.

### MNP: Northern Mariana Islands

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Commonwealth of the Northern Mariana Islands | country | yes | 1 | `mnp-uscensus-tiger2025` | `Public domain (US Government work)` |
| admin1 | Municipality | local_government | yes | 4 | `mnp-uscensus-tiger2025` | `Public domain (US Government work)` |
| admin2 | District (election district) | district | yes | 8 | `mnp-uscensus-tiger2025` | `Public domain (US Government work)` |
| admin3 | Village | ward_village | yes | 135 | `mnp-uscensus-tiger2025` | `Public domain (US Government work)` |
| other | Census block (2020) | statistical | no | 814 | `mnp-uscensus-tiger2025` | `Public domain (US Government work)` |
| other | Census block group | statistical | no | 55 | `mnp-uscensus-tiger2025` | `Public domain (US Government work)` |
| other | Census tract | statistical | no | 23 | `mnp-uscensus-tiger2025` | `Public domain (US Government work)` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `mnp-uscensus-tiger2025` | U.S. Census Bureau | [US Census Bureau TIGER/Line Shapefiles 2025 - Commonwealth of the Northern Mariana Islands (state FIPS 69)](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2025.html) | 2025-09-22 | TIGER/Line 2025 | http, 2026-11-19 |

Notes: The TIGER polygons are clipped to land (the union of 2020 census blocks with land area greater than zero). Before clipping, the municipalities cover 5,117 km²; after, 473 km². Water-only units were dropped. "District 4" exists in both Saipan and the Northern Islands, so the GEOID is used as the code.

Alternatives considered:
- `mnp-geoboundaries-gbopen`: ADM2 is an older copy of TIGER; ADM0 is a Sentinel-2 land mask.
- `mnp-gadm-41`: reference only.

Gaps: no CNMI-government boundary layer was found. The senatorial districts are not published, but they can be dissolved from the municipalities.

### NCL: New Caledonia

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| eez | Overlapping claim | eez | no | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | New Caledonia | country | yes | 1 | `ncl-gnc-limites-terrestres-2024` | `LO-2.0` |
| admin1 | Province | state_province | yes | 3 | `ncl-gnc-limites-terrestres-2024` | `LO-2.0` |
| admin2 | Commune | local_government | yes | 34 | `ncl-gnc-limites-terrestres-2024` | `LO-2.0` |
| admin3 | Quartier (Noumea) | ward_village | yes | 37 | `ncl-noumea-quartiers` | `LO-2.0` |
| other | Aire coutumiere | customary | no | 8 | `ncl-gnc-aires-coutumieres-2020` | `LO-2.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `ncl-gnc-limites-terrestres-2024` | Gouvernement de la Nouvelle-Caledonie (DINUM - Service de la Geomatique et Teledetection; formerly DITTT), Georep | [Limites administratives terrestres (communes, provinces)](https://georep-dtsi-sgt.opendata.arcgis.com/maps/dtsi-sgt::limites-administratives-terrestres-1/about) | 2024-10-28 | update 2024-10-28 (item modified 2026-07-17) | api, 2026-11-19 |
| `ncl-noumea-quartiers` | Ville de Noumea | [Quartiers de la ville de Noumea](https://data.noumea.nc/datasets/33f91ef1da014808b5375c0be0b92141_0/about) | 2025-06-13 | last edit 2025-06-13 | api, 2026-11-19 |
| `ncl-gnc-aires-coutumieres-2020` | Gouvernement de la Nouvelle-Caledonie (DINUM SGT), Georep | [Aires coutumieres](https://georep-dtsi-sgt.opendata.arcgis.com/datasets/b1f9a2ae61154945a470bbf803b59942/about) | 2020-01-29 | 2020-01-29 | api, 2026-11-19 |

Notes: The commune of Poya lies in both Province Nord and Province Sud, so it is split into two units, `98827-nord` and `98827-sud`. That gives 34 commune rows for 33 communes. The Noumea quartiers cover one commune only; elsewhere the finest partition falls back to communes. The publisher describes the aires coutumieres as working data that has not been officially adopted ("non officialisee"). The Matthew and Hunter overlapping claim (France / Vanuatu) is included as a flagged EEZ row.

Alternatives considered:
- `ncl-gnc-bdadmin-2022` (BDADMIN-NC 2022): same producer, older release (7 communes changed by 0.01 to 0.9 km²). It also holds the maritime limits of communes and provinces, which are not used here.
- `ncl-geoboundaries-adm0` (Sentinel-2 land mask): admin0 is dissolved from the provinces instead.
- `ncl-datagouvnc-communes-simplifiees`: a simplified derivative.
- `ncl-ign-admin-express`: does not cover New Caledonia.
- `ncl-gnc-tribus`: points only.
- `ncl-gadm-4-1`: reference only.

Gaps: no polygons for the districts coutumiers. ISEE publishes no sub-communal statistical units. The legislative constituencies are not published as a layer, but they could be derived from lists of communes.

### NIU: Niue

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Country | country | yes | 1 | `niu-linz-island-polygons-topo` | `CC-BY-4.0` |
| admin1 | Village | ward_village | yes | 14 | `niu-spc-sdd-phc2011-villages` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `niu-linz-island-polygons-topo` | Toitu Te Whenua Land Information New Zealand (LINZ) | [Niue Island Polygons (Topo, 1:50k)](https://data.linz.govt.nz/layer/52181-niue-island-polygons-topo-150k/) | 2022-06-28 | LDS version 337269 | api, 2026-11-20 |
| `niu-spc-sdd-phc2011-villages` | Pacific Community (SPC) Statistics for Development Division / Niue Statistics Office | [2011 Niue Population and Housing Census administrative boundaries (villages)](https://pacificdata.org/data/dataset/2011_niu_phc_admin_boundaries) | 2020-06-29 | 2011 PHC | http, 2026-11-19 |

Notes: admin0 is the LINZ Topo50 outline of Niue (261.3 km²). The 14 villages (2011
census) are also the Niue Assembly's village constituencies. They agree with the LINZ
outline to an IoU of 0.995, and are clipped to it (`clipped_to_coastline`). After
clipping, 0.6 km² of LINZ land is covered by no village; in the finest partition it stays
at admin0 level.

Alternatives considered:
- `niu-spc-pcrafi-aal-village` (SPC GEM, CC BY-NC-SA 4.0): 2010 village geography with
  loss attributes. It has 13 villages (Alofi not split), and its internal lines differ
  materially from the census villages (per-village IoU 0.51 to 0.91).
- `niu-geoboundaries-gbopen` (ADM1 is a copy of the census villages; ADM0 is a Sentinel-2
  land mask).
- `niu-spc-sdd-coastal-2019-villages`: a copy of the census villages.
- `niu-osm-admin-relations` (ODbL): 13 villages, because Alofi is not split.
- `niu-linz-geographic-names-topo` (LINZ name points): a name check only.
- `niu-gadm-41`: reference only.

Gaps: no boundaries were found for the 2017 or 2022 censuses.

### NRU: Nauru

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Republic of Nauru | country | yes | 1 | `nru-geoboundaries-gbopen` | `Public domain` |
| admin1 | District | district | yes | 14 | `nru-geoboundaries-gbopen` | `Public domain` |
| other | Enumeration Area (2011 census) | statistical | no | 47 | `nru-spc-sdd-phc2011` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `nru-geoboundaries-gbopen` | geoBoundaries (William & Mary geoLab) | [geoBoundaries gbOpen NRU ADM0-ADM1](https://www.geoboundaries.org/countryDownloads.html#NRU) | 2023-12-12 | gbOpen build 9469f09 | api, 2026-11-19 |
| `nru-spc-sdd-phc2011` | SPC Statistics for Development Division (SDD) for Nauru Bureau of Statistics | [2011 Nauru Population and Housing Census administrative boundaries (District, Enumeration Area)](https://pacificdata.org/data/dataset/2011_nru_phc_admin_boundaries) | 2020-06-29 | 2011 PHC | http, 2026-11-19 |

Notes: The SPC 2011 census district layer covers only the settled coastal belt (7.7 of 21.5 km²) and adds a 15th "Location" unit. The districts therefore come from geoBoundaries ADM1 (public domain), which covers the whole island. admin0 is dissolved from these districts and not taken from the geoBoundaries ADM0, which is ODbL. The 2011 enumeration areas cover the coastal belt only and are kept as a non-nesting layer.

Alternatives considered:
- `nru-spc-sdd-phc2011` district layer: partial coverage (see above).
- `nru-spc-gem-district` (SPC GEM, CC BY-NC-SA 4.0): almost the same geometry as geoBoundaries (1.1 km² symmetric difference), but non-commercial.
- `nru-gadm-41`: reference only.

Gaps: no polygons for the 8 electoral constituencies. The Electoral Act defines them as groups of districts, so they can be dissolved from the districts. The 2019 and 2021 census geographies are not published.

### PCN: Pitcairn Islands

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Territory | country | yes | 1 | `pcn-geoboundaries-gbopen` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `pcn-geoboundaries-gbopen` | geoBoundaries (William & Mary geoLab) | [geoBoundaries gbOpen Pitcairn Islands ADM0](https://www.geoboundaries.org/countryDownloads.html) | 2023-12-12 | gbOpen 9469f09 | api, 2026-11-19 |

Notes: The geoBoundaries ADM0 layer labelled "Pitcairn Island" contains only Henderson Island. Pitcairn, Oeno and Ducie islands were added from Natural Earth 10m (public domain), giving `geometry_method = as_published;supplemented_from_natural_earth`. There is nothing below territory level: Pitcairn has one Island Council, and only Pitcairn Island is inhabited.

Alternatives considered:
- `pcn-naturalearth-10m-admin0` (Natural Earth 1:10m, public domain): coarse; used only for the three missing islands.
- `pcn-osm-admin-relations` (ODbL): a maritime outline, not land.
- `pcn-gadm-41`: reference only.

Gaps: no official UK or Pitcairn government digital outline was found. The Pitcairn Islands Marine Reserve is a protected area, not an administrative unit, and is not included.

### PLW: Palau

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Republic of Palau | country | yes | 1 | `plw-spc-sdd-phc2015` | `CC-BY-4.0` |
| admin1 | State | state_province | yes | 16 | `plw-spc-sdd-phc2015` | `CC-BY-4.0` |
| admin2 | Hamlet | ward_village | yes | 77 | `plw-spc-sdd-phc2015` | `CC-BY-4.0` |
| admin3 | Enumeration Area (2015 census) | statistical | yes | 141 | `plw-spc-sdd-phc2015` | `CC-BY-4.0` |
| other | Group of states (census) | region | no | 7 | `plw-spc-sdd-phc2015` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `plw-spc-sdd-phc2015` | SPC Statistics for Development Division (SDD) for Palau Office of Planning and Statistics | [2015 Palau Population and Housing Census administrative boundaries (Group of States, State, Hamlet, Enumeration Area)](https://pacificdata.org/data/dataset/2015_plw_phc_admin_boundaries) | 2020-06-29 | 2015 PHC | http, 2026-11-19 |

Notes: Two state names in the source are wrong and were corrected (geometry_method `name_corrected`): state 6 "Koro" is now "Koror", and state 9 "Ngaraard" is now "Ngarchelong". The census "group of states" layer has a duplicated code (4), which is suffixed `4-1` and `4-2`.

Alternatives considered:
- `plw-palaris-political-2016` (PALARIS, national lands GIS, served by PacIOOS): an official source, but it has no codes, no data date and no hamlets. The census layer was chosen because it nests exactly with the hamlets and enumeration areas.
- `plw-geoboundaries-gbopen`: ADM1 is OSM (ODbL) and includes reef and lagoon; ADM2 is a copy of the census hamlets.
- `plw-spc-gem-state-aal` (CC BY-NC-SA 4.0): non-commercial.
- `plw-gadm-41`: reference only.

Gaps: the 2020 and 2025 census enumeration areas are not published.

### PNG: Papua New Guinea

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Joint regime | eez | no | 1 | `marineregions-eez-v12` | `CC-BY-4.0` |
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Country | country | yes | 1 | `png-ocha-cod-ab-2019` | `CC-BY-3.0-IGO` |
| admin1 | Region | region | yes | 4 | `png-nso-regions-2015` | `CC-BY-3.0-IGO` |
| admin2 | Province / Autonomous Region / National Capital District | state_province | yes | 22 | `png-ocha-cod-ab-2019` | `CC-BY-3.0-IGO` |
| admin3 | District | district | yes | 87 | `png-ocha-cod-ab-2019` | `CC-BY-3.0-IGO` |
| admin4 | Local Level Government (LLG) | local_government | yes | 326 | `png-ocha-cod-ab-2019` | `CC-BY-3.0-IGO` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `marineregions-eez-v12` | Flanders Marine Institute (VLIZ), Marine Regions | [Maritime Boundaries Geodatabase: Maritime Boundaries and Exclusive Economic Zones (200NM), version 12](https://www.marineregions.org/downloads.php) | 2023-10-25 | v12 | api, 2026-11-19 |
| `png-ocha-cod-ab-2019` | OCHA (HDX); source Papua New Guinea National Statistics Office; contributed by OCHA ROAP | [Papua New Guinea - Subnational Administrative Boundaries (COD-AB) adm0-3, v01](https://data.humdata.org/dataset/cod-ab-png) | 2019-05-10 | v01 (valid_on 2019-05-08; reviewed 2025-10-30; files regenerated 2026-01-26) | http, 2026-11-19 |
| `png-nso-regions-2015` | Papua New Guinea National Statistics Office via OCHA ROAP (HDX) | [Papua New Guinea Regions (2015)](https://data.humdata.org/dataset/papua-new-guinea-regions) | 2015-11-10 | 2015 | http, 2026-11-19 |

Notes: The four regions (Southern/Papua, Highlands, Momase, Islands) are built by dissolving the COD-AB provinces. Each province is assigned to a region by its overlap with the NSO 2015 region polygons. HDX notes that the regions are "not an official administrative division"; they are kept as admin1 with `level_type = region`, because they are the conventional top-level grouping of provinces. The Torres Strait Protected Zone joint regime (PNG / Australia) is included as a flagged EEZ row from Marine Regions, because SPC has no separate polygon for it. The SPC PNG zone includes the PNG mainland.

Alternatives considered:
- `png-nso-census2011-boundaries` (PNG National Statistics Office via the SPREP portal): the originator of the province, district and LLG geometry, but licensed CC BY-NC-SA 4.0. The COD-AB carries the same geometry under CC BY 3.0 IGO. Use the NSO set for its NSO GEOCODEs when linking census tables.
- `png-geoboundaries-adm0` (OSM, ODbL), `png-geoboundaries-adm1..adm3` (copies of the COD-AB).
- `png-gadm-4-1`: reference only; no LLGs.
- `png-pdh-pcrafi-llg-cu` (SPC GEM): the census-unit layer is a map preview only, with a non-commercial licence.

Gaps: ward boundaries (about 6,000 wards) are not public. The 2011 and 2024 census units are not public. The 2022 districts and the open electorates (96) have no public polygons.

### PYF: French Polynesia

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | French Polynesia | country | yes | 1 | `pyf-daf-geographie-administrative-2022` | `CC-BY-4.0` |
| admin1 | Subdivision administrative | region | yes | 5 | `pyf-daf-geographie-administrative-2022` | `CC-BY-4.0` |
| admin2 | Commune | local_government | yes | 48 | `pyf-daf-geographie-administrative-2022` | `CC-BY-4.0` |
| admin3 | Commune associee | ward_village | yes | 116 | `pyf-daf-geographie-administrative-2022` | `CC-BY-4.0` |
| admin4 | Quartier (Quartiers 2000) | statistical | no | 170 | `pyf-ispf-limites-administratives-2022` | `ODbL-1.0` |
| other | Ile / atoll | island | no | 128 | `pyf-daf-geographie-administrative-2022` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `pyf-daf-geographie-administrative-2022` | Section Cadastre-Topographie de la Polynesie francaise (Direction des affaires foncieres, DAF) | [Geographie administrative de la Polynesie francaise (communes et communes associees, iles, groupements)](https://www.data.gouv.fr/datasets/geographie-administrative-de-la-polynesie-francaise) | 2022-02-28 | 2022-02-28 | http, 2026-11-19 |
| `pyf-ispf-limites-administratives-2022` | Institut de la statistique de la Polynesie francaise (ISPF) | [Limites geographiques administratives (Communes, Communes associees, Iles, Quartiers 2000)](https://www.data.gouv.fr/datasets/limites-geographiques-administratives) | 2022-06-10 | shapefiles 2022-06-10 (RP2017 indicators) | http, 2026-11-19 |

Notes: The administrative subdivisions (admin1), communes (admin2) and communes associees (admin3) come from one DAF layer, dissolved on its codes. Communes without associated communes appear once at admin3. The ISPF Quartiers 2000 (admin4) do not fit inside the DAF communes associees: only 93.6% of their area falls inside the commune associee they are assigned to. The two sources use different geometry bases. The quartiers are therefore kept with `nests = false`, their parent is assigned by largest overlap, and they are not used in the finest partition.

Alternatives considered:
- `pyf-ispf-limites-administratives-2022` (ISPF, ODbL) for admin1 to admin3 and islands: an official source three months newer than DAF, but its geometry differs materially (3,732 km² against 3,467 km² for DAF, with about 3,414 km² in common). DAF was chosen because it is the cadastral authority, carries INSEE codes, and is CC BY rather than share-alike. ISPF is used only for the quartiers, where it is the only source.
- `pyf-geoboundaries-gbopen` (ADM0, Sentinel-2): admin0 is dissolved from the communes instead.
- `pyf-tefenua-wfs` (Te Fenua geoportal): needs an account.
- `pyf-ign-admin-express` (IGN): does not cover French Polynesia.
- `pyf-gadm41`: reference only.

Gaps: the 2017 census districts are published as a table only, with no geometry. No geometry is published for the Assemblee electoral sections or the legislative circonscriptions; both are made of whole communes and could be derived.

### SLB: Solomon Islands

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Solomon Islands | country | yes | 1 | `slb-sdd-phc2009-boundaries` | `CC-BY-4.0` |
| admin1 | Province (incl. Honiara Capital Territory) | state_province | yes | 10 | `slb-sdd-phc2009-boundaries` | `CC-BY-4.0` |
| admin2 | Constituency | electoral | yes | 50 | `slb-sdd-phc2009-boundaries` | `CC-BY-4.0` |
| admin3 | Ward | ward_village | yes | 183 | `slb-sdd-phc2009-boundaries` | `CC-BY-4.0` |
| admin4 | Enumeration Area | statistical | yes | 1344 | `slb-sdd-phc2009-boundaries` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `slb-sdd-phc2009-boundaries` | SPC Statistics for Development Division (SDD) for Solomon Islands National Statistics Office (Pacific Data Hub) | [2009 Solomon Islands Population and Housing Census admin boundaries (Province, Constituency, Ward, EA)](https://pacificdata.org/data/dataset/2009_slb_phc_admin_boundaries) | 2020-06-29 | 2009 PHC | http, 2026-11-19 |

Notes: The constituencies (admin2, `level_type = electoral`) nest strictly within provinces and contain the wards, so they sit in the hierarchy rather than in `other`.

Alternatives considered:
- `slb-ocha-cod-ab-2018` (OCHA COD-AB): an identical copy of the same 2009 geometry, with P-codes. Join on the SINSO ids to get them.
- `slb-geoboundaries-adm0/adm1` (Natural Earth, coarse); `slb-geoboundaries-adm2` (a copy of the COD-AB).
- `slb-geoboundaries-adm3/adm4`: PopGIS copies licensed "Other - Direct Permission", which is not open.
- `slb-pdh-pcrafi-2010` (CC BY-NC-SA 4.0): non-commercial; not downloaded.
- `slb-gadm-4-1`: reference only.

Gaps: the 2019 census enumeration areas and wards are not published, so all units are from 2009.

### TKL: Tokelau

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Tokelau | country | yes | 1 | `tkl-linz-island-polygons-topo` | `CC-BY-4.0` |
| admin1 | Atoll (Village / Taupulega) | island | yes | 3 | `tkl-linz-island-polygons-topo` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `tkl-linz-island-polygons-topo` | Toitu Te Whenua Land Information New Zealand (LINZ) | [Tokelau Island Polygons (Topo, 1:25k)](https://data.linz.govt.nz/layer/52149-tokelau-island-polygons-topo-125k/) | 2022-06-28 | LDS version 336486 | api, 2026-11-20 |

Notes: The atolls (admin1) are built from the LINZ Topo50 1:25k islet outlines: the 177
islets are assigned to the nearest of the three atolls (`split_from_land_by_atoll`). The
atolls are 60 to 90 km apart, so the assignment is unambiguous. Lagoons are excluded.
Land totals 9.0 km². Each atoll is also the village (taupulega); no lower level is
published.

Alternatives considered:
- `tkl-geoboundaries-gbopen` (Sentinel-2 land, 9.8 km²): coarser; IoU with LINZ 0.66 to
  0.74 per atoll. It was the land source before LINZ was available.
- `tkl-linz-residential-area-polygons-topo`: built-up footprints of the three settlements,
  not village boundaries.
- `tkl-osm-admin-relations` (ODbL): the atoll polygons are sea areas (about 2,000 to
  2,600 km² each).
- `tkl-linz-geographic-names-topo` (LINZ name points): used for the atoll label points.
- `tkl-gadm-41`: reference only; Atafu is misspelt.
- `tkl-kontur-boundaries`: a copy of OSM.

Gaps: no statistical or electoral layers are published. Swains Island (Olohega) is
administered by American Samoa; see the ASM tables and [caveats](caveats.md).

### TON: Tonga

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Kingdom of Tonga | country | yes | 1 | `ton-tsd-phc2021-admin-boundaries` | `CC-BY-4.0` |
| admin1 | Division | region | yes | 5 | `ton-tsd-phc2021-admin-boundaries` | `CC-BY-4.0` |
| admin2 | District | district | yes | 23 | `ton-tsd-phc2021-admin-boundaries` | `CC-BY-4.0` |
| admin3 | Village | ward_village | yes | 167 | `ton-tsd-phc2021-admin-boundaries` | `CC-BY-4.0` |
| admin4 | Census block | statistical | yes | 389 | `ton-tsd-phc2021-admin-boundaries` | `CC-BY-4.0` |
| admin5 | Census unit | statistical | yes | 843 | `ton-tsd-phc2021-admin-boundaries` | `CC-BY-4.0` |
| other | Constituency (People's Representative) | electoral | no | 17 | `ton-tsd-phc2021-admin-boundaries` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `ton-tsd-phc2021-admin-boundaries` | SPC Statistics for Development Division (SDD) for Tonga Statistics Department | [2021 Tonga PHC administrative boundaries (divisions, districts, villages, constituencies, blocks, census units)](https://pacificdata.org/data/dataset/2021_tonga_phc_admin_boundaries) | 2025-03-06 | 2021 PHC | http, 2026-11-19 |

Notes: The division and district layers in the source carry attributes left over from child units; only their own id and name fields are used. Minerva Reefs are inside the Fiji EEZ polygon, in both SPC and Marine Regions; see [caveats](caveats.md).

Alternatives considered:
- `ton-tsd-phc2016-admin-boundaries` (2016 census set): superseded by 2021.
- `ton-tsd-phc2011-admin-boundaries` (2011 census set): superseded.
- `ton-hdx-cod-ab` (OCHA COD-AB): 2016-era geometry. The 2022 adm1 layer has an "unknown" polygon, a malformed name, and a CRS with no EPSG code. Use it for P-codes.
- `ton-geoboundaries-gbopen`: ADM2 is a copy of the census districts; ADM0 and ADM1 are OSM (ODbL).
- `ton-gadm41`: reference only; incomplete.
- `ton-spc-gem-pcrafi-village-aal` (CC BY-NC-SA 4.0): non-commercial; not downloaded.

Gaps: none at the levels the census defines.

### TUV: Tuvalu

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Tuvalu | country | yes | 1 | `tuv-csd-phc2017-admin-boundaries` | `CC-BY-4.0` |
| admin1 | Island (Kaupule) | island | yes | 9 | `tuv-csd-phc2017-admin-boundaries` | `CC-BY-4.0` |
| admin2 | Village | ward_village | yes | 34 | `tuv-csd-phc2017-admin-boundaries` | `CC-BY-4.0` |
| admin3 | Enumeration area | statistical | yes | 70 | `tuv-csd-phc2017-admin-boundaries` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `tuv-csd-phc2017-admin-boundaries` | SPC Statistics for Development Division (SDD) for Tuvalu Central Statistics Division | [2017 Tuvalu (mini-)census administrative boundaries (islands, villages, EAs)](https://pacificdata.org/data/dataset/2017_tuv_phc_admin_boundaries) | 2020-07-10 | 2017 PHC | http, 2026-11-19 |

Alternatives considered:
- `tuv-csd-phc2012-admin-boundaries` (2012 census set): superseded.
- `tuv-geoboundaries-gbopen`: ADM1 is OSM and lacks Niulakita; ADM2 is a copy of the census villages; ADM3 is a 2014 PopGIS set licensed "Other - Direct Permission", which is not open.
- `tuv-gadm41`: reference only.
- `tuv-spc-gem-pcrafi-island-aal` (CC BY-NC-SA 4.0): non-commercial; not downloaded.

Gaps: the 2022 census boundaries have not been released. The 8 electoral constituencies have no layer. Each is one island, with Niulakita voting with Niutao, so they can be derived from the island layer. The village polygons cover about 17 of the 26 km² of land.

### VUT: Vanuatu

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| eez | Overlapping claim | eez | no | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Republic of Vanuatu | country | yes | 1 | `vut-sdd-phc2016-boundaries` | `CC-BY-4.0` |
| admin1 | Province | state_province | yes | 6 | `vut-sdd-phc2016-boundaries` | `CC-BY-4.0` |
| admin2 | Area Council / Municipality | local_government | yes | 66 | `vut-sdd-phc2016-boundaries` | `CC-BY-4.0` |
| admin3 | Enumeration Area | statistical | yes | 929 | `vut-sdd-phc2016-boundaries` | `CC-BY-4.0` |
| other | Island | island | no | 91 | `vut-sdd-phc2016-boundaries` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `vut-sdd-phc2016-boundaries` | SPC Statistics for Development Division (SDD) for Vanuatu Bureau of Statistics (Pacific Data Hub) | [2016 Vanuatu Population and Housing (Mini-)Census admin boundaries (Province, Island, Area Council, EA)](https://pacificdata.org/data/dataset/2016_vut_phc_admin_boundaries) | 2020-06-10 | 2016 PHC (mini-census) | http, 2026-11-19 |

Notes: The parent codes are implicit in the unit codes. The first digit of the area-council code gives the province, and the first three digits of the enumeration-area code give the area council. Port Vila (513) and Luganville (208) are municipal councils and are included with the area councils. Seven 2016 enumeration areas coded to area council 105 (Mota) lie in Gaua (106). The coded parent is kept; see [caveats](caveats.md#vut-vanuatu). The Matthew and Hunter overlapping claim (France / Vanuatu) is included as a flagged EEZ row.

Alternatives considered:
- `vut-ocha-cod-ab-2018` (OCHA COD-AB): an older PopGIS2 geometry from the same SPC lineage, with the same 66 area-council names. Use it to attach P-codes by name.
- `vut-geoboundaries-adm0/adm1` (OSM, ODbL); `vut-geoboundaries-adm2` (a copy of the COD-AB).
- `vut-geoboundaries-adm3`: 621 older enumeration areas licensed "Other - Direct Permission", which is not open.
- `vut-pdh-pcrafi-2010` (CC BY-NC-SA 4.0): non-commercial; not downloaded.
- `vut-gadm-4-1`: reference only.

Gaps: the 2020 census enumeration areas are not published. No customary or electoral layer was found.

### WLF: Wallis and Futuna

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Territory of the Wallis and Futuna Islands | country | yes | 1 | `wlf-stsee-phc2013-admin-boundaries` | `CC-BY-4.0` |
| admin1 | Circonscription (royaume / kingdom) | state_province | yes | 3 | `wlf-stsee-phc2013-admin-boundaries` | `CC-BY-4.0` |
| admin2 | District | district | yes | 5 | `wlf-stsee-phc2013-admin-boundaries` | `CC-BY-4.0` |
| admin3 | Village | ward_village | yes | 34 | `wlf-stsee-phc2013-admin-boundaries` | `CC-BY-4.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `wlf-stsee-phc2013-admin-boundaries` | SPC Statistics for Development Division (SDD) for Service territorial de la statistique et des etudes economiques (STSEE) / INSEE census | [2013 Wallis and Futuna PHC administrative boundaries (villages, districts)](https://pacificdata.org/data/dataset/2013_wallisfutuna_phc_admin_boundaries) | 2020-06-29 | 2013 PHC | http, 2026-11-19 |

Notes: The circonscriptions (the three kingdoms, admin1) are built by dissolving the districts: Uvea is Hahake + Hihifo + Mua, while Alo and Sigave are each both a district and a circonscription. They carry INSEE codes 98611 (Alo), 98612 (Sigave) and 98613 (Uvea). Wallis and Futuna has no communes.

Alternatives considered:
- `wlf-geoboundaries-gbopen` (ADM0 Sentinel-2): admin0 is dissolved from the circonscriptions instead.
- `wlf-ign-admin-express`: does not cover Wallis and Futuna.
- `wlf-gadm41`: reference only; no villages.

Gaps: the village geometry is from the 2013 census. INSEE published 2018 and 2023 village populations, but no new boundaries. INSEE lists about 36 villages, while the layer has 34 polygons. The village polygons cover about 86 of the 121 km² of land.

### WSM: Samoa

| Level | Local name | level_type | Nests | Units | Source | Licence |
|---|---|---|---|---|---|---|
| eez | Exclusive Economic Zone (200 NM) | eez | yes | 1 | `spc-gem-pacific-eez-200nm` | `CC-BY-NC-SA-4.0` |
| admin0 | Independent State of Samoa | country | yes | 1 | `wsm-sbs-phc2011-admin-boundaries` | `CC-BY-4.0` |
| admin1 | Region | region | yes | 4 | `wsm-sbs-phc2011-admin-boundaries` | `CC-BY-4.0` |
| admin2 | District (itumalo / faipule district) | district | yes | 43 | `wsm-sbs-phc2011-admin-boundaries` | `CC-BY-4.0` |
| admin3 | Village (nu'u, census village) | ward_village | yes | 330 | `wsm-sbs-phc2011-admin-boundaries` | `CC-BY-4.0` |
| admin4 | Enumeration area | statistical | yes | 876 | `wsm-sbs-phc2011-admin-boundaries` | `CC-BY-4.0` |
| other | Itumalo (political district) | district | no | 11 | `wsm-geoboundaries-gbopen` | `CC-BY-SA-3.0` |

| Source | Publisher | Title | Published | Version | Retrieved |
|---|---|---|---|---|---|
| `wsm-sbs-phc2011-admin-boundaries` | SPC Statistics for Development Division (SDD) for Samoa Bureau of Statistics | [2011 Samoa PHC administrative boundaries (regions, districts, enumeration areas)](https://pacificdata.org/data/dataset/2011_wsm_phc_admin_boundaries) | 2020-06-29 | 2011 PHC | http, 2026-11-19 |
| `wsm-geoboundaries-gbopen` | geoBoundaries (William & Mary geoLab) | [geoBoundaries gbOpen WSM ADM0-ADM2](https://www.geoboundaries.org/api/current/gbOpen/WSM/ALL/) | 2023-12-12 | gbOpen 9469f09 | api, 2026-11-19 |

Notes: Villages (admin3) are not published as polygons. They are built by dissolving the 2011 enumeration areas on the village code (enumeration-area id divided by 100, rounded down). The 11 itumalo (traditional political districts) cut across the 4 statistical regions. They come from geoBoundaries (derived from Wikipedia, CC BY-SA 3.0, share-alike) and are kept as a non-nesting layer. Treat them as low-officialness.

Alternatives considered:
- `wsm-geoboundaries-gbopen` ADM2: a copy of the census districts. ADM0 is OSM (ODbL); admin0 is dissolved from the regions instead.
- `wsm-gadm41`: reference only.
- `wsm-spc-gem-pcrafi-district-aal` (CC BY-NC-SA 4.0): non-commercial; not downloaded.

Gaps: the 2016 and 2021 census geographies are not published openly (a commercial 2016 edition exists), so all Samoa units are from 2011. No GIS layer exists for the 51 electoral constituencies of the Electoral Constituencies Act 2019. The Act defines them by lists of villages, so they could be built from the census villages.
