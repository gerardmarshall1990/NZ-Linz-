# Status

## Stage 1: BLOCKED on environment (scaffold committed, no data ingested)

Done: compose (PostGIS 16), schemas raw/core/analytics, `ai_readonly` role, .env.example.
Not verified: nothing has been run (no Docker daemon in this sandbox).

Blockers:
1. Egress denied (proxy 403) for: data.linz.govt.nz, data-aucklandcouncil.opendata.arcgis.com,
   services1.arcgis.com (Auckland Council ArcGIS), www.health.govt.nz, overpass-api.de.
   Fix: environment Network access -> broaden, or add these under Allowed domains.
2. LINZ_API_KEY not provided. Add it as an environment secret/variable.
3. No Docker daemon here, and no ogr2ogr/PostGIS. Either run this repo locally
   (`docker compose up`) or let me install postgresql-16-postgis + gdal-bin via apt.
