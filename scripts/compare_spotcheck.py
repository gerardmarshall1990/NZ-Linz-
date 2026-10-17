#!/usr/bin/env python3
"""Spot-check values of random parcels in a bbox between two databases: compare_spotcheck.py <db_a> <db_b> minE,minN,maxE,maxN [n].
Compares the derived columns of core.sites (zone, overlays, hazards, buildings, title, plan flags). Exit 1 if any differ."""
import os, sys, random
from pathlib import Path
import psycopg
for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
a, b, bbox = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3].split(",")]; n = int(sys.argv[4]) if len(sys.argv) > 4 else 12
dsn = lambda db: f"host=localhost dbname={db} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
SKIP = set(os.environ.get("SKIP_COLS", "").split(","))   # e.g. dist_hospital_m,dist_rail_m in slice mode (nearest facility can lie outside the slice)
COLS = "parcel_id, zone_name, overlays, hazard_flags, building_count, round(total_footprint_m2::numeric,1) AS footprint, title_type, address, address_count, pc120_depends, pc120_proposed_zone, round(area_m2::numeric,1) AS area, is_reserve, dist_hospital_m, dist_rail_m"
COLS = ", ".join(c for c in COLS.split(", ") if c.split(" AS ")[-1].strip() not in SKIP)
env = f"ST_MakeEnvelope({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},2193)"
with psycopg.connect(dsn(a), autocommit=True) as ca, psycopg.connect(dsn(b), autocommit=True) as cb:
    ids_a = {r[0] for r in ca.execute(f"SELECT parcel_id FROM core.sites WHERE geom && {env} AND ST_Within(ST_PointOnSurface(geom), {env})").fetchall()}
    ids_b = {r[0] for r in cb.execute(f"SELECT parcel_id FROM core.sites WHERE geom && {env} AND ST_Within(ST_PointOnSurface(geom), {env})").fetchall()}
    print(f"parcels with centre inside bbox: {a}={len(ids_a)} {b}={len(ids_b)} only_in_{a}={len(ids_a - ids_b)} only_in_{b}={len(ids_b - ids_a)}")
    common = sorted(ids_a & ids_b); random.seed(7); pick = random.sample(common, min(n, len(common))); bad = 0
    for pid in pick:
        ra = ca.execute(f"SELECT {COLS} FROM core.sites WHERE parcel_id = %s", (pid,)).fetchone(); rb = cb.execute(f"SELECT {COLS} FROM core.sites WHERE parcel_id = %s", (pid,)).fetchone()
        diff = [c for c, x, y in zip([d.name for d in ca.execute(f"SELECT {COLS} FROM core.sites LIMIT 0").description], ra, rb) if x != y]
        bad += bool(diff); print(f"{pid} {ra[7]!s:34} zone={ra[1]!s:46.46} {'OK' if not diff else 'DIFF ' + ','.join(diff)}")
    # whole-slice agreement on key derived fields
    q = f"SELECT count(*), count(zone_name), sum(building_count), count(*) FILTER (WHERE array_length(overlays,1) > 0), count(*) FILTER (WHERE hazard_flags IS NOT NULL AND array_length(hazard_flags,1) > 0) FROM core.sites WHERE geom && {env} AND ST_Within(ST_PointOnSurface(geom), {env})"
    print("aggregates (parcels, with zone, buildings, with overlays, with hazards):", a, ca.execute(q).fetchone(), b, cb.execute(q).fetchone())
print("spot-check differences:", bad); sys.exit(1 if bad else 0)
