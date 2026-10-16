# Status

## Stage 1 (LINZ ingest): PASSED. Stage 2 (core.sites): PASSED with documented gaps
Stage 1 counts: parcels 737,649; buildings 826,450; addresses 810,673; titles 769,445.
Stage 2: core.sites = 559,528 Auckland sites (clipped to the Auckland local board boundary). Zone on 559,522 (6 without), 100% of 444,114
urban-proxy sites (have an address, <=2,000 m2). Overlays on 147,168; hazard flag on 190,263; buildings on 404,265; council property link 555,529.
Spot-checks: 5 parcels (THAB, Rural Production, MHS, Single House, Maori Purpose) vs live Auckland Council ArcGIS queries: zone and flood flags matched.
Security: key removed from git history (filter-repo + force push); .env gitignored. Backups: `make backup STAGE=stageN` -> backups/ (gitignored).

Gaps: no rating values (not published), no slope, no bus/shop distances (see docs/DATA_SOURCES.md, docs/LIMITATIONS.md).
Network: health.govt.nz behind Cloudflare bot challenge; overpass-api.de tunnel closed; kumi mirror HTTP 500.
Stage 4 TODO (user request): treat the LINZ 'Maori' parcels (605 in the bbox, 108 sites in Auckland) as a partial indicator; cross-check against
Te Puni Kōkiri and Māori Land Court public data and report the gap.
Next: Stage 3 (rules corpus).
