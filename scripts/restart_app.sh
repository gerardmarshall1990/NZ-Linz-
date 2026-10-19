#!/usr/bin/env bash
# One-line restart: starts the supervisor (database, app, Tailscale address) if it is not already running. Safe to run twice.
cd "$(dirname "$0")/.."
if pgrep -f '[s]erve_forever.sh' >/dev/null; then echo "already running"; else nohup bash scripts/serve_forever.sh >/dev/null 2>&1 & echo "started"; fi
for i in $(seq 1 45); do curl -sf http://127.0.0.1:8000/api/health >/dev/null && { echo "app is up: https://nz-linz.tailcbf7ad.ts.net"; exit 0; }; sleep 2; done
echo "app did not come up: see ~/.tailscale-nzlinz/app.log"; exit 1
