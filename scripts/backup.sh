#!/bin/bash
# pg_dump (custom format, compressed) into ./backups/. Run at the end of every stage.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
mkdir -p backups
out="backups/${POSTGRES_DB}_$(date +%Y%m%d_%H%M%S)${1:+_$1}.dump"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "${PGHOST:-localhost}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$out"
echo "backup written: $out ($(du -h "$out" | cut -f1))"
