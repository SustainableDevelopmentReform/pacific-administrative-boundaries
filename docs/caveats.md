# Caveats

Read this page before using the data for analysis or decisions. The global caveats apply
to every country. The per-country notes come from the processing and QA checks of
v0.1.0. Units, areas and percentages are as computed in EPSG:6933.

## Global caveats

### Boundaries are not legal boundaries

These are the boundaries as published by their sources, harmonised for analysis. They
are not authoritative statements of legal or administrative limits, and they do not
imply endorsement by any government. Several sources say this explicitly. Fiji's census
boundaries, for example, carry the SPC disclaimer that "upper level administrative units
may slightly differ from the official boundaries".

### Topology is as published

Child units are not snapped to their parents. When two levels come from different
sources or editions, they do not line up exactly. Children can stick out of their parent,
or leave parts of it uncovered. The QA stage measures this for every parent unit; the
largest cases are listed per country below.

* In the long tables, each unit keeps its published polygon.
* In the finest partition, children are clipped to their parents. That removes the
  overlaps, but a piece can then be smaller than the unit's own polygon.

### Partial-coverage finest levels

Several of the finest levels cover populated land only:

* census districts and enumeration areas in the Cook Islands;
* villages and enumeration areas in Kiribati and Tuvalu;
* villages in Wallis and Futuna;
* the quartiers, which exist only in Noumea.

In the finest partition, the land that a level does not cover stays as the coarser unit,
flagged `geometry_method = no_<level>_coverage`. A unit that has no children at all stays
at its own level but is not flagged; Gaua in Vanuatu is an example. To find every
fallback, compare `finest_level_code` with the deepest level available for the country.
`finest_level_code` therefore varies within a country. Do not assume that every piece in
a country is at the same level.

### Nesting failures

A few layers do not nest cleanly in the level above:

* **French Polynesia quartiers:** only 93.6% of their area falls inside the commune
  associee they are assigned to. They are marked `nests = false` and are left out of the
  finest partition.
* **Vanuatu enumeration areas:** 7 are coded to an area council they mostly lie outside.
* **Village layers assigned by overlap:** where the source gives no parent code (ASM,
  MNP, KIR), some villages straddle their parent's boundary.

`geometry_method` shows how each parent was assigned: `parent_by_code` or
`parent_by_overlap`.

A nesting-level layer that fails its nest check (the French Polynesia quartiers) is set
to `nests = false`, but it keeps a `parent_uid`: the parent holding the largest share of
its area. Treat that link as information only, not containment.

### EEZ source: SPC Pacific Maritime Boundaries (used under agreement)

The EEZs come from the SPC Pacific Maritime Boundaries polygons (Pacific Data Hub, layers
dated 2022 to 2025), which SPC builds from each country's deposits with the UN (DOALOS);
each row's `boundary_source` names the instrument. SPC publishes them under CC BY-NC-SA 4.0.
This project uses and redistributes them under the CSDR-SPC data use agreement (decision
D-019). **EEZ-derived geometry is SPC data used under that agreement.** The 26 SPC EEZ
rows and the 25 SPC marine rows of the finest partition carry `license = CC-BY-NC-SA-4.0`
and a `license_agreement`. Downstream users are bound by CC BY-NC-SA 4.0 (attribution to
SPC, non-commercial use, share-alike) unless they hold their own agreement with SPC. The
same applies to anything you derive from those rows, such as a marine area or a coastal
buffer clipped to an EEZ. The land pieces of the finest partition keep the licences of
their land sources; their `eez_uid` is an attribute, not SPC geometry. Marine Regions v12 (CC BY 4.0) is the documented alternative and
supplies the two claim/regime polygons SPC does not have (below).

Differences from Marine Regions that users may notice (SPC follows the deposits):

* the Fiji / Wallis and Futuna line: about 12,000 km² that Marine Regions puts in Fiji is in
  SPC's Wallis and Futuna zone;
* the Niue / Tonga line: about 3,200 km² that Marine Regions puts in Tonga is in SPC's Niue
  zone;
* the Fiji marine area is 19.8 thousand km² below Marine Regions: about 12 thousand km²
  from the Wallis and Futuna line, and the rest from other deposited lines, which were
  not investigated;
* SPC zones include land (see below), so their areas are larger than Marine Regions'.

The SPC Fiji polygon is an exception to "SPC follows the deposits": SPC cites the Marine
Regions EEZ methodology for it rather than a Fiji deposit, and marks it provisional.

Some boundary segments are median lines or unsettled rather than treaty lines. Neither
source is a legal boundary.

SPC attribute faults are corrected in processing, never in the raw files, and recorded in
`attribute_notes` (decision D-025): `area_km2` in m² for GUM, MHL and MNP; `iso_ter1`
"FIJ" and "Palau"; MHL `mrgid_eez` 8319 (swapped with Wake) corrected to 8318; `pol_type`
"200 NM" for FSM and PNG.

### EEZ polygons include land

SPC zone polygons are solid: the land is inside the zone, not cut out as holes (decision
D-024). They are published as SPC publishes them, and `area_km2` of an EEZ row is the whole
zone. `pacific_eez.parquet` adds `land_km2` (the country's land units in the zone) and
`marine_km2` (zone minus their union, the finest partition's marine row). Because the land
comes from other sources with their own coastlines, `land_km2` is our land, not SPC's.
`land_km2 + marine_km2` equals `area_km2` for every zone except PNG, where it exceeds the
zone by 130.6 km² of border slivers (see the PNG notes below). The French Polynesia zone
has one interior ring, a high-seas pocket of 3,523 km², which is kept.

### Overlapping claims and joint regimes

Three polygons are not ordinary EEZs:

* **Wake Island / Enenkio** (MRGID 8319): an overlapping claim by the United States and
  the Marshall Islands. It is under MHL. Including it records the Marshall Islands claim;
  it takes no position on that claim. SPC codes Wake as a plain US zone, so this polygon
  comes from Marine Regions v12 (`source_id = marineregions-eez-v12`, CC BY 4.0).
* **Matthew and Hunter Islands** (48948): an overlapping claim by France (New Caledonia)
  and Vanuatu. It is under both NCL and VUT, so it appears twice in
  `pacific_admin.parquet`.
* **Torres Strait Protected Zone** (21798): a joint regime of PNG and Australia, under
  PNG. SPC has no separate polygon for it (it sits inside SPC's Australian zone), so it
  comes from Marine Regions v12 (CC BY 4.0). Matthew and Hunter comes from SPC's own
  overlapping-claim layer.

All three have `nests = false`. They never set `eez_uid` on land units, and each appears
once in the finest partition as a marine row. **When you sum EEZ areas, filter to
`nests = true`** (in the EEZ file, `pol_type = '200NM'`). Otherwise Matthew and Hunter is
counted twice, and claimed areas are counted as national EEZ.

### Minerva Reefs and Swains Island

* **Minerva Reefs**, North and South, lie inside the SPC Fiji EEZ polygon (as in Marine
  Regions). Tonga's claim has no polygon. No land unit covers them.
* **Swains Island (Olohega)** is in the American Samoa EEZ, consistent with the 1980
  US-New Zealand (Tokehega) treaty. It is an American Samoa district and county. Tokelau's
  traditional claim is not modelled.

### Land clipping of US Census TIGER/Line (ASM, GUM, MNP)

TIGER county, county-subdivision, place and tract polygons extend over water, out to the
3 nm limit. Every TIGER level here was clipped to land, using the union of the 2020
census blocks with land area greater than zero, and water-only units were dropped. As a
result:

* the units are smaller than the official TIGER polygons (the American Samoa districts
  shrink from 1,505 to 201.5 km², the Northern Mariana municipalities from 5,117 to
  473 km²);
* the US Census `ALAND`/`AWATER` figures will not match `area_km2`;
* the census blocks are 2020 geography, against 2025 or 2026 boundaries for the
  administrative levels.

### Licences

* **Share-alike sources:** the French Polynesia Quartiers 2000 (`ODbL-1.0`, 170 rows)
  and the Samoa itumalo (`CC-BY-SA-3.0`, 11 rows) are open but share-alike. If you
  redistribute those rows, or a database or derivative made from them, their terms
  apply.
* **Pacific Data Hub licence version:** several SPC census boundary sets on the Pacific
  Data Hub state only "CC-BY", without a version. They are recorded as `CC-BY-4.0`. That
  is an assumption, not a statement by the publisher.
* **PacIOOS terms:** the Marshall Islands villages (PacIOOS) allow free use and
  redistribution, but the data are "not intended for legal use".
* **Sources used under agreement.** The SPC EEZ polygons and the SPC PCRAFI 2010 Cook
  Islands electoral constituencies are CC BY-NC-SA 4.0 (the 2010 layers' own record says
  "Not Specified"); this project uses and redistributes them under the CSDR-SPC data use
  agreement (D-019, D-020). Their rows carry `license = CC-BY-NC-SA-4.0` and the agreement in
  `license_agreement`; downstream users are bound by CC BY-NC-SA 4.0 unless they hold their
  own agreement. To exclude them, filter on `license != 'CC-BY-NC-SA-4.0'`. The LINZ
  layers (COK, NIU, TKL) are CC BY 4.0 and need no agreement; their `license_agreement`
  is empty.
* **No restricted rows.** No row in this build is licence-restricted, and there are no
  restricted companion files. Every published file has `license_restricted = false` on
  all rows.

### Census vintages differ by country

Most subnational units are census geography, and the latest openly published census
geography differs widely by country:

* 2009: SLB
* 2010: FSM
* 2011: COK, NIU, NRU (enumeration areas), WSM
* 2013: WLF
* 2015: PLW
* 2016: VUT
* 2017: FJI, TUV
* 2018: KIR (household listing)
* 2021: MHL, TON
* 2020 blocks, with 2025 or 2026 boundaries: ASM, GUM, MNP

Several countries have held later censuses whose geography is not public. Enumeration
areas are redrawn between censuses, so a table from a newer census will not match these
units. Do not compare unit counts at the `statistical` level across countries as if
they meant the same thing.

### Conventional compared with statutory regions

Some admin1 units are conventional or statistical groupings, not governments:

* PNG regions, which HDX calls "not an official administrative division";
* Fiji divisions;
* French Polynesia administrative subdivisions;
* Tonga divisions;
* Samoa statistical regions;
* the Kiribati and Cook Islands island groups.

These have `level_type = region`. Pacific "admin1" units are not equivalent across
countries. For comparisons, use `level_type`, and read `level_name_local`.

### `level_type` is a category, not a rank

`state_province` occurs at most once per country. `statistical`, however, repeats at
successive levels by design. In the Cook Islands, both the census districts (admin3)
and the enumeration areas (admin4) are `statistical`; in Tonga, so are the census blocks
(admin4) and census units (admin5). Different countries also put local governments
under different types: the island councils of Kiribati, Tuvalu and the Marshall Islands
are `island`. To select exactly one layer, filter on `level_code`, plus
`level_name_local` where needed.

### Derived layers

Some units are not published by any source. They were built here:

* admin0 for most countries (union of admin1);
* Fiji divisions;
* PNG regions;
* Samoa villages;
* Wallis and Futuna circonscriptions;
* French Polynesia subdivisions;
* Cook Islands islands and groups;
* Tokelau atolls;
* the Pitcairn outline.

`geometry_method` names the method used for each; see
[methods.md](methods.md#derived-units-and-geometry_method-tokens). Derived units are as
good as their inputs.

### Codes, names and uids

* `unit_code` is the source's code. Where the source had none, it is a name slug or a
  generated `gen-<n>`; `code_scheme` says which.
* Several sources that were not used carry P-codes or ISO 3166-2 codes. They are named
  in [sources.md](sources.md).
* uids are stable only as long as the source codes are. A new census edition will
  produce new uids.

### Antimeridian

Geometries that cross 180° are split there. Their `bbox` spans -180 to 180, so bounding
box filters return them for any query at their latitude. Plot them in EPSG:3832 or with
shifted longitudes; see [usage.md](usage.md#antimeridian).

## Per-country notes

### ASM: American Samoa
- The villages are assigned to counties by overlap, because the source has no county
  code. Two villages cross county lines. Three counties differ by more than 1% from
  their villages; the worst has 14% of its village area outside it.
- TIGER levels are clipped to land (201.5 km²). Four small county areas (2.3 km²) have no
  village and appear at county level in the finest partition.
- Swains Island and Rose Atoll are their own districts.

### COK: Cook Islands
- Islands (admin2, 15) are the LINZ Topo50 island polygons (2022, 240.7 km²), split by
  island, with official names and the PCRAFI island codes. Groups (admin1, 3) are
  dissolved from them with the PCRAFI group names and codes (Palmerston is in the Southern
  Group). admin0 is their union. The PCRAFI island polygons are not used for geometry: on
  six outer atolls they are offset by 1.6 to 8 km (Penrhyn 8.0 km).
- The census districts and enumeration areas (SDD 2011) cover 145 km² of the 241 km² of
  land. In the finest partition the rest falls back to island level. They are used as
  published, not clipped: 3.2 km² of them lie outside the LINZ islands. The census layer
  is offset at Nassau, where 89% of the census district lies outside the LINZ Nassau
  outline. Parents are assigned by largest overlap.
- The electoral constituencies (24, PCRAFI 2010) are kept as published, non-nesting
  (`level_code = other`) and not clipped. **Their polygons are offset up to 8 km on the
  outer atolls** and include reef and lagoon (237.6 km², of which about 197 km² is on LINZ
  land). They are 2010 boundaries; no later electoral layer is public.
- The PCRAFI layers have known attribute errors inherited from their source. For
  example, Palmerston is labelled "Northern".

### FJI: Fiji
- The SPC disclaimer applies: upper-level units may differ slightly from the official
  boundaries.
- The OCHA COD-AB (P-codes) has different geometry; total tikina area differs by about
  2.6%. Do not mix the two.
- The enumeration areas leave 117 km² of two tikina uncovered (19% and 15% of those
  tikina). In the finest partition that area falls back to tikina level.
- The Divisions are `level_type = region` (groupings without their own government); the
  Provinces are `state_province`.
- Fiji crosses the antimeridian. Minerva Reefs are in the Fiji EEZ polygon.

### FSM: Micronesia (Federated States of)
- All levels come from one 2010 census set and nest exactly.
- The geography is from 2010; the 2020 census areas are not public.

### GUM: Guam
- The 19 villages are the only administrative level. Census tracts, block groups, blocks
  and census designated places are non-nesting `other` layers.
- The units are clipped to land (553.3 km²). The census blocks are 2020 geography.

### KIR: Kiribati
- The villages and enumeration areas (2018) cover the inhabited islands only: 630 of
  860 km². The uninhabited islands, and the unsettled parts of inhabited ones, appear at
  island level in the finest partition.
- The villages are assigned to islands by overlap, because their island ids are not the
  COD-AB codes. 39 villages lie less than 90% inside their assigned island. The area
  share inside the assigned parent is 87%.
- The 391 enumeration areas have no names; the code is used as the name.
- Kiribati has three EEZ zones: Gilbert, Phoenix and Line. Each land unit carries the
  `eez_uid` of its own zone.

### MHL: Marshall Islands
- The villages (PacIOOS/USAID) cover 8 of 25 atolls and do not nest (`other`).
- HDX notes that enumeration area MH0609 is missing from the COD-AB.
- The Wake Island / Enenkio overlapping claim is under MHL.

### MNP: Northern Mariana Islands
- The villages are assigned to districts by overlap. Seven villages lie less than 90%
  inside their district; the worst has 58% of its area outside.
- "District 4" is the name of a district in both Saipan and the Northern Islands. Use
  `uid` (GEOID-based), not `unit_name`.
- TIGER levels are clipped to land (472.8 km²).

### NCL: New Caledonia
- Poya is split into `98827-nord` and `98827-sud`, so there are 34 commune rows for 33
  communes. Aggregate on the INSEE code prefix if you need 33.
- The quartiers exist for Noumea only. They overrun the commune by 2.1% and leave 4.1%
  of it uncovered.
- The publisher describes the aires coutumieres as working data that has not been
  officially adopted.
- The Matthew and Hunter overlapping claim is also under NCL.

### NIU: Niue
- admin0 is the LINZ Topo50 island outline (261.3 km²).
- 14 villages from the 2011 census (SDD); they are also the Assembly constituencies. There
  are no later boundaries. They are clipped to the LINZ outline (`clipped_to_coastline`,
  261.4 to 260.7 km²); about 0.6 km² of LINZ land is not covered by any village and falls
  back to admin0 in the finest partition.

### NRU: Nauru
- The districts come from geoBoundaries (public domain). The official 2011 census layer
  covers only the coastal belt.
- The 2011 enumeration areas cover the coastal belt only and do not nest (`other`).

### PCN: Pitcairn Islands
- admin0 only. Henderson Island comes from geoBoundaries (Sentinel-2). Pitcairn, Oeno and
  Ducie come from Natural Earth 1:10m, which is coarse.

### PLW: Palau
- Two state names are corrected from the source: Koror and Ngarchelong.
- The census "group of states" layer has a duplicated code, stored as `4-1` and `4-2`.
- The finest partition has 13 sliver pieces of essentially zero area flagged
  `no_admin3_coverage`.

### PNG: Papua New Guinea
- The regions are conventional groupings, not an official administrative level.
- The SPC PNG zone includes the mainland (2.86 million km² with land). Along the land
  border with Indonesia (141° E and the Fly River bulge), 130.6 km² of PNG land units lie
  just outside the SPC polygon, because the two layers digitise the border differently. In
  the finest partition those slivers stay attached to the PNG zone, flagged
  `land_outside_eez_outline` (10 Local Level Government pieces), and the zone's domain
  includes them. For PNG, `land_km2 + marine_km2` therefore exceeds the zone's `area_km2`
  by 130.6 km².
- The Torres Strait joint regime is under PNG. It comes from Marine Regions (CC BY 4.0).
- The province, district and LLG geometry is the NSO 2011 census geometry, as carried by
  the 2019 COD-AB. There are no ward or census-unit polygons.

### PYF: French Polynesia
- The two official sources differ. DAF (used for admin1 to admin3 and the islands) totals
  3,467 km²; ISPF totals 3,732 km².
- The ISPF quartiers do not nest in the DAF communes associees. 234 km² of quartier area
  falls outside its assigned parent, and they have `nests = false`.
- The quartiers are licensed `ODbL-1.0`.
- The administrative subdivisions are `level_type = region`; they have no government of
  their own.

### SLB: Solomon Islands
- The constituencies are admin2 (`level_type = electoral`) because they nest strictly
  between provinces and wards.
- The geography is from 2009; the 2019 census areas are not public.

### TKL: Tokelau
- The atolls (Atafu, Nukunonu, Fakaofo; each is also the village/Taupulega) are the 177
  LINZ Topo50 islets (2022, 8.97 km²) grouped by atoll; no official atoll polygons exist.
- Swains Island is not included; it is administered by American Samoa.

### TON: Tonga
- Two census units extend outside their census block. One of them covers more than the
  whole area of its small parent block.
- The 17 constituencies do not nest (`other`).
- Minerva Reefs are in the Fiji EEZ polygon, not Tonga's.

### TUV: Tuvalu
- The villages (and the enumeration areas within them) cover 16.8 of the 26.2 km² of
  land. Eight of the nine islands are more than 1% uncovered. In the finest partition the
  rest (10 km²) falls back to island level.

### VUT: Vanuatu
- Seven 2016 enumeration areas are coded to area council 105 (Mota) but lie in Gaua
  (area council 106), 310 km² in total. The coded parent is kept in the long table. Gaua
  has no enumeration areas of its own, so in the finest partition it appears at area
  council level, without a coverage flag.
- The Matthew and Hunter overlapping claim is also under VUT.
- The 91 islands do not nest (`other`).

### WLF: Wallis and Futuna
- The 2013 villages cover 86.5 of the 121.3 km² of land. In the finest partition the rest
  (34.9 km²) falls back to district level.
- The layer has 34 village polygons; INSEE lists about 36 villages.

### WSM: Samoa
- The villages are derived by dissolving the 2011 enumeration areas on their village
  code. They are census villages, not legally surveyed village boundaries.
- The 11 itumalo come from geoBoundaries, which derived them from Wikipedia. They are
  licensed CC-BY-SA-3.0, are of low officialness, and do not nest.
- All units are from 2011.
