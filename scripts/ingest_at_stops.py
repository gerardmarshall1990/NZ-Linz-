#!/usr/bin/env python3
"""Auckland Transport static GTFS -> raw.at_stops (bus/rail/ferry stops with route and trip counts).

Source: https://gtfs.at.govt.nz/gtfs.zip (Auckland Transport open data). The zip is untrusted: it is extracted to data/at_gtfs/x and only read
as CSV. Idempotent: table is dropped and reloaded. Run with: python3 -I scripts/ingest_at_stops.py
"""
import csv, io, os, subprocess, urllib.request, zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data" / "at_gtfs"
URL = "https://gtfs.at.govt.nz/gtfs.zip"

def env():
    for l in (ROOT / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k, v)

def rows(name):
    with zipfile.ZipFile(D / "gtfs.zip") as z, z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

def main():
    env(); D.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 nz-property-research/0.1"})
    with urllib.request.urlopen(req, timeout=300) as r, open(D / "gtfs.zip", "wb") as o:
        o.write(r.read())
    info = next(rows("feed_info.txt"))
    rtype = {r["route_id"]: r["route_type"] for r in rows("routes.txt")}
    trip_route = {t["trip_id"]: t["route_id"] for t in rows("trips.txt")}
    types, routes, trips = defaultdict(set), defaultdict(set), defaultdict(int)
    for st in rows("stop_times.txt"):
        rid = trip_route.get(st["trip_id"])
        if rid is None: continue
        s = st["stop_id"]; types[s].add(rtype[rid]); routes[s].add(rid); trips[s] += 1
    out = io.StringIO(); w = csv.writer(out)
    for s in rows("stops.txt"):
        if s["location_type"] not in ("", "0"): continue
        sid = s["stop_id"]
        w.writerow([sid, s["stop_code"], s["stop_name"], s["stop_lat"], s["stop_lon"], "|".join(sorted(types.get(sid, ()))),
                    len(routes.get(sid, ())), trips.get(sid, 0), info["feed_version"][:40], info["feed_start_date"], info["feed_end_date"]])
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    base = ["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-v", "ON_ERROR_STOP=1", "-q"]
    subprocess.run(base + ["-c", """DROP TABLE IF EXISTS raw.at_stops; CREATE TABLE raw.at_stops (stop_id text, stop_code text, stop_name text,
        lat double precision, lon double precision, route_types text, n_routes int, n_trips int, feed_version text, feed_start text, feed_end text);"""], check=True, env=e)
    subprocess.run(base + ["-c", "\\copy raw.at_stops FROM STDIN WITH (FORMAT csv)"], input=out.getvalue(), text=True, check=True, env=e)
    subprocess.run(base + ["-c", """ALTER TABLE raw.at_stops ADD COLUMN geom geometry(Point,2193);
        UPDATE raw.at_stops SET geom = ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 2193);
        CREATE INDEX ON raw.at_stops USING gist (geom); ANALYZE raw.at_stops;"""], check=True, env=e)
    print("stops loaded; feed", info["feed_start_date"], "to", info["feed_end_date"])

if __name__ == "__main__":
    main()
