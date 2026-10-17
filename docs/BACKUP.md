# Backups: what is saved and what is rebuilt

**(a) User data: backed up (small).** `make backup` → `backups/userdata_<db>_<time>.tar[.gpg]` containing a dump of the user tables (`core.rh_*` property records, facts and history, upload metadata, plan calibrations/extractions/edits; `core.owner_*` your rule answers; any future `core.user_*` such as leads or scenarios), the uploaded plan files, and the config files. Set `BACKUP_PASSPHRASE` to encrypt with AES-256 (gpg symmetric); keep that passphrase in your password manager, because without it the file cannot be opened. `tests/test_backup_split.py` fails if a new table is not classed as user data or regenerable.

**(b) Regenerable data: not backed up.** `raw.*`, `analytics.*` (rules, chunks, plan versions), `core.sites` and the other derived tables are rebuilt by `make bootstrap` from the original public sources. Your rule answers are replayed after the rebuild (`scripts/replay_owner_review.py`, matched by rule identity, not row id).

**Restore:** `make bootstrap`, then `pg_restore -d <db> --data-only` of `userdata.dump`, and untar `uploads.tar` into `uploads/`. (`make backup-full` still makes a full dump if ever wanted.)

**Privacy:** `backups/`, `uploads/`, `.env` and `data/` are gitignored. This repo can be public: never put the backup file, uploaded plans or property data in it. Store the backup only in a private place you control.

## Where to store it outside the sandbox (free)
The sandbox network reaches GitHub, GitLab, Codeberg, Bitbucket, Dropbox and Google Drive, but every one needs your credentials, which I will not hold.
1. **Download it to your phone** through the Claude app each time (I send the file at the end of each step). Zero setup.
2. **Google Drive** (15 GB free): I can copy the encrypted file into your Drive through the Drive connector already available, only when you say so.
3. **A private GitHub repo** (free, separate from this public one) holding only encrypted backups (files under 100 MB). Needs you to create it and give the session access.
