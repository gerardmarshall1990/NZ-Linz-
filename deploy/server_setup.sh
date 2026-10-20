#!/usr/bin/env bash
# One-command setup of a fresh Ubuntu 24.04 server (run as root, from the provider's web console on your phone). NOT yet tested on a real server: run with CHECK=1 first.
# Usage (type the values; the first line keeps them out of the shell history):
#   export HISTFILE=/dev/null
#   curl -fsSL https://raw.githubusercontent.com/gerardmarshall1990/NZ-Linz-/claude/new-session-ototl3/deploy/server_setup.sh -o s.sh
#   APP_PASSWORD='...' TS_AUTHKEY='tskey-...' LINZ_API_KEY='...' BACKUP_PASSPHRASE='...' [OFFSITE_REMOTE='b2:bucket/path'] bash s.sh
# Optional: ANTHROPIC_API_KEY, ANTHROPIC_MODEL, REPO_BRANCH (default claude/new-session-ototl3), TS_HOSTNAME (default nz-linz-server), CHECK=1 (only check the inputs).
set -euo pipefail
need() { [ -n "${!1:-}" ] || { echo "MISSING: $1"; miss=1; }; }
miss=0; APP_PASSWORD="${APP_PASSWORD:-}"; BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"; TS_AUTHKEY="${TS_AUTHKEY:-}"; LINZ_API_KEY="${LINZ_API_KEY:-}"; for v in APP_PASSWORD TS_AUTHKEY LINZ_API_KEY BACKUP_PASSPHRASE; do need $v; done
[ "${#APP_PASSWORD}" -ge 12 ] || { echo "APP_PASSWORD must be at least 12 characters"; miss=1; }
[ "${#BACKUP_PASSPHRASE}" -ge 16 ] || { echo "BACKUP_PASSPHRASE must be at least 16 characters (a long random phrase)"; miss=1; }
. /etc/os-release; [ "${ID}" = ubuntu ] && [ "${VERSION_ID%%.*}" -ge 24 ] || { echo "needs Ubuntu 24.04 or newer (this is ${PRETTY_NAME})"; miss=1; }
[ "$(id -u)" = 0 ] || { echo "run as root"; miss=1; }
[ $miss = 0 ] || exit 2
[ "${CHECK:-0}" = 1 ] && { echo "inputs look fine; nothing was changed"; exit 0; }
BRANCH="${REPO_BRANCH:-claude/new-session-ototl3}"; TSH="${TS_HOSTNAME:-nz-linz-server}"; APP=/opt/nz-linz
echo "== 1/8 packages"; export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq git curl gnupg ca-certificates python3-venv python3-pip build-essential libpq-dev poppler-utils tesseract-ocr docker.io docker-compose-v2 ufw make rclone postgresql-client unattended-upgrades >/dev/null
echo "== 2/8 user and code"; id nzlinz >/dev/null 2>&1 || useradd -m -s /bin/bash nzlinz; usermod -aG docker nzlinz
mkdir -p $APP && chown nzlinz:nzlinz $APP
sudo -u nzlinz bash -c "cd $APP && { [ -d app/.git ] && git -C app fetch -q origin $BRANCH && git -C app checkout -q $BRANCH && git -C app reset -q --hard origin/$BRANCH || git clone -q -b $BRANCH https://github.com/gerardmarshall1990/NZ-Linz-.git app; }"
echo "== 3/8 python"; sudo -u nzlinz bash -c "cd $APP && python3 -m venv venv && venv/bin/pip install -q --upgrade pip && { venv/bin/pip install -q -r app/requirements.txt || venv/bin/pip install -q \$(sed 's/==.*//; /^#/d' app/requirements.txt); }"
echo "== 4/8 settings (.env, mode 600)"; rnd() { head -c 24 /dev/urandom | base64 | tr -d '/+=' | cut -c1-24; }
E="$APP/app/.env"; PGP=$(rnd); AIP=$(rnd); RWP=$(rnd)
cat > "$E" <<ENV
LINZ_API_KEY=$LINZ_API_KEY
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-}
POSTGRES_DB=nzprop
POSTGRES_USER=nzprop_admin
POSTGRES_PASSWORD=$PGP
AI_READONLY_PASSWORD=$AIP
APP_RW_PASSWORD=$RWP
DATABASE_URL=postgresql://nzprop_admin:$PGP@127.0.0.1:5432/nzprop
AI_DATABASE_URL=postgresql://ai_readonly:$AIP@127.0.0.1:5432/nzprop
APP_PASSWORD=$APP_PASSWORD
TS_AUTHKEY=$TS_AUTHKEY
BACKUP_PASSPHRASE=$BACKUP_PASSPHRASE
UPLOAD_DIR=$APP/uploads
OFFSITE_REMOTE=${OFFSITE_REMOTE:-}
ENV
chown nzlinz:nzlinz "$E"; chmod 600 "$E"; mkdir -p $APP/uploads $APP/backups; chown -R nzlinz:nzlinz $APP/uploads $APP/backups
echo "== 5/8 database (Postgres + PostGIS in Docker, local only)"
sed 's#\["5432:5432"\]#["127.0.0.1:5432:5432"]#' $APP/app/docker-compose.yml > $APP/app/docker-compose.server.yml; chown nzlinz:nzlinz $APP/app/docker-compose.server.yml
sudo -u nzlinz bash -c "cd $APP/app && docker compose -f docker-compose.server.yml up -d"
for i in $(seq 1 60); do docker ps --format '{{.Status}}' | grep -q healthy && break; sleep 3; done
echo "== 6/8 firewall and private address"; ufw --force reset >/dev/null; ufw default deny incoming >/dev/null; ufw allow OpenSSH >/dev/null; ufw allow in on tailscale0 >/dev/null 2>&1 || true; ufw --force enable >/dev/null
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh >/dev/null
tailscale up --authkey="$TS_AUTHKEY" --hostname="$TSH" --accept-dns=false; ufw allow in on tailscale0 >/dev/null
echo "== 7/8 services"
install -m 644 $APP/app/deploy/nz-linz-app.service /etc/systemd/system/; install -m 644 $APP/app/deploy/nz-linz-bootstrap.service /etc/systemd/system/
install -m 644 $APP/app/deploy/nz-linz-backup.service /etc/systemd/system/; install -m 644 $APP/app/deploy/nz-linz-backup.timer /etc/systemd/system/
systemctl daemon-reload; systemctl enable --now nz-linz-backup.timer >/dev/null
systemctl enable --now nz-linz-bootstrap.service
echo "== 8/8 done: the data build runs in the background (about 3 to 4.5 hours: downloads, OCR). Check with: systemctl status nz-linz-bootstrap  or  tail -f $APP/app/bootstrap_timings.log"
echo "The app and the private address (https://$TSH.<your-tailnet>.ts.net) start by themselves once the build finishes."
