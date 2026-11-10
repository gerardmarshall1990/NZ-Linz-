#!/usr/bin/env python3
"""Hazard and relocatable-capacity report for a set of titles (screening only, not a flood or engineering report).
Usage: python3 scripts/hazard_report.py <out_dir> <parcel_id> [<parcel_id> ...]
For each title: zone and area (core.sites), Council flood plain / flood prone / flood sensitive layers (raw.ac_hz_*), Council Overland Flow Paths (live ArcGIS service, centrelines only),
LiDAR DEM from LINZ NZ Elevation (1 m, EPSG:2193) for ground level, slope and contours, the ground left after keeping a clearance corridor around each flow path, and how many
relocatable units of 60 m2 the layout engine fits (lot by lot and amalgamated), using the same zone rules as the Develop tab. Every assumption is written into the output."""
import json, math, os, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path
import numpy as np
from shapely import wkt as shp_wkt
from shapely.geometry import shape, LineString, Polygon, MultiPolygon, box
from shapely.ops import unary_union
ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
sys.path.insert(0, str(ROOT))
from backend.app.db import conn
from backend.app import devscenarios, devlayout, devrules

UA = {"User-Agent": "nz-linz-research"}
OFP_URL = "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Overland_Flow_Paths/FeatureServer/0"
DEM_COLLECTION = "https://nz-elevation.s3.ap-southeast-2.amazonaws.com/auckland/auckland-part-1_2024/dem_1m/2193/"
CLEARANCE_M = (1.0, 2.0, 3.0)            # each side of the published centreline: ASSUMPTIONS, the Council layer has no width
BASE_CLEARANCE_M = 2.0
SHAPES = [(4.0, 15.0), (5.0, 12.0), (6.0, 10.0)]          # width x depth m, all 60 m2: ASSUMED relocatable footprints
UNIT_EXTRA = {"height_m": 3.8, "wall_height_m": 2.7, "gfa_m2": 60, "bedrooms": 2}
ACCESS_WIDTH_M = 3.5

def sh(cmd, **kw): return subprocess.run(cmd, check=True, capture_output=True, text=True, env={**os.environ, "CURL_CA_BUNDLE": "/root/.ccr/ca-bundle.crt", "GDAL_HTTP_PROXY": os.environ.get("HTTPS_PROXY", ""), "GDAL_HTTP_CAINFO": "/root/.ccr/ca-bundle.crt"}, **kw)

def find_tile(lon, lat):
    d = json.load(urllib.request.urlopen(urllib.request.Request(DEM_COLLECTION + "collection.json", headers=UA), timeout=60))
    for l in (x for x in d["links"] if x["rel"] == "item"):
        u = DEM_COLLECTION + l["href"].lstrip("./")
        j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60)); b = j["bbox"]
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]:
            return u, j, DEM_COLLECTION + j["assets"]["visual"]["href"].lstrip("./")
    raise SystemExit("no DEM tile covers the point")

def read_asc(path):
    with open(path) as f:
        h = {}
        for _ in range(6):
            k, v = f.readline().split(); h[k.lower()] = float(v)
        a = np.loadtxt(f)
    return h, a

def pix_xy(h):
    n, m = int(h["nrows"]), int(h["ncols"]); cs = h["cellsize"]
    xs = h["xllcorner"] + (np.arange(m) + .5) * cs; ys = h["yllcorner"] + (n - np.arange(n) - .5) * cs
    return np.meshgrid(xs, ys)

def main(out, ids):
    out = Path(out); out.mkdir(parents=True, exist_ok=True); res = {"assumptions": [], "lots": {}, "sources": {}}
    sites = {i: devscenarios.load_site(i) for i in ids}
    union_all = unary_union([s["poly"] for s in sites.values()]); minx, miny, maxx, maxy = union_all.bounds; pad = 40
    # ---- LiDAR DEM window
    with conn() as c:
        c.execute("set statement_timeout='120s'")
        r = c.execute("select ST_X(ST_Transform(ST_Centroid(ST_Collect(geom)),4326)) lon, ST_Y(ST_Transform(ST_Centroid(ST_Collect(geom)),4326)) lat from core.sites where parcel_id = any(%s)", (ids,)).fetchone()
    item_url, item, tif = find_tile(r["lon"], r["lat"])
    res["sources"]["dem"] = {"name": "LINZ NZ Elevation, Auckland part 1 2024, 1 m DEM (LiDAR-derived, bare earth)", "item": item_url, "file": tif, "captured": f"{item['properties'].get('start_datetime')} to {item['properties'].get('end_datetime')}", "crs": "EPSG:2193 (NZTM2000)", "vertical datum": "NZVD2016 (assumed for the 2024 survey; confirm in the tile metadata)", "licence": "CC BY 4.0 LINZ"}
    dem = out / "dem.tif"; sh(["gdal_translate", "-q", "-projwin", str(minx - pad), str(maxy + pad), str(maxx + pad), str(miny - pad), "/vsicurl/" + tif, str(dem)])
    sh(["gdal_translate", "-q", "-of", "AAIGrid", str(dem), str(out / "dem.asc")]); sh(["gdaldem", "slope", str(dem), str(out / "slope.tif"), "-p", "-compute_edges", "-q"]); sh(["gdal_translate", "-q", "-of", "AAIGrid", str(out / "slope.tif"), str(out / "slope.asc")])
    sh(["gdal_contour", "-q", "-a", "elev", "-i", "0.1", "-f", "GeoJSON", str(dem), str(out / "contours_0.1m.geojson")])
    h, Z = read_asc(out / "dem.asc"); _, S = read_asc(out / "slope.asc"); X, Y = pix_xy(h); nod = h.get("nodata_value", -9999)
    contours = [(float(f["properties"]["elev"]), shape(f["geometry"])) for f in json.load(open(out / "contours_0.1m.geojson"))["features"]]
    # ---- overland flow paths (live Council service, centrelines in EPSG:2193)
    q = {"f": "geojson", "where": "1=1", "geometry": f"{minx - pad},{miny - pad},{maxx + pad},{maxy + pad}", "geometryType": "esriGeometryEnvelope", "inSR": "2193", "outSR": "2193", "spatialRel": "esriSpatialRelIntersects", "outFields": "*"}
    req = urllib.request.Request(OFP_URL + "/query?" + urllib.parse.urlencode(q), headers=UA); ofp_raw = json.load(urllib.request.urlopen(req, timeout=120)); (out / "overland_flow_paths.geojson").write_text(json.dumps(ofp_raw))
    meta = json.load(urllib.request.urlopen(urllib.request.Request(OFP_URL + "?f=json", headers=UA), timeout=60))
    res["sources"]["overland_flow_paths"] = {"name": "Auckland Council Healthy Waters, Overland Flow Paths (polyline centrelines)", "service": OFP_URL, "retrieved": "live query for this report", "method": "re-mapped 2019 by WSP from 2016-17 LiDAR (1 m ground DEM), GIS-derived, not hydraulic modelling; field CatchmentAreaGroup is published without its class limits in the metadata retrieved", "vertical datum": "NZVD1946", "licence": meta.get("copyrightText") or "Auckland Council open data (CC BY 4.0)"}
    ofp = [(f["properties"], shape(f["geometry"])) for f in ofp_raw["features"]]
    res["sources"]["flood_layers"] = {"flood_plains": "Auckland Council Flood_Plains (raw.ac_hz_flood_plains in this database; Auckland Council open data)", "flood_prone": "Auckland Council Flood_Prone_Areas (raw.ac_hz_flood_prone)", "flood_sensitive": "Auckland Council Flood_Sensitive_Areas (raw.ac_hz_flood_sensitive)"}
    # ---- per lot
    corridors = {w: {} for w in CLEARANCE_M}
    for pid in ids:
        s = sites[pid]; P = s["poly"]; lot = {"parcel_id": pid, "address": s["address"], "zone": s["zone_name"], "area_m2": round(P.area, 1), "title": s.get("title_no"), "appellation": s.get("appellation")}
        with conn() as c:
            c.execute("set statement_timeout='120s'")
            row = c.execute("select title_no, appellation, pc120_proposed_zone from core.sites where parcel_id=%s", (pid,)).fetchone(); lot.update(title=row["title_no"], appellation=row["appellation"], pc120_proposed_zone=row["pc120_proposed_zone"])
            fl = {}
            for t, cols in (("ac_hz_flood_plains", "hazard, year_produced, model_type, rainfall_event, climate_change_adjusted, development_scenario, document_name, company, rainfallstandard"),
                            ("ac_hz_flood_prone", "fpa_id, catchmentarea, depth100y, maxdepth, minimumlevel_nzvd2016, level100y_nzvd2016, spilllevel_nzvd2016, depth100y_text, level100y_text_nzvd2016"),
                            ("ac_hz_flood_sensitive", "hazard, model_type, document_name, company, year_produced")):
                rows = c.execute(f"select {cols}, ST_Area(ST_Intersection(f.geom, s.geom)) inter, ST_AsText(ST_Intersection(f.geom, s.geom)) w from raw.{t} f join core.sites s on s.parcel_id=%s and f.geom && s.geom and ST_Intersects(f.geom, s.geom)", (pid,)).fetchall()
                fl[t] = [{**{k: (float(v) if hasattr(v, "as_integer_ratio") and not isinstance(v, int) else v) for k, v in r.items() if k not in ("w", "inter")}, "covers_m2": round(float(r["inter"]), 1), "covers_pct": round(100 * float(r["inter"]) / P.area, 1), "_geom": shp_wkt.loads(r["w"])} for r in rows]
        lot["flood_layers"] = {t: [{k: v for k, v in e.items() if k != "_geom"} for e in es] for t, es in fl.items()}
        # flow paths in the lot
        inside = [(p, g.intersection(P)) for p, g in ofp if g.intersects(P)]; inside = [(p, g) for p, g in inside if not g.is_empty and g.length > 0.05]
        lot["overland_flow_paths"] = [{"objectid": p["OBJECTID"], "catchment_area_group": p["CatchmentAreaGroup"], "length_in_lot_m": round(g.length, 1)} for p, g in inside]
        lot["overland_flow_path_total_m"] = round(sum(g.length for _, g in inside), 1)
        dist = sorted((round(g.distance(P), 1), p["OBJECTID"], p["CatchmentAreaGroup"], round(g.length)) for p, g in ofp)[:2]
        lot["nearest_flow_paths"] = [{"distance_m": a, "objectid": b, "catchment_area_group": c, "full_length_m": l} for a, b, c, l in dist]
        # ground, slope, contours inside the lot
        from shapely import contains_xy
        m = contains_xy(P, X, Y) & (Z != nod); z = Z[m]; sl = S[m]
        lot["ground"] = {"pixels": int(m.sum()), "elevation_min_m": round(float(z.min()), 2), "elevation_max_m": round(float(z.max()), 2), "elevation_mean_m": round(float(z.mean()), 2), "slope_mean_pct": round(float(sl.mean()), 1), "slope_p95_pct": round(float(np.percentile(sl, 95)), 1), "slope_max_pct": round(float(sl.max()), 1)}
        cl = [(e, g.intersection(P)) for e, g in contours if g.intersects(P)]; cl = [(e, g) for e, g in cl if not g.is_empty]
        lot["contours"] = {"interval_m": 0.1, "levels_crossing_lot": sorted({round(e, 1) for e, _ in cl}), "total_length_m": round(sum(g.length for _, g in cl), 1)}
        # depth if water stood at the flood prone area's published level (upper bound, the layer says a specific calculation is required)
        fp = fl["ac_hz_flood_prone"]
        if fp and fp[0].get("level100y_nzvd2016") is not None:
            lvl = float(fp[0]["level100y_nzvd2016"]); d = lvl - z
            lot["depth_if_filled_to_published_level"] = {"level_nzvd2016_m": lvl, "note": fp[0].get("depth100y_text") or "", "max_depth_m": round(float(d.max()), 2), "min_depth_m": round(float(d.min()), 2), "area_deeper_than_0.2m_pct": round(100 * float((d > .2).mean()), 1), "area_deeper_than_0.3m_pct": round(100 * float((d > .3).mean()), 1)}
        # clearance
        for w in CLEARANCE_M:
            near = [g for _, g in ofp if g.distance(P) <= w + 0.01]          # a path just outside the title still has its corridor reach into it
            band = unary_union([g.buffer(w, cap_style="flat") for g in near]) if near else Polygon(); corridors[w][pid] = band
            use = P.difference(band) if not band.is_empty else P; parts = [use] if use.geom_type == "Polygon" else list(use.geoms)
            lot.setdefault("usable_after_clearance", {})[f"{w:g}m_each_side"] = {"corridor_m2": round(P.intersection(band).area, 1), "usable_m2": round(use.area, 1), "usable_pct": round(100 * use.area / P.area, 1), "pieces": len(parts), "largest_piece_m2": round(max(p.area for p in parts), 1)}
        res["lots"][pid] = lot
    # ---- relocatable capacity
    def run(poly, zone, front, shape_wd, excl):
        unit = {"width_m": shape_wd[0], "depth_m": shape_wd[1], **UNIT_EXTRA}
        b = devlayout.best(poly, zone, unit, ACCESS_WIDTH_M, front, devrules.zone_rules(zone), None, excl, ("end", "side"))
        top = b["compliant"][0] if b["compliant"] else None
        bind = devlayout.binding_constraint(b)
        return {"units": top["unit_count"] if top else 0, "binding": bind["binding"], "explanation": bind["explanation"], "checks": [{k: c[k] for k in ("id", "status", "rule", "measured", "required", "unit")} for c in (top["checks"] if top else [])], "top": top, "envelope_area_m2": round(b["envelope"].area, 1)}
    cap = {}
    for pid in ids:
        s = sites[pid]; cap[pid] = {}
        for shp in SHAPES:
            for label, excl in (("no_flow_path_clearance", None), (f"clear_{BASE_CLEARANCE_M:g}m_each_side", corridors[BASE_CLEARANCE_M][pid] if not corridors[BASE_CLEARANCE_M][pid].is_empty else None)):
                r_ = run(s["poly"], s["zone_name"], s["front_point"], shp, excl); cap[pid][f"{shp[0]:g}x{shp[1]:g}|{label}"] = {k: v for k, v in r_.items() if k != "top"}; cap[pid][f"{shp[0]:g}x{shp[1]:g}|{label}|_top"] = r_["top"]
    zones = {}
    for pid in ids: zones.setdefault(sites[pid]["zone_name"], []).append(pid)
    comb = {}
    for zname, pids in zones.items():
        if len(pids) < 2: continue
        U = unary_union([sites[p]["poly"] for p in pids]).simplify(0.02)
        if U.geom_type != "Polygon": comb[zname] = {"note": "lots do not form one piece"}; continue
        fpnt = sites[pids[0]]["front_point"]; comb[zname] = {"lots": pids, "area_m2": round(U.area, 1)}
        for shp in SHAPES:
            for label, w in (("no_flow_path_clearance", None), (f"clear_{BASE_CLEARANCE_M:g}m_each_side", BASE_CLEARANCE_M)):
                excl = unary_union([corridors[w][p] for p in pids]) if w else None
                r_ = run(U, zname, fpnt, shp, excl); comb[zname][f"{shp[0]:g}x{shp[1]:g}|{label}"] = {k: v for k, v in r_.items() if k != "top"}; comb[zname][f"{shp[0]:g}x{shp[1]:g}|{label}|_top"] = r_["top"]
    # activity status rows and flood rules cited
    res["activity"] = {z: devrules.activity_rows(z, ("%dwelling%", "%relocat%")) for z in zones}
    res["capacity"] = {str(p): {k: v for k, v in d.items() if not k.endswith("_top")} for p, d in cap.items()}; res["combined"] = {z: {k: v for k, v in d.items() if not k.endswith("_top")} for z, d in comb.items()}
    res["zone_rules_used"] = {z: {k: {"value": r["v"], "unit": r["unit"], "rule": r["section_ref"]} for k, r in devrules.zone_rules(z).items() if k in ("yard_front_min", "yard_side_min", "yard_rear_min", "building_coverage_max_pct", "impervious_max_pct", "landscaped_min_pct", "building_height_max", "hirb_angle", "hirb_start_height", "ols_ground_floor_min_area", "ols_ground_floor_min_dimension", "dwelling_min_net_floor_area_1br_plus")} for z in zones}
    res["assumptions"] = [f"Relocatable footprints tried (width x depth, each 60 m2): {', '.join(f'{a:g} x {b:g} m' for a, b in SHAPES)}; single storey, ridge {UNIT_EXTRA['height_m']} m, walls {UNIT_EXTRA['wall_height_m']} m, 2 bedrooms.",
                          f"Driveway {ACCESS_WIDTH_M} m wide where more than one unit shares access; 2 parking spaces per unit (default assumption in config/transport_rules.yaml).",
                          f"Flow-path corridor: the Council layer gives centrelines only. Tested {', '.join(f'{w:g}' for w in CLEARANCE_M)} m each side; {BASE_CLEARANCE_M:g} m each side is the base case. The units and their outdoor living space are kept entirely outside the corridor.",
                          "The flood plain and flood prone layers cover every lot completely, so no ground is 'outside the flood plain'; flood depth at each lot is not given by the layers (the flood prone layer says a specific calculation is required).",
                          "Floor levels, flood depth, geotechnical, services and Auckland Transport crossing approval are not modelled: the unit counts are a planning-geometry result only."]
    # ---- map
    draw_map(out / "map.png", ids, sites, ofp, contours, corridors, cap, fl_polys=None, h=h, Z=Z, nod=nod)
    (out / "hazard_report.json").write_text(json.dumps(res, indent=1, default=str)); return res

def draw_map(path, ids, sites, ofp, contours, corridors, cap, fl_polys, h, Z, nod):
    from PIL import Image, ImageDraw, ImageFont
    U = unary_union([s["poly"] for s in sites.values()]); minx, miny, maxx, maxy = U.bounds; pad = 14; sc = 11
    minx -= pad; miny -= pad; maxx += pad; maxy += pad; W, H = int((maxx - minx) * sc), int((maxy - miny) * sc)
    # shaded relief from the DEM, lightly
    n, m = int(h["nrows"]), int(h["ncols"]); cs = h["cellsize"]; img = Image.new("RGB", (W, H), (245, 247, 250)); px = img.load()
    z0 = np.nanmin(np.where(Z != nod, Z, np.nan)); z1 = np.nanmax(np.where(Z != nod, Z, np.nan))
    for yy in range(H):
        for xx in range(W):
            x = minx + xx / sc; y = maxy - yy / sc; col = int((x - h["xllcorner"]) / cs); row = int(n - 1 - (y - h["yllcorner"]) / cs)
            if 0 <= row < n and 0 <= col < m and Z[row, col] != nod:
                t = (Z[row, col] - z0) / max(z1 - z0, .01); px[xx, yy] = (int(236 - 30 * t), int(240 - 20 * t), int(246 - 40 * t))
    d = ImageDraw.Draw(img, "RGBA")
    def T(x, y): return ((x - minx) * sc, (maxy - y) * sc)
    def poly(g, **kw):
        for p in ([g] if g.geom_type == "Polygon" else list(g.geoms)):
            if not p.is_empty: d.polygon([T(*c) for c in p.exterior.coords], **kw)
    for e, g in contours:
        if round(e * 10) % 5: continue          # every 0.5 m
        for ln in ([g] if g.geom_type == "LineString" else list(getattr(g, "geoms", []))):
            if ln.intersects(box(minx, miny, maxx, maxy)): d.line([T(*c) for c in ln.coords], fill=(120, 120, 120, 150), width=1)
    for pid in ids: poly(sites[pid]["poly"], fill=(255, 255, 255, 60), outline=(20, 40, 90, 255))
    for w, col in ((2.0, (60, 120, 255, 70)),):
        for pid in ids:
            if not corridors[w][pid].is_empty: poly(corridors[w][pid], fill=col)
    for _, g in ofp:
        for ln in ([g] if g.geom_type == "LineString" else list(g.geoms)):
            if ln.intersects(box(minx, miny, maxx, maxy)): d.line([T(*c) for c in ln.coords], fill=(0, 70, 220, 255), width=3)
    for pid in ids:
        top = cap[pid].get("4x15|clear_2m_each_side|_top")
        for u in (top["units"] if top else []): poly(u["footprint"], fill=(255, 150, 0, 200), outline=(150, 70, 0, 255))
        cx, cy = sites[pid]["poly"].centroid.coords[0]; d.text(T(cx - 4, cy + 12), sites[pid]["address"].split(",")[0], fill=(0, 0, 0, 255))
    d.text((8, 8), "blue line = Council overland flow path centreline; pale blue = 2 m each side; orange = 4 x 15 m relocatables kept clear; grey = 0.5 m contours (LiDAR 2024)", fill=(0, 0, 0, 255))
    img.save(path)

if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2:]])
