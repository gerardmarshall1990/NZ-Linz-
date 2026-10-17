#!/bin/bash
# Idempotent database setup for bootstrap: create the database if missing, extensions, schemas, and the read-only role grants.
# Works against any reachable PostgreSQL (docker compose db, or the apt cluster in the sandbox). Reads .env; The target database is POSTGRES_DB in .env.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
export PGPASSWORD="$POSTGRES_PASSWORD"
H="${PGHOST:-localhost}"
psql -h "$H" -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q -At -c "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" | grep -q 1 \
  || psql -h "$H" -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE \"$POSTGRES_DB\""
psql -h "$H" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q -f db/init/01_schemas.sql
psql -h "$H" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q -v pw="$AI_READONLY_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE ai_readonly LOGIN PASSWORD %L', :'pw') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') \gexec
SELECT format('ALTER ROLE ai_readonly PASSWORD %L', :'pw') \gexec
ALTER ROLE ai_readonly SET statement_timeout = '15s';
ALTER ROLE ai_readonly SET default_transaction_read_only = on;
REVOKE ALL ON SCHEMA raw FROM ai_readonly;
GRANT USAGE ON SCHEMA core, analytics TO ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA core, analytics TO ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA core, analytics GRANT SELECT ON TABLES TO ai_readonly;
SQL
echo "database $POSTGRES_DB ready"
