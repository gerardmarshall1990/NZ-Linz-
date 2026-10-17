#!/bin/bash
# Encrypted user-data backup to a SEPARATE PRIVATE git repository (never this one).
# Needs: BACKUP_PASSPHRASE in the environment (set it in the cloud environment settings; never commit it, never paste it in chat),
#        BACKUP_REPO_DIR = a local clone of the private backup repo (default backups/github_private), already cloned by hand or by the session.
# Refuses to push if: no passphrase, the backup is not an encrypted gpg file, the passphrase cannot decrypt it, the repo is this repo, the repo is public (when checkable), or anything but *.gpg would be committed.
# Plans and uploaded files are NOT pushed here (see docs/BACKUP.md): this repo takes only the encrypted database part of the backup.
set -euo pipefail
cd "$(dirname "$0")/.."
die() { echo "REFUSED: $*" >&2; exit 2; }
[ -n "${BACKUP_PASSPHRASE:-}" ] || die "BACKUP_PASSPHRASE is not set in the environment (see docs/BACKUP.md)"
[ "${#BACKUP_PASSPHRASE}" -ge 16 ] || die "BACKUP_PASSPHRASE is too short (use 16 or more characters)"
REPO="${BACKUP_REPO_DIR:-backups/github_private}"
[ -d "$REPO/.git" ] || die "$REPO is not a git clone of the private backup repository"
URL=$(git -C "$REPO" remote get-url origin 2>/dev/null) || die "the backup clone has no 'origin' remote"
MAIN=$(git remote get-url origin 2>/dev/null || true)
[ "${URL%.git}" != "${MAIN%.git}" ] || die "the backup repository is the same as this project repository"
case "$URL" in *NZ-Linz-*|*nz-linz-) die "the backup repository looks like the project repository" ;; esac
# public repos answer the unauthenticated API with 200; private ones with 404. If we can't tell (offline), we do not block: the owner created it private.
if echo "$URL" | grep -q "github.com[:/]"; then
  slug=$(echo "$URL" | sed -E 's#.*github.com[:/]##; s#\.git$##'); code=$(curl -s -o /dev/null -m 15 -w "%{http_code}" "https://api.github.com/repos/$slug" || echo 000)
  [ "$code" != "200" ] || die "the backup repository $slug is PUBLIC. Make it private first"
fi
export BACKUP_PASSPHRASE
OUT=$(bash scripts/backup_userdata.sh | tail -1 | sed -E 's/.*: (backups\/[^ ]+) .*/\1/')
case "$OUT" in *.tar.gpg) ;; *) die "the backup was not encrypted ($OUT)" ;; esac
[ -f "$OUT" ] || die "backup file missing"
head -c 300 "$OUT" | grep -q "ustar" && die "file contains plaintext tar data"
pk=$(gpg --batch --list-packets "$OUT" 2>&1 || true); echo "$pk" | grep -q "encrypted with 1 passphrase\|symkey enc packet" || die "not a gpg encrypted file"
gpg --batch --pinentry-mode loopback --passphrase "$BACKUP_PASSPHRASE" -d "$OUT" 2>/dev/null | tar -tf - >/dev/null 2>&1 || die "the passphrase cannot decrypt the backup it just made"
mkdir -p "$REPO/userdata"
cp "$OUT" "$REPO/userdata/"
cat > "$REPO/.gitignore" <<'EOT'
*
!.gitignore
!README.md
!userdata/
!userdata/*.tar.gpg
EOT
[ -f "$REPO/README.md" ] || printf '# Encrypted backups\nOnly gpg (AES-256) encrypted files in userdata/. No plaintext, no plans, no keys. Restore: see docs/BACKUP.md in the main project.\n' > "$REPO/README.md"
git -C "$REPO" add .gitignore README.md "userdata/$(basename "$OUT")"
bad=$(git -C "$REPO" diff --cached --name-only | grep -vE '^(\.gitignore|README\.md|userdata/[^/]+\.tar\.gpg)$' || true)
[ -z "$bad" ] || { git -C "$REPO" reset -q; die "would commit unexpected files: $bad"; }
git -C "$REPO" -c user.name="backup" -c user.email="backup@localhost" commit -q -m "encrypted user-data backup $(basename "$OUT")" || echo "nothing new to commit"
git -C "$REPO" push -q origin HEAD
echo "pushed $(basename "$OUT") ($(du -h "$OUT" | cut -f1)) to $URL"
