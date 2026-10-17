# Backups: what is saved and what is rebuilt

**(a) User data: backed up (small).** `make backup` → `backups/userdata_<db>_<time>.tar[.gpg]` containing a dump of the user tables (`core.rh_*` property records, facts and history, upload metadata, plan calibrations/extractions/edits; `core.owner_*` your rule answers; any future `core.user_*` such as leads or scenarios), the uploaded plan files, and the config files. Set `BACKUP_PASSPHRASE` to encrypt with AES-256 (gpg symmetric); keep that passphrase in your password manager, because without it the file cannot be opened. `tests/test_backup_split.py` fails if a new table is not classed as user data or regenerable.

**(b) Regenerable data: not backed up.** `raw.*`, `analytics.*` (rules, chunks, plan versions), `core.sites` and the other derived tables are rebuilt by `make bootstrap` from the original public sources. Your rule answers are replayed after the rebuild (`scripts/replay_owner_review.py`, matched by rule identity, not row id).

**Restore:** `make bootstrap`, then `pg_restore -d <db> --data-only` of `userdata.dump`, and untar `uploads.tar` into `uploads/`. (`make backup-full` still makes a full dump if ever wanted.)

**Privacy:** `backups/`, `uploads/`, `.env` and `data/` are gitignored. This repo can be public: never put the backup file, uploaded plans or property data in it. Store the backup only in a private place you control.

## Off-sandbox copy: encrypted, to a separate PRIVATE GitHub repo (decided)
`make backup-github` (script `scripts/backup_to_github.sh`) makes the user-data backup, encrypts it with gpg (AES-256), checks it really is encrypted and that your passphrase decrypts it, then commits and pushes only `userdata/*.tar.gpg` to the private backup repository. It **refuses** to push when: `BACKUP_PASSPHRASE` is unset or under 16 characters; the file is not an encrypted gpg file or the passphrase cannot open it; the target repo is this project repo; the target repo is public (checked through GitHub's unauthenticated API: a private repo answers 404); or anything other than encrypted files and the README would be committed. Tested in `tests/test_backup_github.sh` against a local repo.

### One-time setup (you)
1. On GitHub create a **private** repository named `nz-linz-private-backups` (empty is fine). I cannot create it: the integration is read/write on the project repo only (403).
2. Tell me it exists; I will attach it to the session and clone it to `backups/github_private`.
3. **Set the passphrase as an environment variable, never in chat or in a file in this repo:**
   - Make a long random passphrase: at least 6 random words or 20+ random characters, from a password manager's generator.
   - In the Claude app: the cloud environment menu in the session's title bar → **Edit** → add an environment variable named exactly `BACKUP_PASSPHRASE` (use *Network secrets* if that section is offered) → save. A **new session** picks it up.
   - **Keep it safe:** store the same passphrase in your password manager (and a second place such as a printed copy in a safe). If it is lost, every backup is unreadable, and I cannot recover it. Do not store it in the backup repo, in this repo, or in an email. If you ever think it leaked, change it and make a fresh backup; old backups stay readable with the old passphrase.
4. Run `make backup-github` after each step (I do this at the end of every step).

### Restore
`gpg -d userdata_<db>_<time>.tar.gpg > backup.tar` (asks for the passphrase), `tar -xf backup.tar`, then `make bootstrap`, `pg_restore -d <db> --data-only userdata.dump`, and untar `uploads.tar` into `uploads/`.

### Plans and uploaded files need a different route
The private repo takes only the encrypted database dump. Uploaded plans, scans and photos (PDF, DXF, images) are large (up to 60 MB each), personal to owners and tenants, and belong in storage built for files; GitHub is a poor fit (100 MB file limit, history never shrinks). Until you choose, `make backup` still bundles `uploads/` into the local encrypted tar, and the app only holds plans in the sandbox. Options for plans: an encrypted file store you control (Google Drive through the connector, with the same gpg encryption before upload), or your phone/computer via the app download. `backup_to_github.sh` already builds its archive without uploads (`INCLUDE_UPLOADS=0`; tested: the pushed archive contains the database dump and config only).

## Other free options (not chosen)
Download the file to your phone each step (zero setup); Google Drive through the connector (15 GB free; encrypt first).
