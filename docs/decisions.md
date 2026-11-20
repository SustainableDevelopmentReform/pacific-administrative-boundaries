# Decision index

Source registers (`config/sources/*.yml`), code comments and the spec refer to decision IDs
(`D-nnn` project decisions, `E-nnn` escalated source clashes, `P-nnn` processing escalations).
This index gives the public summary of each ID that appears in published files. The full
reasoning for source choices is also written inline in each register's `decisions` block.

| ID | Summary |
|---|---|
| D-003 | Source preference: official national/territorial agency > OCHA COD-AB > geoBoundaries > sovereign-state official sources > OSM (ODbL, flagged) > GADM (reference only, not redistributable) > Natural Earth (admin0 last resort). Most recent wins within a tier. |
| D-004 / E-009 | Original EEZ choice: Marine Regions World EEZ v12 (CC BY 4.0) over the SPC Pacific Maritime Boundaries set (CC BY-NC-SA). **Superseded by D-019.** |
| D-005 | Store EPSG:4326 split at the antimeridian; all overlay and area work in EPSG:3832 or EPSG:6933. |
| D-009 | Kiribati and Marshall Islands SPC "island" layers are display buffers (25 km / 11 km) and are never used as land; Kiribati village/EA codes need a crosswalk to COD-AB island codes; CNMI "District 4" is duplicated by name, so joins use GEOID. |
| D-010 | Samoa villages are derived by dissolving 2011 enumeration areas; Wallis and Futuna circonscriptions are dissolved from districts with INSEE codes. |
| D-011 / D-012 | Downloads go to a temporary directory and are verified (archive test, size, sha256) before being copied into the repository, because writing directly into a cloud-synced folder truncated files silently. |
| D-016 | One licence value per row with `license_url`; Parquet row groups never span two countries and hold at most 5,000 rows, rows sorted by `iso3`, `level_rank`, `unit_code`. |
| D-018 | Fiji Divisions and French Polynesia administrative subdivisions are typed `region`; restricted rows would live in a local-only `<iso3>_admin_restricted.parquet` (none remain after D-020); `pab cache` fetches every source processing reads. |
| D-019 | The EEZ base layer is the SPC Pacific Maritime Boundaries polygons, chosen by the dataset owner: they are the Pacific regional authority's own, built from national deposits, and more recent. SPC publishes them under CC BY-NC-SA 4.0; this project uses and redistributes them under a CSDR-SPC data use agreement, recorded per row in `license_agreement`. Downstream users are bound by CC BY-NC-SA 4.0 unless they hold their own agreement. Marine Regions v12 becomes the alternative. |
| D-020 | A LINZ Data Service API key became available, and agreements with SPC and New Zealand were confirmed. LINZ land outlines and SPC PCRAFI layers can therefore be used for the Cook Islands, Niue and Tokelau. The key is kept in a local, gitignored file and never recorded. Supersedes E-005, E-006, P-002 and P-003. |
| D-021 | Publication route: code, docs and licence on GitHub; data and STAC on S3 at `s3://csdr-public-datasets/pacific-administrative-boundaries/`. Raw downloads are never uploaded. STAC items carry basic provenance and link to GitHub for the rest. The repository URL is provisional. |
| D-022 | The STAC root catalog and collection sit at the top of the published tree (`data/` locally, the S3 prefix root), with items beside their assets and relative links; only the root catalog has an absolute `self` link. The former `stac/` folder is removed. |
| D-023 | Cook Islands, Niue and Tokelau selections after the LINZ download. LINZ Topo50 outlines (CC BY 4.0, 2022) give the Cook Islands islands, the Niue outline and the Tokelau atolls. Cook Islands groups are dissolved from the LINZ islands, with PCRAFI names and codes; the PCRAFI island polygons are offset 1.6 to 8 km on six outer atolls, so they are used for attributes only. The Niue census villages are clipped to the LINZ coastline (`clipped_to_coastline`). The Cook Islands 2010 electoral constituencies are published as they are, with an offset caveat. |
| D-024 | The SPC zone polygons include land, and are published as the full 200 NM zone. Land is not subtracted, because that would carry land-layer errors into the authoritative outline. `pacific_eez.parquet` gains `land_km2` and `marine_km2`. The finest-partition domain of each zone is the SPC polygon. |
| D-025 | SPC does not represent the Torres Strait joint regime or the Wake Island / Enenkio overlapping claim, so both come from Marine Regions v12 (CC BY 4.0) as flagged rows. Matthew and Hunter comes from SPC. SPC attribute faults (areas in m², `iso_ter1` "FIJ"/"Palau", swapped `mrgid_eez`) are corrected in processing and listed in `attribute_notes`, never in the raw files. The Fiji/Wallis and Futuna and Niue/Tonga lines are kept as SPC publishes them. |
| D-026 | Follow-ups. 130.6 km² of PNG border slivers outside the SPC zone stay attached to PNG and flagged, not clipped. The LINZ rows carry no agreement (CC BY 4.0 suffices). The Cook Islands census units stay as published, including the offset Nassau district. The 19.8 thousand km² lower Fiji marine area compared with Marine Regions is documented, not changed. |
| E-001 | Guam villages: US Census TIGER/Line 2025 chosen over the 2001 Guam municipal layer (older, no codes, accuracy caveat). |
| E-002 | Nauru districts: geoBoundaries ADM1 (whole island) chosen over the SPC 2011 census layer (coastal belt only). |
| E-003 | Palau states: SPC 2015 census layer chosen over PALARIS (no codes, no date); two state names corrected (Koror, Ngarchelong). |
| E-004 | French Polynesia admin1-3 and islands: DAF (cadastral authority, CC BY 4.0, INSEE codes) chosen over ISPF (ODbL, three months newer upload); ISPF retained only for Quartiers 2000. |
| E-005 | Cook Islands PCRAFI layers treated as restricted, with open derived islands and groups. **Superseded by D-020 and D-023.** |
| E-006 | Tokelau atolls derived by splitting the geoBoundaries land outline. **Superseded by D-023** (LINZ islets). |
| E-007 | Fiji: SPC/FBoS 2017 census set chosen for all levels over OCHA COD-AB (same lineage, P-codes) for a single consistent hierarchy. |
| E-008 | Papua New Guinea regions kept as admin1 with `level_type = region` (conventional grouping, not statutory). |
| E-010 | Overlapping claims (Wake/Enenkio, Matthew & Hunter) and the Torres Strait joint regime are kept as flagged marine rows and never used as a land unit's EEZ. |
| P-001 to P-009 | Processing defaults, all ratified: Pitcairn admin0 supplemented from Natural Earth; Cook Islands open islands supplemented from census districts and restricted Cook Islands layers kept separate (P-002, P-003; both superseded by D-020); Marshall Islands villages as a non-nesting layer; TIGER polygons clipped to land; land beyond the EEZ outline attached to its country's zone (now only PNG border slivers, D-026); seven mis-coded Vanuatu EAs keep their coded parent; French Polynesia quartiers marked non-nesting; `other` layer uid convention. See `docs/caveats.md`. |
