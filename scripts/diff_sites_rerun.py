#!/usr/bin/env python3
"""Compare core.sites now with the snapshot rollback_<date>.sites_before (taken before a re-run of 30_sites_enrich.sql and 50_plan_versions.sql). Read-only.
Reports: parcels whose Council property record changed; PC120 flag changes; any zone or overlay changes (overlays compared as sets); every other column; row counts of all tables vs counts_before.txt; 5 example parcels before/after."""
import os, sys
from pathlib import Path
import psycopg
ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
SCHEMA = sys.argv[1] if len(sys.argv) > 1 else "rollback_20261017"
c = psycopg.connect(f"host=localhost dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}", autocommit=True)
cols = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='core' AND table_name='sites' AND column_name<>'geom' ORDER BY ordinal_position")]
before = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name='sites_before'", (SCHEMA,))}
cols = [x for x in cols if x in before]
n = c.execute("SELECT count(*) FROM core.sites").fetchone()[0]; nb = c.execute(f"SELECT count(*) FROM {SCHEMA}.sites_before").fetchone()[0]
print(f"rows: now {n}, before {nb}; same parcel ids: {c.execute(f'SELECT count(*) FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id)').fetchone()[0]}")
def expr(col): return f"(SELECT array_agg(o ORDER BY o) FROM unnest(s.{col}) o) IS DISTINCT FROM (SELECT array_agg(o ORDER BY o) FROM unnest(b.{col}) o)" if col == "overlays" else f"s.{col} IS DISTINCT FROM b.{col}"
print("\ncolumn changes (parcels), overlays compared as sets:")
for col in cols:
    if col == "parcel_id": continue
    k = c.execute(f"SELECT count(*) FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id) WHERE {expr(col)}").fetchone()[0]
    if k: print(f"  {col:28} {k}")
ov_order = c.execute(f"SELECT count(*) FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id) WHERE s.overlays IS DISTINCT FROM b.overlays").fetchone()[0]
print(f"  (overlays arrays differing in order only or content: {ov_order}; as sets: see overlays line above)")
print("\nzone changes:", c.execute(f"SELECT count(*) FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id) WHERE s.zone_name IS DISTINCT FROM b.zone_name OR s.zone_code IS DISTINCT FROM b.zone_code OR s.zone_group IS DISTINCT FROM b.zone_group").fetchone()[0])
print("property record changed:", c.execute(f"SELECT count(*) FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id) WHERE s.ac_property_id IS DISTINCT FROM b.ac_property_id").fetchone()[0])
print("PC120 flags changed:", c.execute(f"SELECT count(*) FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id) WHERE s.pc120_zone_differs IS DISTINCT FROM b.pc120_zone_differs OR s.pc120_proposed_zone IS DISTINCT FROM b.pc120_proposed_zone OR s.pc120_depends IS DISTINCT FROM b.pc120_depends").fetchone()[0])
print("\nplan status (verdict dependency) before/after:")
print("  after :", c.execute("SELECT verdict_dependency, count(*) FROM analytics.v_site_plan_status GROUP BY 1 ORDER BY 1").fetchall())
print("  before:", c.execute(f"SELECT CASE WHEN pc120_depends THEN 'depends on PC120' ELSE 'PC120 effect not assessed for this zone' END, count(*) FROM {SCHEMA}.sites_before GROUP BY 1 ORDER BY 1").fetchall())
print("\n5 example parcels (changed property record and/or PC120 flags):")
rows = c.execute(f"""SELECT s.parcel_id, s.address, s.zone_name, b.ac_property_id, s.ac_property_id, b.pc120_proposed_zone, s.pc120_proposed_zone, b.pc120_zone_differs, s.pc120_zone_differs, b.pc120_depends, s.pc120_depends
  FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id)
  WHERE s.pc120_zone_differs IS DISTINCT FROM b.pc120_zone_differs OR s.pc120_depends IS DISTINCT FROM b.pc120_depends OR s.pc120_proposed_zone IS DISTINCT FROM b.pc120_proposed_zone
  ORDER BY (s.address IS NULL), s.parcel_id LIMIT 3""").fetchall()
rows += c.execute(f"""SELECT s.parcel_id, s.address, s.zone_name, b.ac_property_id, s.ac_property_id, b.pc120_proposed_zone, s.pc120_proposed_zone, b.pc120_zone_differs, s.pc120_zone_differs, b.pc120_depends, s.pc120_depends
  FROM core.sites s JOIN {SCHEMA}.sites_before b USING (parcel_id) WHERE s.ac_property_id IS DISTINCT FROM b.ac_property_id AND s.pc120_zone_differs IS NOT DISTINCT FROM b.pc120_zone_differs AND s.address IS NOT NULL ORDER BY s.parcel_id LIMIT %s""", (5 - len(rows),)).fetchall()
for r in rows: print(f"  parcel {r[0]} {r[1]} ({r[2]})\n    property id {r[3]} -> {r[4]}\n    PC120 proposed zone {r[5]} -> {r[6]}; zone differs {r[7]} -> {r[8]}; depends {r[9]} -> {r[10]}")
print("\ntable row counts vs before (only differences shown; raw.sub_* are rebuilt derived copies):")
bef = dict(l.split("\t") for l in (ROOT / "backups/rollback/counts_before.txt").read_text().split("\n") if l)
d = 0
for s, t in c.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('raw','core','analytics') ORDER BY 1,2").fetchall():
    nn = c.execute(f"SELECT count(*) FROM {s}.{t}").fetchone()[0]
    if str(nn) != bef.get(f"{s}.{t}"): d += 1; print(f"  {s}.{t}: {bef.get(f'{s}.{t}')} -> {nn}")
print("  tables with different row counts:", d)
