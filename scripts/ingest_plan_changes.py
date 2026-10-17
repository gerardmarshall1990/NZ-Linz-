#!/usr/bin/env python3
"""Load Auckland Council plan-change property summaries (attributes only, no geometry) into raw.ac_pc_*.

These layers say, per property, which zone/qualifying matters a plan change proposes or applies. They are used to test whether
core.sites (built from Unitary_Plan_Base_Zone) is current. Idempotent: each table is dropped and reloaded.
"""
import csv, io, json, os, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services"
LAYERS = {  # table suffix -> service
    "pc78_withdrawal": "PC78withdrawal_Property_SummaryPROD",
    "pc120_notified": "RPC_PROD_Plan_Change_Property_Summary",
    "pc120_revised": "PC120Revised_PROD_PropertySummary",
}
PAGE = 2000
SLICE = os.environ.get("SLICE_BBOX") or next((l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text().splitlines() if l.startswith("SLICE_BBOX=")), "")  # slice mode: only properties intersecting this EPSG:2193 rectangle

def env():
    for l in (ROOT / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k, v)

def get(url):
    for a in range(6):
        try:
            return json.load(urllib.request.urlopen(url, timeout=300))
        except Exception:
            time.sleep(2 ** a)
    raise RuntimeError(url)

def run(key, svc):
    meta = get(f"{BASE}/{svc}/FeatureServer/0?f=json")
    cols = [f["name"] for f in meta["fields"] if f["name"] not in ("OBJECTID", "GlobalID", "Shape__Area", "Shape__Length")]
    rows, off = [], 0
    while True:
        params = {"where": "1=1", "outFields": ",".join(cols), "returnGeometry": "false", "f": "json", "resultOffset": off, "resultRecordCount": PAGE, "orderByFields": "OBJECTID"}
        if SLICE: params.update({"geometry": SLICE, "geometryType": "esriGeometryEnvelope", "inSR": 2193, "spatialRel": "esriSpatialRelIntersects"})
        q = urllib.parse.urlencode(params)
        feats = get(f"{BASE}/{svc}/FeatureServer/0/query?{q}")["features"]
        rows += [[(f["attributes"].get(c) or "") for c in cols] for f in feats]
        off += len(feats)
        if len(feats) < PAGE: break
    t = f"raw.ac_{key}"
    ddl = f"DROP TABLE IF EXISTS {t}; CREATE TABLE {t} (" + ", ".join(f'"{c.lower()}" text' for c in cols) + ");"
    buf = io.StringIO(); csv.writer(buf).writerows(rows)
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    base = ["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-v", "ON_ERROR_STOP=1", "-q"]
    subprocess.run(base + ["-c", ddl], check=True, env=e)
    subprocess.run(base + ["-c", f"\\copy {t} FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue(), text=True, check=True, env=e)
    print(f"{key}: {len(rows)} rows from {svc} (service dataEdit {meta.get('editingInfo',{}).get('dataLastEditDate')})", flush=True)

if __name__ == "__main__":
    env()
    for k, s in LAYERS.items(): run(k, s)
