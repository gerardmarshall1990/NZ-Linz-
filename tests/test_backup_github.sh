#!/bin/bash
# Test of scripts/backup_to_github.sh against a LOCAL bare repo (no network): refuses without a passphrase, with a short one, into the main repo, and pushes only encrypted files.
set -uo pipefail
cd "$(dirname "$0")/.."
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
git init -q --bare "$T/remote.git"; git clone -q "$T/remote.git" "$T/clone" 2>/dev/null
( cd "$T/clone" && git -c user.name=t -c user.email=t@t commit -q --allow-empty -m init && git push -q origin HEAD 2>/dev/null )
export BACKUP_REPO_DIR="$T/clone"
fail=0
check() { if [ "$2" != "$3" ]; then echo "FAIL: $1 (got $2, want $3)"; fail=1; else echo "ok: $1"; fi; }
env -u BACKUP_PASSPHRASE bash scripts/backup_to_github.sh >/dev/null 2>&1; check "refuses without a passphrase" $? 2
BACKUP_PASSPHRASE=short bash scripts/backup_to_github.sh >/dev/null 2>&1; check "refuses a short passphrase" $? 2
BACKUP_REPO_DIR=/nonexistent BACKUP_PASSPHRASE=0123456789abcdefXYZ bash scripts/backup_to_github.sh >/dev/null 2>&1; check "refuses a missing clone" $? 2
git remote add scratchmain "$(git remote get-url origin)" 2>/dev/null; git remote remove scratchmain
( cd "$T" && git clone -q "$(git -C /home/user/NZ-Linz- remote get-url origin)" "$T/mainclone" 2>/dev/null ) ; [ -d "$T/mainclone/.git" ] && { BACKUP_REPO_DIR="$T/mainclone" BACKUP_PASSPHRASE=0123456789abcdefXYZ bash scripts/backup_to_github.sh >/dev/null 2>&1; check "refuses the project repo" $? 2; } || echo "skip: could not clone the project repo for the refusal test"
BACKUP_PASSPHRASE=0123456789abcdefXYZ bash scripts/backup_to_github.sh >/dev/null 2>&1; check "pushes with a good passphrase" $? 0
files=$(git -C "$T/remote.git" ls-tree -r --name-only HEAD | sort | tr '\n' ' ')
echo "files in remote: $files"
echo "$files" | grep -q "userdata/.*\.tar\.gpg" && check "remote has the encrypted file" 0 0 || check "remote has the encrypted file" 1 0
echo "$files" | tr ' ' '\n' | grep -vE '^(\.gitignore|README\.md|userdata/.*\.tar\.gpg)?$' | grep -q . ; check "remote has nothing but encrypted files and docs" $? 1
f=$(ls "$T"/clone/userdata/*.gpg | head -1)
gpg --batch --pinentry-mode loopback --passphrase 0123456789abcdefXYZ -d "$f" 2>/dev/null | tar -tf - | grep -q userdata.dump; check "backup decrypts and contains the database dump" $? 0
gpg --batch --pinentry-mode loopback --passphrase wrongwrongwrongwrong -d "$f" >/dev/null 2>&1; check "wrong passphrase cannot decrypt" $? 2
git -C "$T/remote.git" log -p --all 2>/dev/null | grep -c "0123456789abcdefXYZ" | { read n; check "passphrase never appears in the repository history" "$n" 0; }
exit $fail
