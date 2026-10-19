#!/bin/bash
# Keeps Postgres, the app and Tailscale (with `serve`) running; restarts anything that dies. Run it as a background task so it outlives the turn: the sandbox stops loose processes between turns.
cd "$(dirname "$0")/.."; set -a; . ./.env; set +a; TS="$HOME/.tailscale-nzlinz"; mkdir -p "$TS"
while true; do
  pg_isready -q || bash scripts/db_up.sh >/dev/null 2>&1
  curl -fsS -m 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1 || (python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips='*' >> "$TS/app.log" 2>&1 &)
  pgrep -x tailscaled >/dev/null || { ("$TS/tailscaled" --tun=userspace-networking --socket="$TS/ts.sock" --statedir="$TS/state" >> "$TS/tailscaled.log" 2>&1 &); sleep 6; }
  "$TS/tailscale" --socket="$TS/ts.sock" serve status 2>/dev/null | grep -q 8000 || timeout 40 "$TS/tailscale" --socket="$TS/ts.sock" serve --bg --https=443 http://127.0.0.1:8000 >/dev/null 2>&1
  sleep 20
done
