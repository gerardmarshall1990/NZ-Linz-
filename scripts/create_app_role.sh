#!/bin/bash
# Create/refresh the limited application role `app_rw` (read core/analytics, write only core.rh_* tables). Password from .env APP_RW_PASSWORD.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
: "${APP_RW_PASSWORD:?set APP_RW_PASSWORD in .env}"
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "${PGHOST:-localhost}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q -v pw="$APP_RW_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE app_rw LOGIN PASSWORD %L', :'pw') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') \gexec
SELECT format('ALTER ROLE app_rw PASSWORD %L', :'pw') \gexec
ALTER ROLE app_rw SET statement_timeout = '30s';
SQL
echo "app_rw ready"
