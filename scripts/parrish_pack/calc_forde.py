#!/usr/bin/env python3
"""Flood design lookups per Forde Brothers house (10 houses). CALCULATED from DATA (LiDAR, Council layers) and ASSUMED inputs. Output: data/hazard/parrish/eng_results.json (same schema as before, plus type/pile counts)."""
import json, math, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np
from shapely import wkt as W_, contains_xy
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
from common import *
import ground, scenarios as sc
from calc import lot_frame, ASSUME as A0, CHS, Z_chs, count_spaces, PID_of
LAY = jload(DATA / "forde_layout.json"); HO = LAY["houses"]
DEAD = 150.0; LIVE = 1.5
ASSUME = {**A0, "unit_dead_load_kg_m2": (DEAD, "ASSUMED 150 kg/m2 for older timber houses (owner's brief); replace with house data"),
          "piles_per_unit": ("12 (Dulwich 7 x 12: 4 rows x 3 lines); 10 (Williams 5 x 13: 5 rows x 2 lines)", "ASSUMED grids; rows from the street end"),
          "spaces_per_unit": ("0 and 1 tested", "AUP E27.6.2(1)(b): minimum parking rates deleted; residential max rows 'No maximum' (Tables E27.6.2.3, E27.6.2.4, S7). NPS-UD not read: UNVERIFIED"),
          "house_dimensions": ("Dulwich 7 x 12 m (84 m2; listed 85 m2); Williams 5 x 13 m (65 m2)", "ASSUMED: supplier data to obtain")}
GRID = {"D": ((0.75, 4.25, 7.75, 11.25), (-3.0, 0.0, 3.0)), "W": ((0.75, 3.9, 7.0, 10.1, 12.25), (-1.75, 1.75))}
def main():
    sc.setup(); sites = sc._sites; haz = jload(DATA / "hazard_report.json")
    lotpoly = {NUM[p]: sites[p]["poly"] for p in IDS}; gmin = {NUM[p]: haz["lots"][str(p)]["ground"]["elevation_min_m"] for p in IDS}; frames = {NUM[p]: lot_frame(sites[p]) for p in IDS}
    rec = []; cnt = 0
    for n in ("2", "4", "6", "8"):
        ax, ay, ux, uy, vx, vy = frames[n]
        for h in LAY["lots"][n]["houses"]:
            cnt += 1; poly = W_.loads(h["poly"]); T = HO[h["type"]]; L = h["l"]; Wd = h["w"]; c = poly.centroid; lx, ly = vx, vy; tx, ty = -ly, lx
            s0x, s0y = c.x - lx * L / 2, c.y - ly * L / 2; rows, offs = GRID[h["type"]]
            piles = [(s0x + lx * s + tx * o, s0y + ly * s + ty * o, k + 1) for k, s in enumerate(rows) for o in offs]
            gx, gy, gz = ground.inside(poly)
            rec.append({"id": f"H{cnt}", "lot": n, "type": h["type"], "name": T["name"], "w": Wd, "l": L, "area": round(Wd * L, 1), "ground_mean": float(gz.mean()), "ground_min": float(gz.min()), "ground_max": float(gz.max()), "ground_door": ground.sample(s0x + lx * 0.3, s0y + ly * 0.3),
                        "street_end": [s0x, s0y], "axis": [lx, ly], "poly": poly.wkt, "piles": [{"id": f"P{k}{chr(97 + i % len(offs))}", "x": x, "y": y, "row": k, "ground": ground.sample(x, y)} for i, (x, y, k) in enumerate(piles)]})
    res = {"assumptions": {k: {"value": v, "basis": b} for k, (v, b) in ASSUME.items()}, "units": [], "lookup": {}, "uplift": [], "uplift_W": [], "gravity": {}, "gravity_W": {}, "parking": {}, "storage": {}, "sizing": {}}
    rho, Cdp, Cdr, blk = RHO, 2.0, 1.2, 1.5; bsq, brd = 0.30, 0.1143; zs = 0.5; fy = 350.0; phi = 0.9
    for r in rec:
        u = {k: r[k] for k in ("id", "lot", "type", "name", "w", "l", "area")}; u.update({"ground_mean_RL": round(r["ground_mean"], 2), "ground_min_RL": round(r["ground_min"], 2), "ground_max_RL": round(r["ground_max"], 2), "ground_door_RL": round(r["ground_door"], 2), "levels": {}, "piles": r["piles"], "geom": r["poly"], "street_end": r["street_end"], "axis": r["axis"], "n_piles": len(r["piles"])})
        for d in DEPTHS:
            lvl = gmin[r["lot"]] + d; ffl = lvl + FREEBOARD; top = ffl - FLOOR_DEPTH; ex = [top - p["ground"] for p in r["piles"]]
            H = ffl - r["ground_door"]; nr = max(0, math.ceil(H / 0.175 - 1e-9)); run_ = (nr - 1) * 0.28 + 1.2 if nr else 0.0; ramp = 12 * max(H, 0)
            u["levels"][str(d)] = {"flood_level_RL": round(lvl, 2), "depth_at_unit_m": round(max(0, lvl - r["ground_mean"]), 2), "ffl_RL": round(ffl, 2), "chassis_underside_RL": round(top, 2), "pile_exposed_min_m": round(min(ex), 2), "pile_exposed_max_m": round(max(ex), 2),
                                   "ffl_above_mean_ground_m": round(ffl - r["ground_mean"], 2), "access_height_m": round(H, 2), "stair_risers": nr, "stair_run_m": round(run_, 1), "ramp_length_m": round(ramp, 1)}
            for v in VELS:
                hw = [max(0.0, lvl - p["ground"]) for p in r["piles"]]
                Fsq = [0.5 * rho * Cdp * bsq * h * v * v * blk / 1e3 for h in hw]; Frd = [0.5 * rho * Cdr * brd * h * v * v * blk / 1e3 for h in hw]
                Msq = max(f * (h / 2 + zs) for f, h in zip(Fsq, hw)); Mrd = max(f * (h / 2 + zs) for f, h in zip(Frd, hw))
                u.setdefault("loads", {})[f"{d}|{v}"] = {"max_pile_drag_square_kN": round(max(Fsq), 2), "max_pile_drag_round_kN": round(max(Frd), 2), "unit_total_drag_square_kN": round(sum(Fsq), 1), "unit_total_drag_round_kN": round(sum(Frd), 1),
                                                           "max_pile_moment_round_kNm": round(Mrd, 2), "max_pile_moment_square_kNm": round(Msq, 2), "dxv_m2s": round(max(hw) * v, 2), "max_wetted_height_m": round(max(hw), 2)}
        res["units"].append(u)
    for d in DEPTHS:
        for v in VELS:
            w = max(res["units"], key=lambda uu: uu["loads"][f"{d}|{v}"]["max_pile_moment_round_kNm"]); L_ = w["loads"][f"{d}|{v}"]
            Mreq = L_["max_pile_moment_round_kNm"]; Zreq = Mreq * 1e3 / (phi * fy); pick = next(((D, t, Z_chs(D, t)) for D, t in CHS if Z_chs(D, t) >= Zreq), None)
            tot = max(uu["loads"][f"{d}|{v}"]["unit_total_drag_round_kN"] for uu in res["units"]); brace = tot / 2 / math.cos(math.radians(45)); Abr = brace * 1e3 / (phi * fy) / 100
            res["lookup"][f"{d}|{v}"] = {"worst_unit": w["id"], "max_pile_moment_kNm": Mreq, "Z_required_cm3": round(Zreq, 1), "chs_pick": None if pick is None else {"OD_mm": pick[0], "t_mm": pick[1], "Z_cm3": round(pick[2], 1)}, "unit_total_drag_kN_max": round(tot, 1), "brace_axial_kN": round(brace, 1), "brace_area_cm2": round(Abr, 2), "dxv_max": w["loads"][f"{d}|{v}"]["dxv_m2s"]}
    for key, area, npl in (("uplift", 84.0, 12), ("uplift_W", 65.0, 10)):
        Wd = DEAD * 9.81 * area / 1e3
        for e in (0.2, 0.5, 0.8, 1.1):
            x = max(0.0, e - (FREEBOARD - FLOOR_DEPTH)); B = RHO * G * area * x / 1e3; U_ = max(0.0, B - 0.9 * Wd)
            res[key].append({"water_above_design_level_m": e, "water_above_floor_underside_m": round(x, 2), "buoyancy_kN": round(B, 1), "dead_kN": round(Wd, 1), "net_uplift_kN": round(U_, 1), "per_pile_kN": round(U_ / npl, 1)})
        w_uls = 1.2 * (DEAD * 9.81 / 1e3) + 1.5 * LIVE; res["gravity" if key == "uplift" else "gravity_W"] = {"uls_kPa": round(w_uls, 2), "per_pile_kN": round(w_uls * area / npl, 1), "basis": f"1.2G + 1.5Q on {area / npl:.1f} m2 tributary per pile; CALCULATED from ASSUMED G ({DEAD:.0f} kg/m2) and Q; combinations UNVERIFIED"}
    res["hydrostatic_per_m_solid_kN"] = {str(d): round(0.5 * RHO * G * d * d / 1e3, 2) for d in DEPTHS}
    # parking test: spaces (2.5 x 5.0) that fit outside house footprints (+0.5 m) and corridor on ground at or below 200 mm / 500 mm depth, inside the zone-independent 1 m yards; informational against 0 and 1 per house
    X, Y, Z = ground.grid(); lot_of = np.full(Z.shape, "", dtype=object)
    for n, P in lotpoly.items(): lot_of[contains_xy(P.buffer(-1.0), X, Y)] = n
    by_lot = {}
    for u in res["units"]: by_lot.setdefault(u["lot"], []).append(W_.loads(u["geom"]))
    corr = sc._corr
    for n, P in lotpoly.items():
        pid = PID_of(n); res["parking"][n] = {}
        for d in DEPTHS:
            lvl = gmin[n] + d
            for thr, tag in ((0.2, "le200mm"), (0.5, "le500mm")):
                ok = (Z >= lvl - thr) & (lot_of == n); cells = [box(x - .5, y - .5, x + .5, y + .5) for x, y in zip(X[ok], Y[ok])]; okp = unary_union(cells) if cells else Polygon()
                blocked = unary_union([u.buffer(0.5) for u in by_lot.get(n, [])] + ([corr[pid]] if corr[pid] is not None else [])); allowed = okp.difference(blocked) if not okp.is_empty else okp
                res["parking"][n].setdefault(str(d), {})[tag] = {"area_ok_m2": round(okp.area, 1), "area_ok_pct": round(100 * okp.area / P.area, 1), "free_area_m2": round(allowed.area, 1), "spaces": count_spaces(allowed, P)}
            res["parking"][n][str(d)]["required_spaces"] = len(by_lot.get(n, []))
    res["accessway"] = {}
    for u in res["units"]:
        res["storage"][u["id"]] = {str(d): round(1.25 * sum(bsq * bsq * max(0.0, gmin[u["lot"]] + d - p["ground"]) for p in u["piles"]), 2) for d in DEPTHS}
    roof = sum(u["area"] for u in res["units"]); res["impervious"] = {"FORDE10": {"roof_m2": round(roof, 1), "access_m2": 0.0, "parking_m2": 0.0, "units": len(res["units"])}}
    res["lots_ground_min"] = gmin; jdump(res, DATA / "eng_results.json"); print("houses", [(u["id"], u["lot"], u["type"], u["n_piles"], u["levels"]["1.2"]["pile_exposed_max_m"]) for u in res["units"]]); print(res["uplift"][1], res["gravity"], res["impervious"])
if __name__ == "__main__": main()
