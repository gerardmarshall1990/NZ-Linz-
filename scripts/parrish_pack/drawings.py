"""Generated screening drawings (PNG) for the Parrish Road pack. Plain-language, all marked DRAFT. Uses the app's parcels, Council flow paths, LiDAR DEM and the indicative layouts."""
import json, math, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape, Point, LineString
from shapely import wkt
from common import *
import ground, scenarios as sc
OUTD = OUT / "drawings"; OUTD.mkdir(exist_ok=True)
def F(sz, bold=False):
    for p in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()
W, H = 1800, 1250
SHADE_KEY = True
class View:
    def __init__(s, bounds, box):
        s.minx, s.miny, s.maxx, s.maxy = bounds; s.x0, s.y0, s.x1, s.y1 = box
        s.k = min((s.x1 - s.x0) / (s.maxx - s.minx), (s.y1 - s.y0) / (s.maxy - s.miny))
    def p(s, x, y): return (s.x0 + (x - s.minx) * s.k, s.y1 - (y - s.miny) * s.k)
def ramp(z, lo, hi):
    t = max(0, min(1, (z - lo) / (hi - lo))); return (int(255 * t * .7 + 60), int(180 + 60 * t), int(255 - 150 * t))
def base(title, sub, bounds, shade=True, flow=True):
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im); v = View(bounds, (60, 130, W - 420, H - 60))
    X, Y, Z = ground.grid()
    if shade:
        lo, hi = 32.0, 34.4
        for x, y, z in zip(X.ravel(), Y.ravel(), Z.ravel()):
            if np.isnan(z) or not (bounds[0] - 1 <= x <= bounds[2] + 1 and bounds[1] - 1 <= y <= bounds[3] + 1): continue
            a, b = v.p(x - .5, y + .5), v.p(x + .5, y - .5); d.rectangle([a, b], fill=ramp(z, lo, hi))
    d.text((60, 30), title, font=F(34, True), fill="black"); d.text((60, 80), sub, font=F(16), fill=(60, 60, 60))
    d.rectangle([W - 420, 0, W, 130], fill="white"); d.rectangle([5, 5, W - 5, H - 5], outline="black", width=2)
    return im, d, v
def lots():
    sc.setup(); return {NUM[p]: sc._sites[p]["poly"] for p in IDS}
def ofp(b=None):
    from shapely.geometry import box
    g = jload(DATA / "overland_flow_paths.geojson"); out = [shape(f["geometry"]) for f in g["features"]]
    if b: bx = box(*b); out = [o.intersection(bx) for o in out]; out = [x for o in out for x in ([o] if o.geom_type == "LineString" else list(getattr(o, "geoms", []))) if x.geom_type == "LineString" and not x.is_empty]
    return out
def poly(d, v, g, **kw):
    pts = [v.p(x, y) for x, y in g.exterior.coords]; d.polygon(pts, **kw)
def furniture(d, v, bounds, legend, note):
    # north arrow, scale bar, legend, stamp
    x = W - 380; d.text((x, 150), "LEGEND", font=F(22, True), fill="black"); y = 190
    for kind, col, txt in legend:
        if kind == "box": d.rectangle([x, y, x + 36, y + 22], fill=col[0], outline=col[1], width=3)
        elif kind == "line": d.line([x, y + 11, x + 36, y + 11], fill=col, width=5)
        elif kind == "dot": d.ellipse([x + 12, y + 3, x + 24, y + 15], fill=col)
        d.text((x + 50, y), txt, font=F(17), fill="black"); y += 36
    if SHADE_KEY:
        d.text((x, y + 20), "Elevation (LiDAR 1 m DEM)", font=F(17, True), fill="black")
        for i in range(10):
            d.rectangle([x + i * 34, y + 50, x + (i + 1) * 34, y + 70], fill=ramp(32.0 + i * .26, 32.0, 34.4))
        d.text((x, y + 74), "32.0 m", font=F(15), fill="black"); d.text((x + 270, y + 74), "34.4 m RL", font=F(15), fill="black")
    # scale bar
    L = 10; a = v.p(bounds[0] + 2, bounds[1] + 2); b = v.p(bounds[0] + 2 + L, bounds[1] + 2); d.rectangle([a[0], a[1] - 8, b[0], a[1]], fill="black"); d.text((a[0], a[1] + 4), "10 m", font=F(16), fill="black")
    # north
    nx, ny = W - 120, H - 420; d.polygon([(nx, ny - 70), (nx - 18, ny), (nx + 18, ny)], fill="black"); d.text((nx - 8, ny + 6), "N", font=F(26, True), fill="black")
    # note + stamp
    yy = H - 150
    for ln in note: d.text((W - 400, yy - 130 + 0), "", font=F(14)); 
    d.text((W - 400, H - 330), "\n".join(note), font=F(15), fill=(40, 40, 40))
    d.rectangle([W - 400, H - 90, W - 20, H - 25], outline=(190, 0, 0), width=4); d.text((W - 385, H - 80), "DRAFT - NOT FOR CONSTRUCTION\nNot surveyed. Not engineer-checked.", font=F(15, True), fill=(190, 0, 0))
def site_plan(L, runs, E):
    allp = [p for p in L.values()]; b = (min(p.bounds[0] for p in allp) - 12, min(p.bounds[1] for p in allp) - 12, max(p.bounds[2] for p in allp) + 12, max(p.bounds[3] for p in allp) + 12)
    im, d, v = base("Drawing 1: Site plan (indicative, 8 x 60 m2 relocatables)", "2, 4, 6 and 8 Parrish Road, Sandringham. EPSG:2193 (NZTM). Layout is a screening result from this app, not a design.", b)
    for n, p in L.items():
        poly(d, v, p, outline=(0, 0, 0), width=4)
        c = p.centroid; cx, cy = v.p(c.x, c.y + 3); d.text((cx - 30, cy), f"Lot {n}", font=F(22, True), fill=(0, 0, 0))
    for g in ofp(b):
        for L2 in [g]:
            if True: d.line([v.p(x, y) for x, y in L2.coords], fill=(0, 60, 220), width=6)
    for key, col in (("2+4|THAB|flood", (255, 235, 120)), ("6+8|MHU|flood", (255, 235, 120))):
        r = runs[key]
        if r.get("access_geom"):
            for g in ([r["access_geom"]] if isinstance(r["access_geom"], dict) else r["access_geom"]): poly(d, v, shape(g), fill=(200, 200, 200), outline=(90, 90, 90), width=2)
        for g in r["units_geom"]: poly(d, v, shape(g), fill=(250, 220, 190), outline=(120, 60, 0), width=3)
        for g in r.get("ols_geom", []): poly(d, v, shape(g), outline=(30, 120, 30), width=2)
    for u in E["units"]:
        c = wkt.loads(u["geom"]).centroid; x, y = v.p(c.x, c.y); d.text((x - 24, y - 10), u["id"], font=F(16, True), fill="black")
    furniture(d, v, b, [("box", ((250, 220, 190), (120, 60, 0)), "Relocatable 4 x 15 m (60 m2)"), ("box", ((200, 200, 200), (90, 90, 90)), "Shared driveway 3.5 m"), ("line", (0, 60, 220), "Council overland flow path"), ("box", ((255, 255, 255), (30, 120, 30)), "Outdoor living 20 m2"), ("box", ((255, 255, 255), (0, 0, 0)), "Title boundary (LINZ)")],
              ["Whole site is inside the Council 100-year", "flood plain (S2) and a flood prone area (S3).", "FFL per unit: see Table 6 / Appendix A.", "Datum: NZVD2016 (LiDAR) - Council flood", "layers use NZVD2016; flow path layer uses", "NZVD1946. UNVERIFIED conversion.", "Zone-standard yards and coverage: see", "Zoning_Feasibility.xlsx (S7, S14)."])
    im.save(OUTD / "01_site_plan.png"); return im
def flow_plan(L, runs, E, pk):
    allp = list(L.values()); b = (min(p.bounds[0] for p in allp) - 18, min(p.bounds[1] for p in allp) - 18, max(p.bounds[2] for p in allp) + 18, max(p.bounds[3] for p in allp) + 18)
    im, d, v = base("Drawing 2: Flood and overland flow path plan", "Council layers over LiDAR ground. 2 m offset is an ASSUMED planning figure. Sources S2, S3, S5, S6.", b)
    for n, p in L.items(): poly(d, v, p, outline="black", width=4); c = p.centroid; x, y = v.p(c.x, c.y); d.text((x - 24, y - 10), f"Lot {n}", font=F(24, True), fill="black")
    from shapely.geometry import box
    for g in ofp(b):
        d.line([v.p(x, y) for x, y in g.coords], fill=(0, 60, 220), width=6)
        bb = g.buffer(2).intersection(box(*b))
        for part in ([bb] if bb.geom_type == "Polygon" else list(bb.geoms)): d.line([v.p(x, y) for x, y in part.exterior.coords], fill=(0, 140, 255), width=2)
    # 0.5 m contours inside window
    cg = jload(DATA / "contours_0.1m.geojson")
    for f in cg["features"]:
        z = f["properties"].get("ELEV", f["properties"].get("elev", f["properties"].get("ELEV_M")))
        if z is None: z = list(f["properties"].values())[0]
        if abs((z * 2) - round(z * 2)) > 1e-6: continue
        g = shape(f["geometry"])
        for part in ([g] if g.geom_type == "LineString" else list(g.geoms)):
            if part.distance(allp[0].union(allp[1]).union(allp[2]).union(allp[3])) < 20:
                d.line([v.p(x, y) for x, y in part.coords], fill=(90, 50, 20), width=1)
                m = part.interpolate(0.5, normalized=True); x, y = v.p(m.x, m.y); d.text((x, y), f"{z:.1f}", font=F(12), fill=(90, 50, 20))
    furniture(d, v, b, [("line", (0, 60, 220), "Council flow path (centreline)"), ("line", (0, 140, 255), "2 m planning offset (ASSUMED)"), ("line", (90, 50, 20), "LiDAR contour 0.5 m (m RL)"), ("box", ((255, 255, 255), (0, 0, 0)), "Title boundary")],
              ["Flood plain: 100% of each lot (S2).", "Flood prone area FPA 30836607: spill level", "37.03 m RL (S3), so 'specific calculation", "required'. Depths here are NOT modelled.", "Only a Council/engineer flood model gives", "depth and velocity (Confirmed Input 1, 3)."])
    im.save(OUTD / "02_flow_path_plan.png")
def pile_plan(E):
    us = E["units"]; xs = [wkt.loads(u["geom"]).bounds for u in us]; b = (min(a[0] for a in xs) - 8, min(a[1] for a in xs) - 8, max(a[2] for a in xs) + 8, max(a[3] for a in xs) + 8)
    im, d, v = base("Drawing 3: Indicative pile layout (10 piles per unit)", "Pile grid ASSUMED (5 rows x 2). Engineer sets the real grid. Sources S6, S14.", b, shade=False)
    for u in us:
        poly(d, v, wkt.loads(u["geom"]), outline=(120, 60, 0), width=3, fill=(250, 235, 215))
        for p in u["piles"]:
            x, y = v.p(p["x"], p["y"]); d.rectangle([x - 5, y - 5, x + 5, y + 5], fill="black")
        c = wkt.loads(u["geom"]).centroid; x, y = v.p(c.x, c.y); d.text((x - 30, y - 12), u["id"], font=F(18, True), fill=(120, 60, 0))
    furniture(d, v, b, [("box", ((250, 235, 215), (120, 60, 0)), "Unit footprint 4 x 15 m"), ("box", ((0, 0, 0), (0, 0, 0)), "Pile (300 mm pier or 114 mm CHS)")],
              ["Pile ground RL (LiDAR) is listed in", "Appendix A, Table A1.", "Stepped pile heights follow the ground", "under each pile (ASSUMED floor frame", "0.30 m deep)."])
    im.save(OUTD / "03_pile_layout.png")
def section(E):
    u = next(x for x in E["units"] if x["id"] == "L2-U1"); lv = u["levels"]["0.9"]; im = Image.new("RGB", (W, 900), "white"); d = ImageDraw.Draw(im)
    d.text((60, 30), "Drawing 4: Indicative long section through L2-U1 (design flood depth 0.9 m: ASSUMED)", font=F(30, True), fill="black")
    d.text((60, 75), "Ground profile from LiDAR (S6) along the unit centreline. Flood level = lot minimum ground + 0.9 m (ASSUMED depth); FFL = flood level + 0.5 m. Vertical exaggeration x4.", font=F(18), fill=(60, 60, 60))
    prof = []; sx, sy = u["street_end"]; ax, ay = u["axis"]
    for s in np.arange(0, 15.01, 0.5): prof.append((s, ground.sample(sx + ax * s, sy + ay * s)))
    zlo, zhi = 31.8, 34.6; X0, X1, Y0, Y1 = 120, 1500, 150, 800
    px = lambda s: X0 + s / 15 * (X1 - X0); py = lambda z: Y1 - (z - zlo) / (zhi - zlo) * (Y1 - Y0)
    fl = lv["flood_level_RL"]; ffl = lv["ffl_RL"]; cu = lv["chassis_underside_RL"]
    d.rectangle([px(0), py(fl), px(15), Y1], fill=(215, 235, 255)); d.line([px(0), py(fl), px(15), py(fl)], fill=(0, 90, 220), width=4); d.text((px(15) + 10, py(fl) - 10), f"Flood level {fl:.2f} m RL (ASSUMED)", font=F(16), fill=(0, 90, 220))
    d.polygon([(px(0), Y1)] + [(px(s), py(z)) for s, z in prof] + [(px(15), Y1)], fill=(180, 150, 110), outline="black")
    d.rectangle([px(0), py(ffl), px(15), py(cu)], fill=(250, 220, 190), outline=(120, 60, 0), width=3)
    d.line([px(0), py(ffl + .0), px(15), py(ffl)], fill=(120, 60, 0)); d.text((px(15) + 10, py(ffl) - 10), f"FFL {ffl:.2f} m RL", font=F(16), fill=(120, 60, 0))
    d.text((px(15) + 10, py(cu) + 6), f"Chassis underside {cu:.2f}", font=F(16), fill=(120, 60, 0))
    for p in u["piles"][::2]:
        s = (p["x"] - sx) * ax + (p["y"] - sy) * ay; d.rectangle([px(s) - 5, py(cu), px(s) + 5, py(p["ground"]) + 10], fill="black")
    d.text((X0, Y1 + 20), "Street end (0 m)", font=F(16), fill="black"); d.text((px(15) - 120, Y1 + 20), "Far end (15 m)", font=F(16), fill="black")
    d.text((X0, Y1 + 50), f"Pile exposed height {lv['pile_exposed_min_m']:.2f} to {lv['pile_exposed_max_m']:.2f} m (CALCULATED from LiDAR + ASSUMED inputs). Piles embedded below ground to depth set by geotech (not shown).", font=F(16), fill="black")
    d.rectangle([W - 460, 820, W - 20, 885], outline=(190, 0, 0), width=4); d.text((W - 445, 830), "DRAFT - NOT FOR CONSTRUCTION\nNot surveyed. Not engineer-checked.", font=F(15, True), fill=(190, 0, 0))
    im.save(OUTD / "04_section.png")
def main():
    L = lots(); runs = jload(DATA / "scenario_runs.json"); E = jload(DATA / "eng_results.json")
    site_plan(L, runs, E); flow_plan(L, runs, E, None); pile_plan(E); section(E); print("ok", [p.name for p in OUTD.iterdir()])
if __name__ == "__main__": main()
