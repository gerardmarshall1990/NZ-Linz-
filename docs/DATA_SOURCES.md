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
