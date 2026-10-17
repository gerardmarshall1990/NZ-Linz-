#!/bin/bash
# Back up USER DATA only (small): property records and facts with history, upload metadata, plan extractions/calibrations/edits, owner rule answers, plus the uploaded plan files.
# Everything else (raw, derived layers, rules) is rebuilt by `make bootstrap` and is NOT backed up.
# User tables are those named core.rh_*, core.user_*, core.owner_* (tests/test_backup_split.py fails if a table is not classified).
# Output: backups/userdata_<db>_<timestamp>.tar[.gpg]. Set BACKUP_PASSPHRASE in the environment/.env to encrypt (strongly recommended before it leaves the sandbox).
# Never commit the output: backups/ is gitignored. This data is private (property, plan and owner data).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
export PGPASSWORD="$POSTGRES_PASSWORD"
ts=$(date +%Y%m%d_%H%M%S); w=$(mktemp -d); trap 'rm -rf "$w"' EXIT
mkdir -p backups
args=()
for t in $(psql -h "${PGHOST:-localhost}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname='core' AND (tablename LIKE 'rh\_%' OR tablename LIKE 'user\_%' OR tablename LIKE 'owner\_%')"); do args+=(-t "$t"); done
pg_dump -h "${PGHOST:-localhost}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc "${args[@]}" -f "$w/userdata.dump"
up="${UPLOAD_DIR:-uploads}"; [ -d "$up" ] && tar -C "$up" -cf "$w/uploads.tar" . || tar -cf "$w/uploads.tar" -T /dev/null
cp config/rh_property_fields.yaml "$w/" ; cp .env.example "$w/env.example"
tar -C "$w" -cf "backups/userdata_${POSTGRES_DB}_${ts}.tar" userdata.dump uploads.tar rh_property_fields.yaml env.example
out="backups/userdata_${POSTGRES_DB}_${ts}.tar"
if [ -n "${BACKUP_PASSPHRASE:-}" ]; then
  gpg --batch --yes --pinentry-mode loopback --passphrase "$BACKUP_PASSPHRASE" --symmetric --cipher-algo AES256 -o "$out.gpg" "$out" && rm "$out"; out="$out.gpg"
else echo "WARNING: BACKUP_PASSPHRASE not set: backup is NOT encrypted. Do not store it anywhere shared."; fi
echo "user-data backup: $out ($(du -h "$out" | cut -f1))"
