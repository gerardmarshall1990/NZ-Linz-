#!/usr/bin/env python3
"""Idempotent Auckland Council ArcGIS FeatureServer -> PostGIS (schema raw) loader.

Usage: ingest_auckland.py <key> [<key> ...]   or   ingest_auckland.py all
Pages cached in data/auckland/<key>/ (resumable). Each table is dropped and reloaded, so re-runs are safe.
Source: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services (Auckland Council open data, CC BY 4.0).
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services"
PAGE = 2000
SLICE = os.environ.get("SLICE_BBOX") or next((l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text().splitlines() if l.startswith("SLICE_BBOX=")), "")  # "minE,minN,maxE,maxN" EPSG:2193: slice mode (separate cache)
DATA = ROOT / "data" / ("slice" if SLICE else "") / "auckland"
# key -> (service, layer id)
LAYERS = {
    "zone": ("Unitary_Plan_Base_Zone", 0),
    "precinct": ("Precincts", 0),
    "boundary_local_board": ("LocalBoardBoundaries_PROD", 0),
    "property": ("AC_Property_Query", 0),
    "ov_heritage_place": ("Historic_Heritage_Overlay_Place", 0),
    "ov_heritage_extent": ("Historic_Heritage_Overlay_Extent_of_Place", 0),
    "ov_sea": ("Significant_Ecological_Areas_Overlay", 0),
    "ov_special_character": ("Special_Character_Areas_Overlay_Residential_and_Business", 0),
    "ov_volcanic_regional": ("Regionally_Significant_Volcanic_Viewshafts_And_Height_Sensitive_Areas_Overlay", 0),
    "ov_volcanic_local": ("Locally_Significant_Volcanic_Viewshafts_Overlay", 0),
    "ov_onl": ("Outstanding_Natural_Landscapes_Overlay", 0),
    "ov_onf": ("Outstanding_Natural_Features_Overlay", 0),
    "ov_onc": ("Outstanding_Natural_Character_Overlay", 0),
    "ov_hnc": ("High_Natural_Character_Overlay", 0),
    "ov_ridgeline": ("Ridgeline_Protection_Overlay", 0),
    "ov_national_grid": ("National_Grid_Corridor_Overlay", 0),
    "ov_notable_trees": ("Notable_Trees_Overlay", 0),
    "ov_notable_tree_groups": ("Notable_Group_of_Trees_Overlay", 0),
    "ov_aircraft_noise": ("Aircraft_Noise_Overlay", 0),
    "ov_mana_whenua": ("Sites_and_Places_of_Significance_to_Mana_Whenua_Overlay", 0),
    "ov_waitakere": ("Waitakere_Ranges_Heritage_Area_Overlay", 0),
    "ov_quarry_buffer": ("Quarry_Buffer_Area_Overlay", 0),
    "ov_stream_mgmt": ("Natural_Stream_Management_Areas_Overlay", 0),
    "hz_flood_plains": ("Flood_Plains", 0),
    "hz_flood_prone": ("Flood_Prone_Areas", 0),
    "hz_flood_sensitive": ("Flood_Sensitive_Areas", 0),
    "hz_coastal_inundation": ("Coastal_Inundation_1_per_cent_AEP_Plus_1m_Control", 0),
    "hz_landslide_large": ("Large_Scale_Landslide_Susceptibility", 0),
    "hz_liquefaction": ("Liquefaction_Vulnerability_Calibrated_Assessment", 0),
    "hz_tsunami": ("Tsunami_Evacuation_Zone", 0),
}

def load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1); os.environ.setdefault(k, v)

def fetch(service, layer, offset):
    params = {"where": "1=1", "outFields": "*", "outSR": 2193, "f": "geojson", "resultOffset": offset, "resultRecordCount": PAGE, "orderByFields": "OBJECTID"}
    if SLICE: params.update({"geometry": SLICE, "geometryType": "esriGeometryEnvelope", "inSR": 2193, "spatialRel": "esriSpatialRelIntersects"})
    q = urllib.parse.urlencode(params)
    url = f"{BASE}/{service}/FeatureServer/{layer}/query?{q}"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                body = r.read()
            json.loads(body)  # validate
            return body
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"giving up on {service} offset={offset}")

GEOM = {"esriGeometryPolygon": "MultiPolygon", "esriGeometryPoint": "MultiPoint", "esriGeometryMultipoint": "MultiPoint", "esriGeometryPolyline": "MultiLineString"}
SQLTYPE = {"esriFieldTypeInteger": "integer", "esriFieldTypeSmallInteger": "integer", "esriFieldTypeDouble": "double precision", "esriFieldTypeSingle": "double precision", "esriFieldTypeOID": "integer"}

def create_empty(service, layer, table, env):
    """A layer with no features in the requested extent (slice mode, or a layer that is empty upstream) still gets its table, with the layer's own columns, so later SQL never fails on a missing relation."""
    meta = json.load(urllib.request.urlopen(f"{BASE}/{service}/FeatureServer/{layer}?f=json", timeout=120))
    cols = ", ".join(f'"{f["name"].lower()}" {SQLTYPE.get(f["type"], "text")}' for f in meta["fields"] if f["name"].lower() != "ogc_fid")
    g = GEOM.get(meta.get("geometryType"), "Geometry")
    sql = f"DROP TABLE IF EXISTS raw.{table}; CREATE TABLE raw.{table} (ogc_fid serial PRIMARY KEY, geom geometry({g}, 2193), {cols}); CREATE INDEX ON raw.{table} USING gist (geom);"
    subprocess.run(["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-v", "ON_ERROR_STOP=1", "-qc", sql], check=True, env=env)

def run(key):
    service, layer = LAYERS[key]
    table = f"ac_{key}"
    d = DATA / key; d.mkdir(parents=True, exist_ok=True)
    offset, pages = 0, []
    while True:
        f = d / f"page_{offset:08d}.json"
        if not f.exists():
            tmp = f.with_suffix(".tmp"); tmp.write_bytes(fetch(service, layer, offset)); tmp.rename(f)
        n = len(json.loads(f.read_bytes())["features"])
        pages.append(f)
        if n == 0: pages.pop(); break
        offset += n
        if n < PAGE and not json.loads(f.read_bytes()).get("exceededTransferLimit"): break
    env = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    subprocess.run(["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"],
                    "-qc", f"DROP TABLE IF EXISTS raw.{table}"], check=True, env=env)
    if not pages: create_empty(service, layer, table, env); print(f"{key}: no features in this extent -> empty raw.{table}", flush=True); return
    dsn = (f"PG:host=localhost dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} "
           f"password={os.environ['POSTGRES_PASSWORD']}")
    for i, f in enumerate(pages):
        subprocess.run(["ogr2ogr", "-f", "PostgreSQL", dsn, str(f), "-nln", f"raw.{table}", "-t_srs", "EPSG:2193",
                        "-lco", "GEOMETRY_NAME=geom", "-lco", "SPATIAL_INDEX=GIST", "-nlt", "PROMOTE_TO_MULTI",
                        "-lco", "FID=ogc_fid", "-append" if i else "-overwrite"], check=True)
    print(f"{key}: {len(pages)} pages -> raw.{table}", flush=True)

if __name__ == "__main__":
    load_env()
    keys = list(LAYERS) if sys.argv[1:] == ["all"] else sys.argv[1:]
    for k in keys: run(k)
