#!/usr/bin/env bash
# Nightly: encrypted user-data backup, copy to OFFSITE_REMOTE (an rclone remote such as b2:bucket/nz-linz) if set, keep the newest 30 local copies. Refuses to run without BACKUP_PASSPHRASE.
set -euo pipefail
cd "$(dirname "$0")/.."; set -a; . ./.env; set +a
[ -n "${BACKUP_PASSPHRASE:-}" ] || { echo "REFUSED: BACKUP_PASSPHRASE is not set, so the backup would not be encrypted"; exit 2; }
out=$(bash scripts/backup_userdata.sh | tail -1); f=$(echo "$out" | sed -n 's/^user-data backup: \([^ ]*\) .*/\1/p'); case "$f" in *.gpg) ;; *) echo "REFUSED: backup is not encrypted"; exit 3 ;; esac
echo "$out"
if [ -n "${OFFSITE_REMOTE:-}" ]; then rclone copy "$f" "$OFFSITE_REMOTE" --quiet && echo "copied off the server to $OFFSITE_REMOTE" || { echo "OFF-SERVER COPY FAILED"; exit 4; }
else echo "NOTE: OFFSITE_REMOTE is not set: this backup exists only on this server"; fi
ls -1t backups/userdata_*.tar.gpg 2>/dev/null | tail -n +31 | xargs -r rm -f
