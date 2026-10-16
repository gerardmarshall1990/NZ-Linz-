#!/bin/bash
# Creates the read-only agent role. SELECT on core + analytics only; nothing on raw.
set -euo pipefail
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v pw="$AI_READONLY_PASSWORD" <<'SQL'
CREATE ROLE ai_readonly LOGIN PASSWORD :'pw';
ALTER ROLE ai_readonly SET statement_timeout = '15s';
ALTER ROLE ai_readonly SET default_transaction_read_only = on;
REVOKE ALL ON SCHEMA raw FROM ai_readonly;
GRANT USAGE ON SCHEMA core, analytics TO ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA core, analytics TO ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA core, analytics GRANT SELECT ON TABLES TO ai_readonly;
SQL
