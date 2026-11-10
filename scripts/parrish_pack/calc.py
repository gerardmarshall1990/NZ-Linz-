#!/usr/bin/env python3
"""Step 2 calculations: parametric flood design lookups for the indicative 8-unit scheme (operative zoning, 2+4 and 6+8 amalgamated, 4 x 15 m units, flow-path clearance 2 m each side).
Every result is CALCULATED from DATA (LiDAR ground, Council layers) and ASSUMED inputs listed in ASSUME; nothing here is a design or a certified figure. Output: data/hazard/parrish/eng_results.json"""
import json, math
import numpy as np
from shapely.geometry import shape, Point, box, Polygon, LineString
from shapely.ops import unary_union
from shapely import affinity, contains_xy
from common import *
import ground, scenarios as sc
from backend.app import devscenarios
ASSUME = {
 "water_density_kg_m3": (RHO, "ASSUMED clear fresh water; sediment-laden flood water may be 1,100 to 1,200"),
 "g": (G, "CALCULATED constant"),
 "Cd_square_pile": (2.0, "ASSUMED, UNVERIFIED against ASCE 7 Chapter 5 (not read)"),
 "Cd_round_pile": (1.2, "ASSUMED, UNVERIFIED against ASCE 7 Chapter 5 (not read)"),
 "blockage_factor": (1.5, "ASSUMED allowance for bracing and trapped debris on pile projected area; the engineer sets the real figure"),
 "concrete_pier_mm": (300, "ASSUMED 300 x 300 mm"), "steel_pile_OD_mm": (114.3, "ASSUMED CHS outside diameter for the drag area"),
 "piles_per_unit": (10, "ASSUMED 5 rows x 2 lines, rows at 0.5, 4.0, 7.5, 11.0 and 14.5 m from the street end"),
 "floor_frame_depth_m": (FLOOR_DEPTH, "ASSUMED depth of chassis and floor frame below top of floor; manufacturer drawings needed"),
 "freeboard_m": (FREEBOARD, "owner's specification (1% AEP level + 500 mm); Council wording UNVERIFIED"),
 "unit_dead_load_kg_m2": (120, "ASSUMED; manufacturer weights needed"), "live_load_kPa": (1.5, "ASSUMED domestic floor; AS/NZS 1170.1 not read: UNVERIFIED"),
 "scour_depth_to_fixity_m": (0.5, "ASSUMED; geotechnical report decides"), "steel_fy_MPa": (350, "ASSUMED grade; UNVERIFIED"), "phi": (0.9, "ASSUMED; UNVERIFIED"),
 "stair_riser_m": (0.175, "ASSUMED; Building Code D1/AS1 not read: UNVERIFIED"), "stair_going_m": (0.28, "ASSUMED; D1/AS1 not read: UNVERIFIED"), "stair_top_landing_m": (1.2, "ASSUMED"),
 "ramp_gradient": ("1:12", "ASSUMED accessible gradient; D1/AS1 not read: UNVERIFIED"),
 "parking_space_m": ("2.5 x 5.0", "ASSUMED"), "spaces_per_unit": (2, "ASSUMED default (config/transport_rules.yaml)"),
}
CHS = [(60.3, 3.6), (76.1, 3.6), (88.9, 5.0), (114.3, 5.4), (139.7, 5.4), (168.3, 6.4)]      # candidate round hollow sections; availability UNVERIFIED
def Z_chs(D, t): d = D - 2 * t; return math.pi * (D ** 4 - d ** 4) / (32 * D) / 1e3         # mm^3 x 1e-3 -> cm^3? (D in mm) -> returns cm^3
def lot_frame(site):
    P = site["poly"]; fp = Point(site["front_point"]); pts = list(P.exterior.coords); edges = [LineString([a, b]) for a, b in zip(pts, pts[1:])]
    fe = min(edges, key=lambda e: e.distance(fp)); (ax, ay), (bx, by) = fe.coords[0], fe.coords[-1]
    if ax > bx: ax, ay, bx, by = bx, by, ax, ay
    L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L; vx, vy = -uy, ux
    if (P.centroid.x - ax) * vx + (P.centroid.y - ay) * vy < 0: vx, vy = -vx, -vy
    return ax, ay, ux, uy, vx, vy
def main():
    sc.setup(); sites = sc._sites; haz = jload(DATA / "hazard_report.json"); runs = jload(DATA / "scenario_runs.json")
    lotpoly = {NUM[p]: sites[p]["poly"] for p in IDS}; gmin = {NUM[p]: haz["lots"][str(p)]["ground"]["elevation_min_m"] for p in IDS}; frames = {NUM[p]: lot_frame(sites[p]) for p in IDS}
    units = []
    for key in ("2+4|THAB|flood", "6+8|MHU|flood"):
        r = runs[key]
        for g in r["units_geom"]: units.append(shape(g))
    rec = []
    for poly in units:
        lot = next((n for n, P in lotpoly.items() if P.contains(poly.centroid)), None) or min(lotpoly, key=lambda n: lotpoly[n].distance(poly.centroid))
        ax, ay, ux, uy, vx, vy = frames[lot]; mrr = poly.minimum_rotated_rectangle; c = list(mrr.exterior.coords)[:4]
        e = [(c[(i + 1) % 4][0] - c[i][0], c[(i + 1) % 4][1] - c[i][1]) for i in range(4)]; lens = [math.hypot(*x) for x in e]; i = int(np.argmax(lens[:2])); lx, ly = e[i][0] / lens[i], e[i][1] / lens[i]
        if lx * vx + ly * vy < 0: lx, ly = -lx, -ly                                  # long axis pointing from the street end to the far end
        cx, cy = poly.centroid.x, poly.centroid.y; sl = max(lens[:2]); sw = min(lens[:2]); tx, ty = -ly, lx
        s0x, s0y = cx - lx * sl / 2, cy - ly * sl / 2                                # street-end centre
        piles = [(s0x + lx * s + tx * o, s0y + ly * s + ty * o, k + 1) for k, s in enumerate((0.5, 4.0, 7.5, 11.0, 14.5)) for o in (-1.5, 1.5)]
        gx, gy, gz = ground.inside(poly)
        door = ground.sample(s0x + lx * 0.3, s0y + ly * 0.3)
        rec.append({"lot": lot, "centroid": [cx, cy], "length_m": round(sl, 2), "width_m": round(sw, 2), "axis": [lx, ly], "street_end": [s0x, s0y], "ground_mean": float(gz.mean()), "ground_min": float(gz.min()), "ground_max": float(gz.max()), "ground_door": door,
                    "piles": [{"id": f"P{k}{'ab'[0 if (j % 2 == 0) else 1]}", "x": x, "y": y, "row": k, "ground": ground.sample(x, y)} for j, (x, y, k) in enumerate(piles)], "poly": poly.wkt})
    rec.sort(key=lambda r: (int(r["lot"]), r["centroid"][0])); cnt = {}
    for r in rec: cnt[r["lot"]] = cnt.get(r["lot"], 0) + 1; r["id"] = f"L{r['lot']}-U{cnt[r['lot']]}"
    res = {"assumptions": {k: {"value": v, "basis": b} for k, (v, b) in ASSUME.items()}, "units": [], "lookup": {}, "uplift": [], "gravity": {}, "parking": {}, "storage": {}, "sizing": {}}
    A = ASSUME; rho, Cdp, Cdr, blk = RHO, 2.0, 1.2, 1.5; bsq, brd = 0.30, 0.1143; zs = 0.5; fy = 350.0; phi = 0.9
    for r in rec:
        L = {d: gmin[r["lot"]] + d for d in DEPTHS}; u = {"id": r["id"], "lot": r["lot"], "ground_mean_RL": round(r["ground_mean"], 2), "ground_min_RL": round(r["ground_min"], 2), "ground_max_RL": round(r["ground_max"], 2), "ground_door_RL": round(r["ground_door"], 2), "levels": {}, "piles": r["piles"], "geom": r["poly"], "street_end": r["street_end"], "axis": r["axis"]}
        for d in DEPTHS:
            lvl = L[d]; ffl = lvl + FREEBOARD; top = ffl - FLOOR_DEPTH; ex = [top - p["ground"] for p in r["piles"]]
            H = ffl - r["ground_door"]; nr = math.ceil(H / 0.175 - 1e-9); run_ = (nr - 1) * 0.28 + 1.2; ramp = 12 * H
            u["levels"][str(d)] = {"flood_level_RL": round(lvl, 2), "depth_at_unit_m": round(max(0, lvl - r["ground_mean"]), 2), "ffl_RL": round(ffl, 2), "chassis_underside_RL": round(top, 2), "pile_exposed_min_m": round(min(ex), 2), "pile_exposed_max_m": round(max(ex), 2),
                                   "ffl_above_mean_ground_m": round(ffl - r["ground_mean"], 2), "access_height_m": round(H, 2), "stair_risers": nr, "stair_run_m": round(run_, 1), "ramp_length_m": round(ramp, 1)}
            for v in VELS:
                hw = [max(0.0, lvl - p["ground"]) for p in r["piles"]]
                Fsq = [0.5 * rho * Cdp * bsq * h * v * v * blk / 1e3 for h in hw]; Frd = [0.5 * rho * Cdr * brd * h * v * v * blk / 1e3 for h in hw]
                Msq = max(f * (h / 2 + zs) for f, h in zip(Fsq, hw)); Mrd = max(f * (h / 2 + zs) for f, h in zip(Frd, hw))
                u.setdefault("loads", {})[f"{d}|{v}"] = {"max_pile_drag_square_kN": round(max(Fsq), 2), "max_pile_drag_round_kN": round(max(Frd), 2), "unit_total_drag_square_kN": round(sum(Fsq), 1), "unit_total_drag_round_kN": round(sum(Frd), 1),
                                                           "max_pile_moment_round_kNm": round(Mrd, 2), "max_pile_moment_square_kNm": round(Msq, 2), "dxv_m2s": round(max(hw) * v, 2), "max_wetted_height_m": round(max(hw), 2)}
        res["units"].append(u)
    # lookup (worst unit) by depth and velocity for pile sizing and bracing
    for d in DEPTHS:
        for v in VELS:
            w = max(res["units"], key=lambda uu: uu["loads"][f"{d}|{v}"]["max_pile_moment_round_kNm"]); L_ = w["loads"][f"{d}|{v}"]
            Mreq = L_["max_pile_moment_round_kNm"]; Zreq = Mreq * 1e3 / (phi * fy)                                        # cm^3 (kNm -> Nmm/MPa = mm^3 /1e3)
            pick = next(((D, t, Z_chs(D, t)) for D, t in CHS if Z_chs(D, t) >= Zreq), None)
            tot = max(uu["loads"][f"{d}|{v}"]["unit_total_drag_round_kN"] for uu in res["units"]); brace = tot / 2 / math.cos(math.radians(45)); Abr = brace * 1e3 / (phi * fy) / 100
            res["lookup"][f"{d}|{v}"] = {"worst_unit": w["id"], "max_pile_moment_kNm": Mreq, "Z_required_cm3": round(Zreq, 1), "chs_pick": None if pick is None else {"OD_mm": pick[0], "t_mm": pick[1], "Z_cm3": round(pick[2], 1)}, "unit_total_drag_kN_max": round(tot, 1), "brace_axial_kN": round(brace, 1), "brace_area_cm2": round(Abr, 2), "dxv_max": w["loads"][f"{d}|{v}"]["dxv_m2s"]}
    # uplift and tie-downs (independent of depth: water above the design level)
    Wd = 120 * 9.81 * UNIT_A / 1e3
    for e in (0.2, 0.5, 0.8, 1.1):
        x = max(0.0, e - (FREEBOARD - FLOOR_DEPTH)); B = RHO * G * UNIT_A * x / 1e3; U_ = max(0.0, B - 0.9 * Wd)
        res["uplift"].append({"water_above_design_level_m": e, "water_above_floor_underside_m": round(x, 2), "buoyancy_kN": round(B, 1), "dead_kN": round(Wd, 1), "net_uplift_kN": round(U_, 1), "per_pile_kN": round(U_ / 10, 1)})
    w_uls = 1.2 * (120 * 9.81 / 1e3) + 1.5 * 1.5; res["gravity"] = {"uls_kPa": round(w_uls, 2), "per_pile_kN": round(w_uls * UNIT_A / 10, 1), "basis": "1.2G + 1.5Q on 6 m2 tributary per pile; CALCULATED from ASSUMED G and Q; load combinations UNVERIFIED (AS/NZS 1170.0 not read)"}
    res["hydrostatic_per_m_solid_kN"] = {str(d): round(0.5 * RHO * G * d * d / 1e3, 2) for d in DEPTHS}
    # parking and accessway tests (E36.6.1.7 and E36.6.1.8) by lot and peak depth
    X, Y, Z = ground.grid(); lot_of = np.full(Z.shape, "", dtype=object)
    for n, P in lotpoly.items(): lot_of[contains_xy(P, X, Y)] = n
    unit_by_lot = {}
    for u in res["units"]: unit_by_lot.setdefault(u["lot"], []).append(shape_from(u["geom"]))
    access = {k: runs[k].get("access_geom") for k in ("2+4|THAB|flood", "6+8|MHU|flood")}; acc_poly = {k: (shape(g) if g else None) for k, g in access.items()}
    corr = sc._corr
    for n, P in lotpoly.items():
        pid = PID_of(n); res["parking"][n] = {}
        for d in DEPTHS:
            lvl = gmin[n] + d
            for thr, tag in ((0.2, "le200mm"), (0.5, "le500mm")):
                ok = (Z >= lvl - thr) & (lot_of == n)
                cells = [box(x - .5, y - .5, x + .5, y + .5) for x, y in zip(X[ok], Y[ok])]; okp = unary_union(cells) if cells else Polygon()
                blocked = unary_union([u.buffer(0.5) for u in unit_by_lot.get(n, [])] + ([corr[pid]] if corr[pid] is not None else []) + [g for g in acc_poly.values() if g is not None])
                allowed = okp.difference(blocked) if not okp.is_empty else okp
                spaces = count_spaces(allowed, P)
                res["parking"][n].setdefault(str(d), {})[tag] = {"area_ok_m2": round(okp.area, 1), "area_ok_pct": round(100 * okp.area / P.area, 1), "free_area_m2": round(allowed.area, 1), "spaces": spaces}
            res["parking"][n][str(d)]["required_spaces"] = 2 * len(unit_by_lot.get(n, []))
    res["accessway"] = {}
    for k, g in acc_poly.items():
        if g is None: continue
        m = contains_xy(g, X, Y) & ~np.isnan(Z); res["accessway"][k] = {"pixels": int(m.sum()), "ground_min": round(float(Z[m].min()), 2), "ground_max": round(float(Z[m].max()), 2), "area_m2": round(g.area, 1), "lots_served": [n for n in lotpoly if lotpoly[n].intersects(g)],
                                                                          "max_depth_by_peak_depth": {str(d): round(float(max(0.0, max(gmin[lot_of[yy, xx]] + d - Z[yy, xx] for yy, xx in zip(*np.where(m))))), 2) for d in DEPTHS}}
    # displaced volume (compensatory storage) per unit: piles over the wetted height, plus 25% for stair/walkway piles (ASSUMED)
    for u in res["units"]:
        res["storage"][u["id"]] = {str(d): round(1.25 * sum(bsq * bsq * max(0.0, gmin[u["lot"]] + d - p["ground"]) for p in u["piles"]), 2) for d in DEPTHS}
    runsA = {k: runs[k] for k in ("2+4|THAB|flood", "6+8|MHU|flood")}; res["impervious"] = {k: {"roof_m2": UNIT_A * r["units"], "access_m2": r.get("access_m2", 0), "parking_m2": 12.5 * 2 * r["units"], "units": r["units"]} for k, r in runsA.items()}
    res["lots_ground_min"] = gmin; jdump(res, DATA / "eng_results.json"); print("units", [u["id"] for u in res["units"]]); print(json.dumps(res["lookup"]["0.6|1.0"]), res["uplift"][1], res["accessway"])
def PID_of(n): return next(p for p in IDS if NUM[p] == n)
def shape_from(wkt_): from shapely import wkt; return wkt.loads(wkt_)
def count_spaces(allowed, lot):
    if allowed.is_empty: return 0
    best = 0
    th0 = lot_theta(lot)
    for th in (th0, th0 + 90):
        for (w, l) in ((2.5, 5.0), (5.0, 2.5)):
            c = allowed.centroid; a = affinity.rotate(allowed, -th, origin=c); minx, miny, maxx, maxy = a.bounds; placed = []; y = miny
            while y + l <= maxy + 1e-9:
                x = minx
                while x + w <= maxx + 1e-9:
                    cell = box(x, y, x + w, y + l)
                    if a.buffer(1e-6).contains(cell) and not any(cell.intersection(p).area > 1e-6 for p in placed): placed.append(cell); x += w
                    else: x += 0.5
                y += 0.5
            best = max(best, len(placed))
    return best
def lot_theta(lot):
    pts = list(lot.minimum_rotated_rectangle.exterior.coords); return math.degrees(math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]))
if __name__ == "__main__": main()
