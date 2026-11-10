"""Relocatable catalogue optimiser. Reads config/forde_catalogue.csv (name,url,length_m,width_m,floor_area_m2,bedrooms,bathrooms,price_nzd,status,source_note), one row per available home (Forde Brothers stock: fordebrothers.co.nz). For each home it packs the four lots as one MHU-standards site with the app's layout engine (two variants: T9 = 1 space/unit, standard outdoor living; T10 = no parking, 16 m2 ground + 5 m2 deck) and ranks by (a) total bedrooms, (b) total floor area, (c) total price. Writes /out/Forde_Options.csv and footprint drawings /out/drawings/07_*.png. Nothing is invented: an empty catalogue produces nothing."""
import sys, csv, math
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import scenarios as sc
from scenarios import *
import drawings as dr
from drawings import *
CAT = ROOT / "config" / "forde_catalogue.csv"
def pack(row, spu, ola):
    sc.setup(); pids = [PID[n] for n in (2, 4, 6, 8)]
    U = unary_union([sc._sites[p]["poly"] for p in pids]).simplify(0.02); front = sc._sites[pids[0]]["front_point"]; R = dict(devrules.zone_rules(ZN["MHU"]))
    if ola is not None: R["ols_ground_floor_min_area"] = {**R["ols_ground_floor_min_area"], "v": ola}
    excl = unary_union([sc._corr[p] for p in pids if sc._corr[p] is not None])
    unit = {"width_m": float(row["width_m"]), "depth_m": float(row["length_m"]), "height_m": 3.8, "wall_height_m": 2.7, "gfa_m2": float(row["floor_area_m2"]), "bedrooms": int(row["bedrooms"])}
    b = devlayout.best(U, ZN["MHU"], unit, 3.5, front, R, spu, excl, ("end", "side")); top = b["compliant"][0] if b["compliant"] else None
    return top
def draw(name, top, title):
    L = lots(); allp = list(L.values()); b = (min(p.bounds[0] for p in allp) - 12, min(p.bounds[1] for p in allp) - 12, max(p.bounds[2] for p in allp) + 12, max(p.bounds[3] for p in allp) + 12)
    im, d, v = base(title, "Footprints from the app's layout engine; MHU standards; 2 m flow-path offset. Screening layout.", b)
    for n, p in L.items(): poly(d, v, p, outline="black", width=4)
    for g in ofp(b): d.line([v.p(x, y) for x, y in g.coords], fill=(0, 60, 220), width=5)
    if top["access"] is not None: poly(d, v, top["access"], fill=(200, 200, 200), outline=(90, 90, 90), width=2)
    for i, u in enumerate(top["units"], 1):
        poly(d, v, u["footprint"], fill=(250, 220, 190), outline=(120, 60, 0), width=3); c = u["footprint"].centroid; x, y = v.p(c.x, c.y); d.text((x - 8, y - 8), str(i), font=F(18, True), fill="black")
        if u.get("ols") is not None: poly(d, v, u["ols"], outline=(30, 120, 30), width=2)
    furniture(d, v, b, [("box", ((250, 220, 190), (120, 60, 0)), "Home footprint"), ("box", ((200, 200, 200), (90, 90, 90)), "Driveway 3.5 m"), ("line", (0, 60, 220), "Council overland flow path"), ("box", ((255, 255, 255), (30, 120, 30)), "Outdoor living"), ("box", ((255, 255, 255), (0, 0, 0)), "Title boundary")], ["DRAFT screening layout."])
    im.save(OUT / "drawings" / name)
def main():
    if not CAT.exists(): print("no catalogue at", CAT); return
    rows = [r for r in csv.DictReader(open(CAT)) if r.get("name")]
    if not rows: print("catalogue is empty: nothing to optimise"); return
    res = []
    for r in rows:
        for var, spu, ola in (("T9", 1, None), ("T10", 0, 16)):
            top = pack(r, spu, ola); n = top["unit_count"] if top else 0
            beds = n * int(r["bedrooms"]); area = n * float(r["floor_area_m2"]); cost = n * float(r["price_nzd"] or 0)
            res.append({**r, "variant": var, "units": n, "total_bedrooms": beds, "total_floor_area_m2": round(area, 1), "total_price_nzd": cost, "top": top})
    res.sort(key=lambda x: (-x["total_bedrooms"], -x["total_floor_area_m2"]))
    with open(OUT / "Forde_Options.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["rank_by_bedrooms", "name", "url", "variant", "units_fit", "bedrooms_each", "total_bedrooms", "total_floor_area_m2", "total_price_nzd", "status", "source_note"])
        for i, x in enumerate(res, 1): w.writerow([i, x["name"], x["url"], x["variant"], x["units"], x["bedrooms"], x["total_bedrooms"], x["total_floor_area_m2"], x["total_price_nzd"], x["status"], x["source_note"]])
    for i, x in enumerate(res[:3], 1):
        if x["top"]: draw(f"07_option{i}.png", x["top"], f"Option {i}: {x['units']} x {x['name']} ({x['variant']})")
    print("options", len(res))
if __name__ == "__main__": main()
