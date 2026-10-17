#!/usr/bin/env python3
"""Load config/rh_requirements.yaml into analytics.rh_requirements (requirement slots; numeric values stay blank until sourced from official documents)."""
import os
from pathlib import Path
import psycopg, yaml
ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
dsn = f"host={os.environ.get('PGHOST','localhost')} dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
reqs = yaml.safe_load((ROOT / "config/rh_requirements.yaml").read_text())["requirements"]
with psycopg.connect(dsn) as c:
    c.execute("TRUNCATE analytics.rh_requirements")
    for r in reqs:
        c.execute("""INSERT INTO analytics.rh_requirements (id, topic, check_kind, fact, operator, unit, value_num, clause, source, source_url, last_verified, signs_off, evidence_needed)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (r["id"], r["topic"], r["check"], r.get("fact"), r.get("operator"), r.get("unit"), r.get("value"), r.get("clause"), r.get("source"), r.get("source_url"), r.get("last_verified"), r.get("signs_off"), r.get("evidence")))
    c.commit(); print(len(reqs), "requirement slots loaded;", sum(1 for r in reqs if r.get("value") is None), "without a sourced value")
