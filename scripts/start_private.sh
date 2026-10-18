#!/bin/bash
# Start the app so it is reachable ONLY from your own devices through Tailscale (private network, free personal plan): nothing is exposed to the public internet.
# Needs these environment variables (set them in the cloud environment settings, never in files or chat): APP_PASSWORD (16+ characters), TS_AUTHKEY (a Tailscale auth key, reusable + ephemeral).
# The app itself listens on 127.0.0.1 only (never all network interfaces); Tailscale forwards https://<name>.<tailnet>.ts.net to it.
set -euo pipefail
cd "$(dirname "$0")/.."
[ "${#APP_PASSWORD}" -ge 12 ] 2>/dev/null || { echo "REFUSED: APP_PASSWORD must be set (12+ characters; 16+ recommended)"; exit 2; }
[ "${#APP_PASSWORD}" -ge 16 ] || echo "WARNING: APP_PASSWORD is under 16 characters: use a longer random one when you can"
[ -n "${TS_AUTHKEY:-}" ] || { echo "REFUSED: TS_AUTHKEY is not set"; exit 2; }
TS_DIR="${TS_DIR:-$HOME/.tailscale-nzlinz}"; mkdir -p "$TS_DIR"
if [ ! -x "$TS_DIR/tailscaled" ]; then
  ver=$(curl -fsS https://pkgs.tailscale.com/stable/ | grep -o 'tailscale_[0-9.]*_amd64.tgz' | head -1)
  curl -fsS -o "$TS_DIR/ts.tgz" "https://pkgs.tailscale.com/stable/$ver" && tar -xzf "$TS_DIR/ts.tgz" -C "$TS_DIR" --strip-components=1 && rm "$TS_DIR/ts.tgz"
fi
pgrep -x tailscaled >/dev/null || (nohup "$TS_DIR/tailscaled" --tun=userspace-networking --socket="$TS_DIR/ts.sock" --statedir="$TS_DIR/state" > "$TS_DIR/tailscaled.log" 2>&1 &)
sleep 3
"$TS_DIR/tailscale" --socket="$TS_DIR/ts.sock" up --authkey="$TS_AUTHKEY" --hostname=nz-linz --ssh=false --accept-dns=false --timeout=60s
pgrep -f "uvicorn backend.app.main:app" >/dev/null || (nohup python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1 > "$TS_DIR/app.log" 2>&1 &)
sleep 2
"$TS_DIR/tailscale" --socket="$TS_DIR/ts.sock" serve --bg --https=443 http://127.0.0.1:8000
"$TS_DIR/tailscale" --socket="$TS_DIR/ts.sock" serve status
echo "Open on your iPhone (Tailscale app connected): https://nz-linz.<your-tailnet>.ts.net  (shown above)"
