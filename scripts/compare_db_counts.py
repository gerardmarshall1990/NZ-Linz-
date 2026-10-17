#!/usr/bin/env python3
"""Compare exact row counts of every table in raw/core/analytics between two databases: compare_db_counts.py <db_a> <db_b>.
User-entered tables (core.rh_*) are listed separately and not counted as differences."""
import os, sys
from pathlib import Path
import psycopg
for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
def counts(db):
    dsn = f"host={os.environ.get('PGHOST','localhost')} dbname={db} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
    out = {}
    with psycopg.connect(dsn, autocommit=True) as c:
        for s, t in c.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('raw','core','analytics') ORDER BY 1,2").fetchall():
            out[f"{s}.{t}"] = c.execute(f'SELECT count(*) FROM "{s}"."{t}"').fetchone()[0]
    return out
a, b = counts(sys.argv[1]), counts(sys.argv[2])
bad = 0
print(f"{'table':44}{sys.argv[1]:>14}{sys.argv[2]:>14}  note")
for t in sorted(set(a) | set(b)):
    x, y = a.get(t), b.get(t); user = t.startswith("core.rh_")
    note = "user data" if user else ("" if x == y else "DIFF"); bad += (not user and x != y)
    print(f"{t:44}{str(x):>14}{str(y):>14}  {note}")
print("tables differing:", bad); sys.exit(1 if bad else 0)
