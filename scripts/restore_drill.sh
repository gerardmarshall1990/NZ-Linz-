#!/bin/bash
# Restore drill: proves a backup can be restored. Takes a fresh encrypted backup of the live database, restores it into a scratch database that has only the schema, and compares every user table's row count and content hash with the live database. PASS or FAIL.
# Uses a throwaway passphrase for the drill unless BACKUP_PASSPHRASE is set. Drops the scratch database afterwards.
set -uo pipefail
cd "$(dirname "$0")/.."; set -a; . ./.env; set +a
export PGPASSWORD="$POSTGRES_PASSWORD"; H="${PGHOST:-localhost}"; U="$POSTGRES_USER"; D="${POSTGRES_DB}"; S="${D}_drill"
[ -n "${BACKUP_PASSPHRASE:-}" ] || { BACKUP_PASSPHRASE=$(openssl rand -hex 24); export BACKUP_PASSPHRASE; echo "(using a throwaway passphrase for this drill)"; }
out=$(bash scripts/backup_userdata.sh 2>&1 | tail -1); f=$(echo "$out" | sed -n 's/^user-data backup: \([^ ]*\) .*/\1/p'); [ -f "$f" ] || { echo "FAIL: backup not made: $out"; exit 1; }
case "$f" in *.gpg) ;; *) echo "FAIL: backup is not encrypted"; exit 1 ;; esac
file "$f" | grep -qi "gpg\|pgp\|data" && ! tar -tf "$f" >/dev/null 2>&1 || { echo "FAIL: the file is readable without the passphrase"; exit 1; }
psql -h "$H" -U "$U" -d postgres -qc "DROP DATABASE IF EXISTS $S" -c "CREATE DATABASE $S" || exit 1
pg_dump -h "$H" -U "$U" -d "$D" --schema-only | psql -h "$H" -U "$U" -d "$S" -q -v ON_ERROR_STOP=0 >/dev/null 2>&1
# the user tables reference core.sites (and addresses): copy just the referenced rows into the scratch database, as a bootstrapped server already has them
ids=$(for t in $(psql -h "$H" -U "$U" -d "$D" -Atc "SELECT table_name FROM information_schema.columns WHERE table_schema='core' AND column_name='parcel_id' AND (table_name LIKE 'rh\_%' OR table_name LIKE 'user\_%' OR table_name LIKE 'owner\_%')"); do psql -h "$H" -U "$U" -d "$D" -Atc "SELECT parcel_id FROM core.$t WHERE parcel_id IS NOT NULL"; done | sort -u | paste -sd, -)
if [ -n "$ids" ]; then psql -h "$H" -U "$U" -d "$D" -qc "\copy (SELECT * FROM core.sites WHERE parcel_id IN ($ids)) TO STDOUT" | psql -h "$H" -U "$U" -d "$S" -q -c "\copy core.sites FROM STDIN" >/dev/null 2>&1; fi
aids=$(psql -h "$H" -U "$U" -d "$D" -Atc "SELECT address_id FROM core.user_listing WHERE address_id IS NOT NULL" 2>/dev/null | sort -u | paste -sd, -)
if [ -n "$aids" ]; then for at in $(psql -h "$H" -U "$U" -d "$D" -Atc "SELECT n.nspname||'.'||c.relname FROM pg_constraint k JOIN pg_class c ON c.oid=k.confrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_class t ON t.oid=k.conrelid WHERE t.relname='user_listing' AND k.contype='f' AND k.conkey::text LIKE '%' AND c.relname<>'sites'"); do psql -h "$H" -U "$U" -d "$D" -qc "\copy (SELECT * FROM $at) TO STDOUT" 2>/dev/null | psql -h "$H" -U "$U" -d "$S" -q -c "\copy $at FROM STDIN" >/dev/null 2>&1; done; fi
bash scripts/restore_userdata.sh "$f" "$S" >/dev/null 2>&1 || { echo "FAIL: restore step failed"; psql -h "$H" -U "$U" -d postgres -qc "DROP DATABASE IF EXISTS $S"; exit 1; }
tables=$(psql -h "$H" -U "$U" -d "$D" -Atc "SELECT tablename FROM pg_tables WHERE schemaname='core' AND (tablename LIKE 'rh\_%' OR tablename LIKE 'user\_%' OR tablename LIKE 'owner\_%') ORDER BY 1")
bad=0; n=0
for t in $tables; do
  a=$(psql -h "$H" -U "$U" -d "$D" -Atc "SELECT count(*)||':'||coalesce(md5(string_agg(x::text, '|' ORDER BY x::text)),'') FROM core.$t x")
  b=$(psql -h "$H" -U "$U" -d "$S" -Atc "SELECT count(*)||':'||coalesce(md5(string_agg(x::text, '|' ORDER BY x::text)),'') FROM core.$t x" 2>&1)
  n=$((n+1)); [ "$a" = "$b" ] || { echo "  MISMATCH core.$t live=$a restored=$b"; bad=$((bad+1)); }
done
psql -h "$H" -U "$U" -d postgres -qc "DROP DATABASE IF EXISTS $S"
rows=$(psql -h "$H" -U "$U" -d "$D" -Atc "SELECT (SELECT count(*) FROM core.user_setting)||' settings, '||(SELECT count(*) FROM core.user_listing)||' listings'")
[ $bad -eq 0 ] && echo "PASS: encrypted backup restored; $n user tables identical to live ($rows)" || { echo "FAIL: $bad of $n tables differ"; exit 1; }
