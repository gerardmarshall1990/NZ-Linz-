# Status

## Stage 1: LINZ ingest done (Auckland extent). Gate: PASSED against real data
Row counts: parcels 737,649; buildings 826,450; addresses 810,673; titles 769,445 (no dupes, no null geometry).
Spot checks (address -> parcel -> buildings): 2-20 Park Rd Grafton (Auckland Hospital) 43,140 m2, 11 buildings;
303 Queen St 6,453 m2, 12 buildings; 1 Federal St 1,284 m2, 2 buildings; 42 Reimers Ave 852 m2, 1 building.
Caveat: areas are LINZ-consistent but not compared to an external viewer.
Local DB is apt Postgres 16/PostGIS (not Docker). Start: `pg_ctlcluster 16 main start`.

Open items: www.health.govt.nz returns 403 and overpass-api.de is unreachable (see DATA_SOURCES.md).
Next: Stage 2 (Auckland Council zoning, overlays, hazards -> core.sites).
