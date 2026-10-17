#!/usr/bin/env python3
"""Idempotent LINZ WFS -> PostGIS (schema raw) loader for the Auckland extent.

Usage: ingest_linz.py <dataset> [<dataset> ...]   (datasets: parcels buildings addresses titles facilities rail_stations)
Pages are cached under data/linz/<dataset>/ so an interrupted run resumes.
Each dataset is loaded into a fresh raw.<table> (dropped and recreated) so re-runs are safe.
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Auckland region extent, EPSG:2193. WFS URN axis order is northing,easting.
E0, N0, E1, N1 = 1640000, 5850000, 1830000, 6050000
# SLICE_BBOX="minE,minN,maxE,maxN" (EPSG:2193, in .env) loads only that rectangle into a separate cache (data/slice): used to prove `make bootstrap` quickly.
SLICE = os.environ.get("SLICE_BBOX") or next((l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text().splitlines() if l.startswith("SLICE_BBOX=")), "")
if SLICE: E0, N0, E1, N1 = [int(float(v)) for v in SLICE.split(",")]
BBOX = f"{N0},{E0},{N1},{E1},urn:ogc:def:crs:EPSG::2193"
DATA = ROOT / "data" / ("slice" if SLICE else "") / "linz"
PAGE = 5000
DATASETS = {  # name -> (LINZ layer id, raw table, sort key)
    "parcels": ("layer-50772", "linz_parcels", "id"),
    "buildings": ("layer-101290", "linz_buildings", "building_id"),
    "addresses": ("layer-123113", "linz_addresses", "address_id"),
    "titles": ("layer-50804", "linz_titles", "id"),
    "facilities": ("layer-105588", "linz_facilities", "facility_id"),  # hospitals + schools
    "rail_stations": ("layer-50318", "linz_rail_stations", "t50_fid"),
}

def load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

def fetch(layer, sort, start):
    url = (f"https://data.linz.govt.nz/services;key={os.environ['LINZ_API_KEY']}/wfs?service=WFS&version=2.0.0"
           f"&request=GetFeature&typeNames=data.linz.govt.nz:{layer}&outputFormat=application/json"
           f"&srsName=EPSG:2193&count={PAGE}&startIndex={start}&sortBy={sort}&bbox={BBOX}")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"giving up on {layer} startIndex={start}")

def pg_dsn():
    return (f"PG:host=localhost dbname={os.environ['POSTGRES_DB']} "
            f"user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}")

def run(name):
    layer, table, sort = DATASETS[name]
    d = DATA / name
    d.mkdir(parents=True, exist_ok=True)
    start, pages = 0, []
    while True:
        f = d / f"page_{start:08d}.json"
        if not f.exists():
            body = fetch(layer, sort, start)
            tmp = f.with_suffix(".tmp"); tmp.write_bytes(body); tmp.rename(f)
        n = len(json.loads(f.read_bytes())["features"])
        print(f"{name} startIndex={start} n={n}", flush=True)
        pages.append(f)
        if n < PAGE: break
        start += PAGE
    # fresh load
    subprocess.run(["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"],
                    "-c", f"DROP TABLE IF EXISTS raw.{table}"], check=True,
                   env={**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]})
    for i, f in enumerate(pages):
        cmd = ["ogr2ogr", "-f", "PostgreSQL", pg_dsn(), str(f), "-nln", f"raw.{table}", "-t_srs", "EPSG:2193",
               "-lco", "GEOMETRY_NAME=geom", "-lco", "SPATIAL_INDEX=GIST", "-nlt", "PROMOTE_TO_MULTI",
               "-lco", "FID=ogc_fid", "-append" if i else "-overwrite"]
        subprocess.run(cmd, check=True)
    print(f"{name}: loaded {len(pages)} pages into raw.{table}", flush=True)

if __name__ == "__main__":
    load_env()
    for n in sys.argv[1:]:
        run(n)
