"""The building model of a property in metres, from its current human-confirmed extractions. Unscaled levels are reported, never measured."""
from shapely.geometry import Polygon
from .db import conn

def confirmed_levels(parcel_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute("""SELECT x.id, x.level_name, x.model, x.calibrated FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id = x.upload_id
                            WHERE u.parcel_id = %s AND x.status = 'human_confirmed' AND x.superseded_by IS NULL ORDER BY x.id""", (parcel_id,)).fetchall()
    out = []
    for r in rows:
        m = r["model"]; mpp = (m.get("units") or {}).get("metres_per_unit")
        # DXF models are already in metres (coordinates scaled at parse); px-space models are scaled by the calibration
        k = 1.0 if m.get("source") == "dxf" else (float(mpp) if mpp else None)
        rooms = []
        for ro in m["rooms"]:
            poly = [[x * k, y * k] for x, y in ro["polygon"]] if k else None
            rooms.append({"id": ro["id"], "label": ro.get("label"), "type": ro["type"], "polygon_m": poly, "area_m2": ro.get("area_m2")})
        out.append({"extraction_id": r["id"], "level_name": r["level_name"] or f"level of extraction {r['id']}", "calibrated": bool(k), "rooms": rooms,
                    "doors": m.get("doors", []), "exits": m.get("exits", []), "lifts": m.get("lifts", [])})
    return out

def adjacency(rooms: list[dict], dist: float, min_wall: float) -> dict[str, set[str]]:
    polys = {r["id"]: Polygon(r["polygon_m"]).buffer(0) for r in rooms if r["polygon_m"]}
    adj = {k: set() for k in polys}
    ids = list(polys)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if polys[a].distance(polys[b]) > dist: continue
            if polys[a].buffer(dist).intersection(polys[b].boundary).length >= min_wall or polys[b].buffer(dist).intersection(polys[a].boundary).length >= min_wall:
                adj[a].add(b); adj[b].add(a)
    return adj
