#!/usr/bin/env python3
"""Step 1: collect every per-title fact for 2, 4, 6 and 8 Parrish Road from the app's data and live Council services -> data/hazard/parrish/pack_data.json"""
import json, urllib.parse, urllib.request
from shapely.geometry import shape, LineString, Point
from shapely.ops import unary_union
from common import *
import ground
from backend.app.db import conn
from backend.app import devscenarios
UA = {"User-Agent": "nz-linz-research"}; B = "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/"
def get(u, **q): return json.load(urllib.request.urlopen(urllib.request.Request(u + ("?" + urllib.parse.urlencode(q) if q else ""), headers=UA), timeout=120))
def esri(svc, where="1=1", geom=None, fields="*", rgeom=False):
    q = dict(f="json", where=where, outFields=fields, returnGeometry=str(rgeom).lower(), outSR="2193")
    if geom: q.update(geometry=geom, geometryType="esriGeometryEnvelope", inSR="2193", spatialRel="esriSpatialRelIntersects")
    return get(B + svc + "/FeatureServer/0/query", **q).get("features", [])

def main():
    haz = jload(DATA / "hazard_report.json"); out = {"generated": TODAY, "lots": {}, "listing": {}}
    sites = {p: devscenarios.load_site(p) for p in IDS}; U = unary_union([s["poly"] for s in sites.values()]); x0, y0, x1, y1 = U.bounds
    env = f"{x0-150},{y0-150},{x1+150},{y1+150}"
    ofp = [(f["attributes"], shape({"type": "LineString", "coordinates": f["geometry"]["paths"][0]})) for f in esri("Overland_Flow_Paths", geom=env, rgeom=True) if f.get("geometry")]
    sw = {svc: [(f["attributes"], f.get("geometry")) for f in esri(svc, geom=env, fields="SW_ASSET_OWNER,SW_ASSET_TYPE,SW_STATUS,SW_DIAMETER_MM,SW_MATERIAL", rgeom=True)] for svc in ("Stormwater_Pipe", "Stormwater_Catchpit", "Stormwater_Connection", "Stormwater_Manhole_And_Chamber")}
    with conn() as c:
        c.execute("set statement_timeout='120s'")
        for pid in IDS:
            s = sites[pid]; P = s["poly"]; h = haz["lots"][str(pid)]
            r = c.execute("select ac_property_id, ac_valuation_ref, title_no, title_type, appellation, estate_description, zone_name, pc120_proposed_zone, hazard_flags, overlays, precincts, address_count from core.sites where parcel_id=%s", (pid,)).fetchone()
            lot = {"parcel_id": pid, "address": s["address"], "title_no": r["title_no"], "appellation": r["appellation"], "tenure": r["title_type"], "estate": r["estate_description"], "area_m2": h["area_m2"], "zone_operative": r["zone_name"], "overlays_aup": r["overlays"], "precincts": r["precincts"],
                   "ac_property_id": r["ac_property_id"], "valuation_ref": r["ac_valuation_ref"], "capital_value": "UNVERIFIED: Council rating value not in the app (rates data not loaded)"}
            # existing buildings (LINZ outlines)
            lot["buildings"] = {"count": len(s["buildings"]), "footprint_m2": [round(b.area, 1) for b in s["buildings"]]}
            # PC120 property summaries (live)
            pc = {}
            for key, svc in (("notified_nov2025", "PC120NotifiedForRevised_PROD_PropertySummary"), ("amended_aug2026", "PC120Revised_PROD_PropertySummary")):
                f = esri(svc, where=f"PROPERTYID='{r['ac_property_id']}'")
                if f:
                    a = f[0]["attributes"]; pc[key] = {"zone": a.get("Zone1"), "qualifying_matters": [a.get(f"QM{i}") for i in range(1, 16) if a.get(f"QM{i}")], "ftn": a.get("FTN"), "label": a.get("Label1"), "change": a.get("Change")}
            lot["pc120"] = pc
            # flow paths
            near = sorted(((g.distance(P), a, g) for a, g in ofp), key=lambda t: t[0])[:3]
            lot["overland_flow_paths"] = [{"objectid": a["OBJECTID"], "catchment_area_group": a["CatchmentAreaGroup"], "distance_m": round(d, 1), "full_length_m": round(g.length), "inside_lot_m": round(g.intersection(P).length, 1)} for d, a, g in near]
            # location of the flow path in the lot frame (u along the street frontage from its west end, v depth from the street)
            fp = Point(s["front_point"]); pts = list(P.exterior.coords); edges = [LineString([a, b]) for a, b in zip(pts, pts[1:])]
            fe = min(edges, key=lambda e: e.distance(fp)); (ax, ay), (bx, by) = fe.coords[0], fe.coords[-1]
            if ax > bx: ax, ay, bx, by = bx, by, ax, ay
            L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L; vx, vy = -uy, ux
            if (P.centroid.x - ax) * vx + (P.centroid.y - ay) * vy < 0: vx, vy = -vx, -vy
            loc = []
            for d, a, g in near:
                inter = g.intersection(P)
                if inter.is_empty or inter.length < 0.05: continue
                segs = [inter] if inter.geom_type == "LineString" else list(inter.geoms)
                for sg in segs:
                    uv = [((x - ax) * ux + (y - ay) * uy, (x - ax) * vx + (y - ay) * vy) for x, y in sg.coords]
                    loc.append({"objectid": a["OBJECTID"], "length_m": round(sg.length, 1), "u_from_to_m": [round(min(u for u, v in uv), 1), round(max(u for u, v in uv), 1)], "depth_from_street_m": [round(min(v for u, v in uv), 1), round(max(v for u, v in uv), 1)], "frontage_length_m": round(L, 1)})
            lot["flow_path_location_in_lot"] = loc
            # services (Council stormwater network only; Watercare water/wastewater data is not used: licence)
            def nearest(svc):
                best = None
                for a, g in sw[svc]:
                    if not g: continue
                    gg = LineString(g["paths"][0]) if "paths" in g else Point(g["x"], g["y"])
                    d = gg.distance(P)
                    if best is None or d < best[0]: best = (d, a)
                return None if best is None else {"distance_m": round(best[0], 1), "attributes": {k: v for k, v in best[1].items() if v not in (None, "")}}
            lot["services"] = {"stormwater_pipes_within_150m_of_the_four_lots": len(sw["Stormwater_Pipe"]), "nearest_public_stormwater_pipe": nearest("Stormwater_Pipe"), "nearest_stormwater_catchpit": nearest("Stormwater_Catchpit"), "nearest_stormwater_connection": nearest("Stormwater_Connection"), "nearest_stormwater_manhole": nearest("Stormwater_Manhole_And_Chamber"),
                               "smaf_overlay": "not in a Stormwater Management Area Flow overlay (point test at the lot centroid returned no polygon)", "water_supply_and_wastewater": "UNVERIFIED: Watercare network data is not loaded (licence); PC120 flags a Combined Wastewater Network Control qualifying matter on every lot"}
            for k in ("flood_layers", "ground", "contours", "depth_if_filled_to_published_level", "usable_after_clearance", "nearest_flow_paths", "overland_flow_path_total_m", "pc120_proposed_zone"):
                lot[k] = h.get(k)
            out["lots"][str(pid)] = lot
    out["listing"] = {"agent": "Bayleys Real Estate Ltd", "listing_number": "1657716", "price": "by negotiation (not disclosed)", "listed_area_m2_total": 2006, "source": "owner's term sheet dated 10 Nov 2026 (S12); listing page not re-fetched: UNVERIFIED"}
    out["stormwater_pipe_count_150m"] = len(sw["Stormwater_Pipe"]); out["sums"] = {"area_m2": round(sum(l["area_m2"] for l in out["lots"].values()), 1)}
    jdump(out, DATA / "pack_data.json"); print(json.dumps({k: v for k, v in out["lots"]["5098060"].items() if k in ("title_no", "pc120", "flow_path_location_in_lot", "services", "buildings")}, indent=1)[:3000])
if __name__ == "__main__": main()
