#!/usr/bin/env python3
"""Re-apply the owner's recorded rule answers (core.owner_review_log) after analytics.rules has been rebuilt. Latest answer per rule wins.
A rule is matched by (zone, section_ref, parameter, status, topic); an answer whose key matches 0 or >1 rules is reported and skipped, never guessed."""
import os
from pathlib import Path
import psycopg
for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
dsn = f"host={os.environ.get('PGHOST','localhost')} dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
with psycopg.connect(dsn) as c:
    if not c.execute("SELECT to_regclass('core.owner_review_log')").fetchone()[0]: print("no review log table: nothing to replay"); raise SystemExit
    rows = c.execute("""SELECT DISTINCT ON (zone, section_ref, parameter, status, topic) zone, section_ref, parameter, status, topic, answer, answered_at
                        FROM core.owner_review_log ORDER BY zone, section_ref, parameter, status, topic, id DESC""").fetchall()
    ok = skipped = 0
    for z, s, p, st, t, ans, at in rows:
        where = "zone IS NOT DISTINCT FROM %s AND section_ref IS NOT DISTINCT FROM %s AND parameter IS NOT DISTINCT FROM %s AND status IS NOT DISTINCT FROM %s AND topic IS NOT DISTINCT FROM %s"
        n = c.execute(f"SELECT count(*) FROM analytics.rules WHERE {where}", (z, s, p, st, t)).fetchone()[0]
        if n != 1: print(f"skipped ({n} matches): {z} / {s} / {p}"); skipped += 1; continue
        c.execute(f"UPDATE analytics.rules SET owner_review=%s, owner_verified=%s, owner_verified_at=%s WHERE {where}", (ans, ans == "correct", at, z, s, p, st, t)); ok += 1
    c.commit(); print(f"replayed {ok} owner answers, skipped {skipped}")
