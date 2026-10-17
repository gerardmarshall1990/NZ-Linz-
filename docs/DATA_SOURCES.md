# Data sources

Loaded 2026-10-16 by `scripts/ingest_linz.py` (LINZ Data Service WFS 2.0, EPSG:2193, bbox E1640000-1830000 N5850000-6050000,
paged 5000/request). The bbox over-fetches slightly (Whangarei, Kaipara, Waikato, Thames-Coromandel, Hauraki rows exist);
clip to the Auckland Council boundary when building `core.sites`.
Licence: CC BY 4.0 (LINZ). Refresh: re-run the script (drops and reloads the raw table; pages cached in `data/`, delete to re-download).

| Dataset | LINZ layer | Table | Rows | Notes |
|---|---|---|---|---|
| NZ Primary Parcels | layer-50772 | raw.linz_parcels | 737,649 | `calc_area` equals ST_Area of geom. 605 have parcel_intent = 'Maori' |
| NZ Building Outlines | layer-101290 | raw.linz_buildings | 826,450 | no height/age fields; `use` and capture dates only |
| NZ Addresses | layer-123113 | raw.linz_addresses | 810,673 | 729,196 are territorial_authority = Auckland |
| NZ Property Titles | layer-50804 | raw.linz_titles | 769,445 | no owner names |

Other LINZ layers identified (not yet loaded): NZ Properties: Ownership table-105627, Property-Address Reference table-115638,
Title Estates table-51566, Title Memorial table-52068 (check openness before use), NZ Rail Station Points layer-50318.
Row counts verified distinct on primary key; zero null geometries.

## Reachability (this sandbox, 2026-10-16)
- data.linz.govt.nz, data-aucklandcouncil.opendata.arcgis.com, services1.arcgis.com: OK
- www.health.govt.nz: 403 (HealthCERT list blocked); overpass-api.de: unreachable. Stage 4 / amenities depend on these.

# Stage 2: Auckland Council + LINZ extras (loaded 2026-10-16)

Source: Auckland Council open data ArcGIS FeatureServer, `https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/<service>/FeatureServer/0`
(licence CC BY 4.0, loaded by `scripts/ingest_auckland.py`, EPSG:2193, 2000 features/page).

| Key / table | Service | Rows | Used for |
|---|---|---|---|
| raw.ac_zone | Unitary_Plan_Base_Zone | 139,490 | base zone (coded; decoded via core.zone_lookup) |
| raw.ac_precinct | Precincts | 528 | precincts |
| raw.ac_boundary_local_board | LocalBoardBoundaries_PROD | 21 | Auckland Council boundary (dissolved) |
| raw.ac_property | AC_Property_Query | 754,787 | council property id, valuation ref, rate account (NO dollar values) |
| raw.ac_ov_* (19 layers) | heritage place/extent, SEA, special character, volcanic viewshafts (regional/local), ONL/ONF/ONC/HNC, ridgeline, national grid, notable trees/groups, aircraft noise, mana whenua sites, Waitakere Ranges, quarry buffer, natural stream mgmt | see below | overlay flags |
| raw.ac_hz_flood_plains / flood_prone / flood_sensitive | Flood_Plains, Flood_Prone_Areas, Flood_Sensitive_Areas | 12,629 / 35,338 / 859 | flood flags |
| raw.ac_hz_coastal_inundation | Coastal_Inundation_1_per_cent_AEP_Plus_1m_Control | 1,894 | coastal inundation flag |
| raw.ac_hz_landslide_large | Large_Scale_Landslide_Susceptibility | 86,475 | landslide code 1-5 (regional model, coarse) |
| raw.ac_hz_liquefaction | Liquefaction_Vulnerability_Calibrated_Assessment | 1,172 | liquefaction category |
| raw.ac_hz_tsunami | Tsunami_Evacuation_Zone | 2 | tsunami zone (Red/Yellow) |
| raw.linz_facilities | LINZ layer-105588 NZ Facilities | 704 (bbox) | 48 hospitals, 656 schools, for distances |
| raw.linz_rail_stations | LINZ layer-50318 | 50 (bbox) | rail distance |

## NOT available / not loaded (be explicit)
- **Rating values (capital / land / improvement): not openly published.** Searched the Auckland Council open-data hub (queries: capital value,
  rating valuation, land value, rateable value) and the full ArcGIS service list: none. `AC_Property_Query` has VALUATIONREF and rate
  account keys only. Values need a licensed source (e.g. QV/CoreLogic/council rates data request). `core.sites` has no value columns; land-to-value
  ratio is therefore not computed. Not scraped.
- **Slope / DEM: not done.** Council contours 2024 exist (Auckland open data hub) and LINZ has DEM layers; a slope raster pipeline is still to do.
- **Bus stops and shops: not loaded.** Overpass main (overpass-api.de) is not yet reachable; overpass.kumi.systems returned HTTP 500. Auckland Transport GTFS not tested.
- **Coastal erosion/instability (CoastalInstabilityAndErosion, polylines) and Shallow_Landslide_Susceptibility (4.9M polygons): not loaded.**
- **Wastewater/water network (wm_Wastewater_Pipes_Public etc.): identified, not loaded.**
- **HealthCERT list (www.health.govt.nz): reachable but served a Cloudflare bot challenge (cf-mitigated: challenge) to scripted clients. Not bypassed.** Stage 4 will look for the list via data.govt.nz / other published exports.

## Methods (core.sites)
- Sites = LINZ primary parcels whose point-on-surface lies in the dissolved Auckland local board boundary, minus road, hydro, railway, erosion,
  legalisation, streambed, accretion, reclamation, CMA, marginal strip, licence and unknown parcels. Reserves are kept (`is_reserve`).
- Zone = zone with the largest overlap area (`zone_share` = fraction of parcel); `zone_count` = number of zones touched.
- Overlays / hazards = parcel interior intersects layer interior (edge-touching ignored). Layers are subdivided (<=256 vertices) for speed.
- Buildings assigned to the parcel containing their point-on-surface; footprints are full footprint areas (no clipping), coverage capped at 100%.
- Māori flags: `maori_land_linz` (LINZ parcel_intent = 'Maori') and `zone_maori_purpose`. Partial indicators only (see Stage 4).

# Stage 3 additions (2026-10-17)
| Source | URL | Licence | Notes |
|---|---|---|---|
| Auckland Unitary Plan operative chapter PDFs (C, D, E, H, J) | https://unitaryplan.aucklandcouncil.govt.nz/ (index data/operative/data.xml, dated 16 Oct 2026) | Auckland Council publication; licence not stated on the plan site: confirm reuse terms before redistributing text outside this tool | 99 PDFs, 1,685 pages; refresh with `make rules` |
| Auckland Council plan status pages | aucklandcouncil.govt.nz (operative-in-part page, proposed plan changes list, PC120 page) | as above | used for `analytics.plan_versions` |
| Council plan-change property summaries (PC78 withdrawal, PC120 notified/revised) | services1.arcgis.com Auckland Council ArcGIS | CC BY 4.0 (Council open data) | attributes only, `raw.ac_pc*` |
| Auckland Transport static GTFS | https://gtfs.at.govt.nz/gtfs.zip (feed 5 Oct 2026 to 7 Feb 2027) | AT open data (licence to confirm) | 6,863 stops, `raw.at_stops` |
| Manual sources | `docs/sources_manual/` | n/a | HealthCERT, Ngā Paerewa, council forms, TPK/Māori Land Court exports |
