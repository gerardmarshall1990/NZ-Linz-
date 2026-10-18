"""Map layers (MASTER_SPEC Part 2 and Part 4 map): zones, overlays, hazards and Māori land as GeoJSON for the viewport. Read-only over the Council open-data layers; the bounding box is required and capped so a request cannot pull the whole city;
features are simplified for display (not for measurement). Hazard layers are labelled information only for conversions of existing buildings."""
from fastapi import HTTPException
from .db import conn

OVERLAYS = {"heritage_extent": "ac_ov_heritage_extent", "special_character": "ac_ov_special_character", "mana_whenua": "ac_ov_mana_whenua", "national_grid": "ac_ov_national_grid", "notable_trees": "ac_ov_notable_trees",
            "aircraft_noise": "ac_ov_aircraft_noise", "ridgeline": "ac_ov_ridgeline", "sea": "ac_ov_sea", "stream_management": "ac_ov_stream_mgmt", "precincts": "ac_precinct"}
HAZARDS = {"flood_plains": "ac_hz_flood_plains", "flood_prone": "ac_hz_flood_prone", "flood_sensitive": "ac_hz_flood_sensitive", "coastal_inundation": "ac_hz_coastal_inundation", "landslide": "ac_hz_landslide_large", "liquefaction": "ac_hz_liquefaction", "tsunami": "ac_hz_tsunami"}
MAX_SPAN_DEG = 0.06      # about 6 km: zoom in to see polygons
LIMIT = 500

def kinds() -> dict: return {"zones": "Planning zones", "maori_land": "Māori land (LINZ parcels flagged Māori)", "rest_homes": "Existing certified rest homes (from your HealthCERT export; empty until loaded)", "overlays": sorted(OVERLAYS), "hazards": sorted(HAZARDS), "note": "Hazard layers are information only for conversions of existing buildings."}

def _bbox(b: str) -> tuple:
    try: x0, y0, x1, y1 = [float(v) for v in b.split(",")]
    except Exception: raise HTTPException(422, "bbox must be minLon,minLat,maxLon,maxLat")
    if not (165 <= x0 < x1 <= 179 and -48 <= y0 < y1 <= -34): raise HTTPException(422, "bbox outside New Zealand")
    if x1 - x0 > MAX_SPAN_DEG or y1 - y0 > MAX_SPAN_DEG: raise HTTPException(422, f"zoom in: the view must be under {MAX_SPAN_DEG} degrees across")
    return x0, y0, x1, y1

def get(kind: str, bbox: str, name: str | None = None) -> dict:
    x0, y0, x1, y1 = _bbox(bbox); env = "ST_Transform(ST_MakeEnvelope(%s,%s,%s,%s,4326),2193)"
    with conn() as c:
        if kind == "zones":
            rows = c.execute(f"SELECT jsonb_build_object('zone', COALESCE(l.zone_name, z.zone::text)) AS p, ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(z.geom, 2), 4326), 6)::jsonb AS g FROM raw.ac_zone z LEFT JOIN core.zone_lookup l ON l.code = z.zone WHERE z.geom && {env} LIMIT {LIMIT}", (x0, y0, x1, y1)).fetchall()
        elif kind == "maori_land":
            rows = c.execute(f"SELECT jsonb_build_object('parcel_id', parcel_id, 'address', address, 'zone', zone_name, 'maori_land_linz', maori_land_linz) AS p, ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(geom, 2), 4326), 6)::jsonb AS g FROM core.sites WHERE (maori_land_linz OR zone_name ILIKE '%%ori Purpose%%') AND geom && {env} LIMIT {LIMIT}", (x0, y0, x1, y1)).fetchall()
        elif kind == "rest_homes":
            rows = c.execute("SELECT jsonb_build_object('name', name, 'beds', beds, 'address', address_raw) AS p, ST_AsGeoJSON(ST_MakePoint(lon, lat), 6)::jsonb AS g FROM core.user_rest_home WHERE lon BETWEEN %s AND %s AND lat BETWEEN %s AND %s LIMIT %s", (x0, x1, y0, y1, LIMIT)).fetchall()
        elif kind in ("overlay", "hazard"):
            tab = (OVERLAYS if kind == "overlay" else HAZARDS).get(name or "")
            if not tab: raise HTTPException(422, f"name must be one of {sorted(OVERLAYS if kind == 'overlay' else HAZARDS)}")
            rows = c.execute(f"SELECT to_jsonb(t) - 'geom' - 'ogc_fid' - 'globalid' AS p, ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(geom, 2), 4326), 6)::jsonb AS g FROM raw.{tab} t WHERE geom && {env} LIMIT {LIMIT}", (x0, y0, x1, y1)).fetchall()
        else: raise HTTPException(404, "unknown layer kind")
    feats = [{"type": "Feature", "properties": {k: v for k, v in (r["p"] or {}).items() if not str(k).startswith("shape__")}, "geometry": r["g"]} for r in rows]
    return {"type": "FeatureCollection", "features": feats, "truncated": len(rows) >= LIMIT, "layer": kind + (":" + name if name else ""),
            "note": "Display only (simplified). Source: Auckland Council open data (CC BY 4.0) / LINZ." + (" Hazard flags are information only for conversions of existing buildings." if kind == "hazard" else "")}
