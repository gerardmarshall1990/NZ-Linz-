# Status

## Stage 1: BLOCKED on environment (scaffold committed, no data ingested)

Done: compose (PostGIS 16), schemas raw/core/analytics, `ai_readonly` role, .env.example.
Verified in sandbox (apt Postgres 16 + PostGIS 3.4, GDAL 3.8.4): init SQL and role script apply cleanly; ai_readonly has no access to `raw`, read-only, 15s timeout. Docker itself is untested (no daemon here).

Blockers:
1. Egress denied (proxy 403) for: data.linz.govt.nz, data-aucklandcouncil.opendata.arcgis.com,
   services1.arcgis.com (Auckland Council ArcGIS), www.health.govt.nz, overpass-api.de.
   Fix: environment Network access -> broaden, or add these under Allowed domains.
2. LINZ_API_KEY not provided. Add it as an environment secret/variable.
3. (Resolved) Postgres/PostGIS/GDAL installed via apt. Start with `pg_ctlcluster 16 main start`.
