"""Target schemes for the owner's 9 to 10 dwellings: all four lots as one MHU-standards site (stricter than THAB), with the 2 m flow-path offset. T9: 1 space per unit, standard outdoor living. T10: no on-site parking, outdoor living 16 m2 ground + 5 m2 raised deck (H5.6.14(1)(a)(b))."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import scenarios as sc
from scenarios import *
def go(key, spu, ola):
    sc.setup(); pids = [PID[n] for n in (2, 4, 6, 8)]
    U = unary_union([sc._sites[p]["poly"] for p in pids]).simplify(0.02); front = sc._sites[pids[0]]["front_point"]; R = dict(devrules.zone_rules(ZN["MHU"]))
    if ola is not None: R["ols_ground_floor_min_area"] = {**R["ols_ground_floor_min_area"], "v": ola}
    excl = unary_union([sc._corr[p] for p in pids if sc._corr[p] is not None])
    b = devlayout.best(U, ZN["MHU"], UNIT, 3.5, front, R, spu, excl, ("end", "side")); top = b["compliant"][0]; bind = devlayout.binding_constraint(b)
    per = {}
    for g in top["units"]:
        c = g["footprint"].centroid; lot = next((n for n in (2, 4, 6, 8) if sc._sites[PID[n]]["poly"].contains(c)), None)
        straddle = [n for n in (2, 4, 6, 8) if sc._sites[PID[n]]["poly"].intersection(g["footprint"]).area > 0.5]
        per.setdefault(str(lot), []).append(straddle)
    res = {"units": top["unit_count"], "binding": bind["binding"], "explanation": bind["explanation"], "area_m2": round(U.area, 1), "zone": "MHU", "spu": spu, "ola": ola,
           "checks": [{k: c[k] for k in ("id", "status", "rule", "measured", "required", "unit")} for c in top["checks"]], "units_geom": [mapping(u["footprint"]) for u in top["units"]], "ols_geom": [mapping(u["ols"]) if u.get("ols") is not None else None for u in top["units"]],
           "access_geom": mapping(top["access"]) if top["access"] is not None else None, "access_m2": round(top["access"].area, 1) if top["access"] is not None else 0, "alloc_by_lot": {k: len(v) for k, v in per.items()}, "straddles": {k: v for k, v in per.items()}}
    return key, res
if __name__ == "__main__":
    p = DATA / "scenario_runs.json"; cache = jload(p)
    for k, spu, ola in (("T9", 1, None), ("T10", 0, 16)):
        k, r = go(k, spu, ola); cache[k] = r; print(k, r["units"], r["alloc_by_lot"], r["binding"], [(c["id"], c["status"]) for c in r["checks"] if c["status"] in ("FAIL",)], r["straddles"])
    jdump(cache, p)
