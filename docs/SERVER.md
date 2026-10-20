# Moving to a server (phone steps) and what stays on your side

Status: scripts written and syntax-checked here; **not yet run on a real server**. The first run is done together: you paste, I read what the console prints (send a screenshot) and fix whatever breaks. The restore drill (below) was run for real on this sandbox.

## You do (about 15 minutes, all in Safari)
1. Create a Hetzner Cloud account (or the provider you chose in HOSTING.md) and add a card.
2. Create a server: **Ubuntu 24.04**, at least **4 GB memory and 40 GB disk** (about EUR 6 a month), any location, no extras. Open the server's **Console** button.
3. In Tailscale (login.tailscale.com, Settings, Keys) make a **reusable-off, one-off auth key** for the server.
4. Decide where the off-server backup goes (see below) and get its rclone remote name, or choose "server only for now".
5. In the console, type exactly (values are yours; the first line keeps them out of the history):
   ```
   export HISTFILE=/dev/null
   curl -fsSL https://raw.githubusercontent.com/gerardmarshall1990/NZ-Linz-/claude/new-session-ototl3/deploy/server_setup.sh -o s.sh
   CHECK=1 APP_PASSWORD='...' TS_AUTHKEY='tskey-...' LINZ_API_KEY='...' BACKUP_PASSPHRASE='...' bash s.sh
   ```
   If it says "inputs look fine", run the same line again **without** `CHECK=1`. Add `OFFSITE_REMOTE='remote:folder'` if you have one.
6. The build then runs by itself for **about 3 to 4.5 hours** (downloads and OCR). The app address is `https://nz-linz-server.<your tailnet>.ts.net`. Your saved inputs and property records are put back from a backup file (see "Moving your data").

## What it sets up
Ubuntu packages, a locked-down `nzlinz` user, Postgres with PostGIS in Docker bound to the server itself only, the app as a service that restarts if it dies, a firewall that allows only SSH and Tailscale, a Tailscale address, a nightly 2:46 am encrypted backup (`scripts/nightly_backup.sh`: refuses to run without the passphrase, refuses an unencrypted file, copies to your off-server remote, keeps the newest 30).

## Moving your data from the sandbox
Take a backup here (`make backup`, encrypted with the same `BACKUP_PASSPHRASE`) and put the file on the server as `/opt/nz-linz/restore_this.tar.gpg` before the build finishes; the build service restores it at the end. Until the passphrase is set in the sandbox, tell me and I will make the file.

## Off-server copy (decision needed, otherwise server-only)
Any rclone remote works (Backblaze B2, Google Drive, S3, an SFTP storage box). The file is encrypted before it leaves the server. Server-only is allowed but a server failure then loses your data.

## Restore drill (done)
`bash scripts/restore_drill.sh`: makes a fresh encrypted backup, checks it cannot be read without the passphrase, restores it into an empty scratch database and compares every user table with the live one. Last run: **PASS, 59 user tables identical (73 settings, 3 listings)**.
To restore for real: `bash scripts/restore_userdata.sh <file.tar.gpg>` on a database that has been built (`make bootstrap`, `make app-db`).

## Risks
Untested on a real server; a full rebuild depends on LINZ and Council downloads staying available; if the backup passphrase is lost the backups cannot be opened.
