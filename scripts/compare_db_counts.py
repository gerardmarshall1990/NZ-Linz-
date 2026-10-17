#!/usr/bin/env python3
"""Compare exact row counts of every table in raw/core/analytics between two databases: compare_db_counts.py <db_a> <db_b> [minE,minN,maxE,maxN].
With a bbox (EPSG:2193) tables with a geom column are counted only where they intersect it, so a slice database can be compared with the full one.
User-entered tables (core.rh_*) are listed separately and not counted as differences."""
import os, sys
from pathlib import Path
import psycopg
for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
BBOX = sys.argv[3] if len(sys.argv) > 3 else None
def counts(db):
    dsn = f"host={os.environ.get('PGHOST','localhost')} dbname={db} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
    out = {}
    with psycopg.connect(dsn, autocommit=True) as c:
        for s, t in c.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('raw','core','analytics') ORDER BY 1,2").fetchall():
            has_geom = c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND column_name='geom'", (s, t)).fetchone()
            w = f" WHERE geom && ST_MakeEnvelope({','.join(BBOX.split(','))},2193) AND ST_Intersects(geom, ST_MakeEnvelope({','.join(BBOX.split(','))},2193))" if (BBOX and has_geom) else ""
            out[f"{s}.{t}"] = c.execute(f'SELECT count(*) FROM "{s}"."{t}"{w}').fetchone()[0]
    return out
a, b = counts(sys.argv[1]), counts(sys.argv[2])
bad = 0
print(f"{'table':44}{sys.argv[1]:>14}{sys.argv[2]:>14}  note")
for t in sorted(set(a) | set(b)):
    x, y = a.get(t), b.get(t); user = t.startswith("core.rh_")
    note = "user data" if user else ("" if x == y else "DIFF"); bad += (not user and x != y)
    print(f"{t:44}{str(x):>14}{str(y):>14}  {note}")
print("tables differing:", bad); sys.exit(1 if bad else 0)
