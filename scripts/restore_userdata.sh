#!/bin/bash
# Restore a user-data backup (backups/userdata_*.tar or .tar.gpg) into a database. Usage: scripts/restore_userdata.sh <backup file> [target database]
# Decrypts with BACKUP_PASSPHRASE when the file ends in .gpg. Recreates the user tables (core.rh_*, core.user_*, core.owner_*) from the dump and untars the uploaded plans into UPLOAD_DIR (default uploads/).
# The target database must already have the app schema (make bootstrap / make app-db) so the other tables exist. Existing user tables in the target are REPLACED by the backup.
set -euo pipefail
cd "$(dirname "$0")/.."
f="${1:?usage: restore_userdata.sh <backup file> [target database]}"; set -a; . ./.env; set +a
db="${2:-$POSTGRES_DB}"; export PGPASSWORD="$POSTGRES_PASSWORD"; w=$(mktemp -d); trap 'rm -rf "$w"' EXIT
case "$f" in
  *.gpg) [ -n "${BACKUP_PASSPHRASE:-}" ] || { echo "BACKUP_PASSPHRASE is not set: cannot decrypt"; exit 2; }
         gpg --batch --yes --pinentry-mode loopback --passphrase "$BACKUP_PASSPHRASE" -d -o "$w/b.tar" "$f" 2>/dev/null || { echo "decryption failed: wrong passphrase or damaged file"; exit 3; } ;;
  *) cp "$f" "$w/b.tar" ;;
esac
tar -C "$w" -xf "$w/b.tar"; [ -f "$w/userdata.dump" ] || { echo "no userdata.dump inside the backup"; exit 4; }
pg_restore -h "${PGHOST:-localhost}" -U "$POSTGRES_USER" -d "$db" --clean --if-exists --no-owner --exit-on-error "$w/userdata.dump"
if [ -f "$w/uploads.tar" ]; then mkdir -p "${UPLOAD_DIR:-uploads}"; tar -C "${UPLOAD_DIR:-uploads}" -xf "$w/uploads.tar"; fi
echo "restored $f into database $db"
