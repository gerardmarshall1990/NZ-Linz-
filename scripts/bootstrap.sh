#!/bin/bash
# make bootstrap: rebuild every regenerable layer from the original public sources into the POSTGRES_DB named in .env, with per-step timings.
# Inputs needed: .env (LINZ_API_KEY, DB passwords). Optional manual files (docs/sources_manual/) are loaded if present.
# Output: bootstrap_timings.log in the repo root (gitignored) and a final table-count summary.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG=bootstrap_timings.log; : > "$LOG"
T0=$(date +%s)
step() { local n="$1"; shift; local s=$(date +%s); echo "== $n"; "$@"; local e=$(( $(date +%s) - s )); printf '%-28s %6d s\n' "$n" "$e" | tee -a "$LOG"; }
step init_db            bash scripts/init_db.sh
step ingest_linz        make refresh-linz
step ingest_auckland    make refresh-auckland
step core_sites         make core
step rules_corpus       make rules
step owner_review_log    bash -c 'make owner-review-table && python3 scripts/replay_owner_review.py'
step feeds_register     make feeds
step app_tables_roles   make app-db
step manual_sources     make manual
printf '%-28s %6d s\n' TOTAL $(( $(date +%s) - T0 )) | tee -a "$LOG"
