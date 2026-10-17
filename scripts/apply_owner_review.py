#!/usr/bin/env python3
"""Record the owner's answers from docs/key_standards_check.html (decision 17). Only the owner's pasted answers can set owner_verified.

Usage:  python3 scripts/apply_owner_review.py answers.txt            (dry run: shows what would change)
        python3 scripts/apply_owner_review.py answers.txt --apply    (writes)
Each line is  "<key> => correct|wrong|unsure"  exactly as copied from the page. 'correct' sets owner_verified=true; 'wrong' and 'unsure' set owner_review
and leave owner_verified=false. Dwelling activity-status cards (keys like 'H3.4.1 (A3)|A3') are matched on section_ref + parameter.
"""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1); os.environ.setdefault(k, v)

def psql(sql):
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    return subprocess.run(["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-v", "ON_ERROR_STOP=1", "-At", "-F", "|", "-c", sql], check=True, env=e, capture_output=True, text=True).stdout

def main():
    path, apply = sys.argv[1], "--apply" in sys.argv
    n = {"correct": 0, "wrong": 0, "unsure": 0, "unmatched": 0}; sql = []
    for line in open(path):
        m = re.match(r"^(.*?)\s*=>\s*(correct|wrong|unsure)\s*$", line.strip())
        if not m: continue
        key, ans = m.groups(); parts = key.split("|")
        if len(parts) == 3 and parts[2].isdigit(): where, rid = f"id = {int(parts[2])}", parts[2]
        elif len(parts) == 2: where = f"topic = 'activity_status' AND status = 'operative' AND section_ref = '{parts[0].replace(chr(39), '')}' AND parameter = '{parts[1].replace(chr(39), '')}'"
        else: n["unmatched"] += 1; continue
        found = psql(f"SELECT count(*) FROM analytics.rules WHERE {where}").strip()
        if found == "0": n["unmatched"] += 1; continue
        n[ans] += 1
        sql.append(f"UPDATE analytics.rules SET owner_review = '{ans}', owner_verified = {'true' if ans == 'correct' else 'false'}, owner_verified_at = now() WHERE {where};")
    print(n, "(dry run)" if not apply else "")
    if apply and sql: psql("\n".join(sql)); print("applied", len(sql), "updates")

if __name__ == "__main__":
    main()
