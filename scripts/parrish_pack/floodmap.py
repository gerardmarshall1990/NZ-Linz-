"""Drawing 5/6: Council flood plain, flood prone area and flood sensitive layers over the four lots (S2, S3, S4)."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
import drawings as dr
from drawings import *
from shapely import wkt as W_
from shapely.geometry import box
from backend.app.db import conn
def layer(t, b):
    with conn() as c:
        c.execute("set statement_timeout='120s'")
        r = c.execute(f"select ST_AsText(ST_Intersection(geom, ST_MakeEnvelope(%s,%s,%s,%s,2193))) w from raw.{t} where geom && ST_MakeEnvelope(%s,%s,%s,%s,2193)", (*b, *b)).fetchall()
    return [W_.loads(x["w"]) for x in r if x["w"]]
def polys(g):
    if g.is_empty: return []
    return [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon" and not p.is_empty]
def draw(L, b, name, title, sub, sets, note):
    im, d, v = base(title, sub, b, shade=False)
    for lay, fill, outl in sets:
        for g in lay:
            for p in polys(g):
                d.polygon([v.p(x, y) for x, y in p.exterior.coords], fill=fill, outline=outl)
    X, Y, Z = ground.grid()
    from shapely.geometry import box as bx
    for g in ofp(b): d.line([v.p(x, y) for x, y in g.coords], fill=(0, 60, 220), width=4)
    for n, p in L.items(): poly(d, v, p, outline="black", width=4); c = p.centroid; x, y = v.p(c.x, c.y + 3); d.text((x - 28, y), f"Lot {n}", font=F(22, True), fill="black")
    leg = [("box", (s[1], s[2]), s[3]) for s in sets] if False else []
    furniture(d, v, b, [("box", ((s[1][0], s[1][1], s[1][2]), s[2]), s[3]) for s in [(0, *x) for x in LEG[name]]] + [("line", (0, 60, 220), "Council overland flow path"), ("box", ((255, 255, 255), (0, 0, 0)), "Title boundary (LINZ)")], note)
    im.save(OUTD / name)
LEG = {}
def main():
    dr.SHADE_KEY = False; import drawings; drawings.SHADE_KEY = False
    L = lots(); allp = list(L.values()); b = (min(p.bounds[0] for p in allp) - 60, min(p.bounds[1] for p in allp) - 60, max(p.bounds[2] for p in allp) + 60, max(p.bounds[3] for p in allp) + 60)
    fp = layer("ac_hz_flood_plains", b); fa = layer("ac_hz_flood_prone", b); fs = layer("ac_hz_flood_sensitive", b)
    print(len(fp), len(fa), len(fs))
    FP = (110, 170, 255, 150); FA = (255, 190, 90, 150); FS = (160, 220, 120, 150)
    LEG["05_flood_plain.png"] = [((FP[0], FP[1], FP[2]), (0, 90, 200), "1% AEP Flood Plain (S2)")]
    draw(L, b, "05_flood_plain.png", "Drawing 5: Council 1% AEP flood plain over the four lots", "Auckland Council Flood Plains layer (Meola model, URS 2017, 100-year, climate-change adjusted, MPD), live data read 10 Nov 2026. Extent only.", [(fp, FP[:3], (0, 90, 200))],
         ["All four lots are 100% inside the", "flood plain polygon (S2).", "The layer gives extent only: no depth,", "level or velocity is published.", "Engineer's model required (Inputs 1, 3).", "Shows where the layer is: not a flood", "depth map."])
    LEG["06_flood_prone.png"] = [((FA[0], FA[1], FA[2]), (200, 120, 0), "Flood Prone Area (S3)")]
    draw(L, b, "06_flood_prone.png", "Drawing 6: Flood prone area FPA 30836607", "Council Flood Prone Areas layer, read 10 Nov 2026. No Flood Sensitive Area is mapped here. Extent only.", [(fa, FA[:3], (200, 120, 0)), (fs, FS[:3], (60, 140, 40))],
         ["Flood prone area 30836607: published 100-year", "spill level 37.03 m RL (NZVD2016), noted", "'Spills - specific calculation is required' (S3).", "No flood sensitive area on the lots (S4).", "Depth to the spill level would be 2.9 to 4.8 m", "on the lots (CALCULATED vs LiDAR): the", "engineer must confirm what the lots reach."])
if __name__ == "__main__": main()
