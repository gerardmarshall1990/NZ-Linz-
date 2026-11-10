#!/usr/bin/env python3
"""Step 3 engine runs: 60 m2 (4 x 15 m) relocatables on each title and each combination of titles, under four zoning regimes, with and without a 2 m each-side overland flow path clearance.
Writes data/hazard/parrish/scenario_runs.json (cached by run key). Uses the app's layout engine (S14) with the zone standards in the rules table (S7)."""
import json, sys, concurrent.futures as cf
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from common import *
from backend.app import devscenarios, devlayout, devrules
ZN = {"THAB": "Residential - Terrace Housing and Apartment Building Zone", "MHU": "Residential - Mixed Housing Urban Zone", "SHZ": "Residential - Single House Zone"}
REG = {"A": {"name": "Operative zoning (AUP map today)", "phys": {2: "THAB", 4: "THAB", 6: "MHU", 8: "MHU"}, "rule": {2: "THAB", 4: "THAB", 6: "MHU", 8: "MHU"}},
       "B": {"name": "Current legal position (operative + PC120 immediate-effect rezoning rules on 2 and 4)", "phys": {2: "THAB", 4: "THAB", 6: "MHU", 8: "MHU"}, "rule": {2: "SHZ", 4: "MHU", 6: "MHU", 8: "MHU"}},
       "C": {"name": "PC120 as notified (3 Nov 2025)", "phys": {2: "SHZ", 4: "MHU", 6: "THAB", 8: "THAB"}, "rule": {2: "SHZ", 4: "MHU", 6: "THAB", 8: "THAB"}},
       "D": {"name": "PC120 with Council's August 2026 proposed amendments (Single House, flood hazards)", "phys": {p: "SHZ" for p in (2, 4, 6, 8)}, "rule": {p: "SHZ" for p in (2, 4, 6, 8)}}}
COMBOS = [("2", [2]), ("4", [4]), ("6", [6]), ("8", [8]), ("2+4", [2, 4]), ("6+8", [6, 8]), ("2+4+6+8", [2, 4, 6, 8]), ("2|4|6|8 separate titles", None)]
PID = {v: k for k, v in NUM.items()}; PID = {int(k): v for k, v in {v: k for k, v in NUM.items()}.items()} if False else {int(n): p for p, n in NUM.items()}
UNIT = {"width_m": UNIT_W, "depth_m": UNIT_L, "height_m": 3.8, "wall_height_m": 2.7, "gfa_m2": UNIT_A, "bedrooms": 2}
_sites = {}; _corr = {}
def setup():
    global _sites, _corr
    if _sites: return
    _sites.update({p: devscenarios.load_site(p) for p in IDS})
    lines = [shape(f["geometry"]) for f in jload(DATA / "overland_flow_paths.geojson")["features"]]
    for p in IDS:
        near = [g for g in lines if g.distance(_sites[p]["poly"]) <= 2.01]; _corr[p] = unary_union([g.buffer(2.0, cap_style="flat") for g in near]) if near else None
def groups(combo_lots, reg):
    """Contiguous lots of the same physical zone form one amalgamated group (a split-zone site is assessed per zone portion: ASSUMED)."""
    out = []
    for n in combo_lots:
        z = REG[reg]["phys"][n]
        if out and out[-1]["zone"] == z: out[-1]["lots"].append(n)
        else: out.append({"zone": z, "lots": [n]})
    return out
def run_key(lots, zone, flood): return f"{'+'.join(map(str, lots))}|{zone}|{'flood' if flood else 'noflood'}"
def run(args):
    lots, zone, flood = args; setup(); pids = [PID[n] for n in lots]
    U = unary_union([_sites[p]["poly"] for p in pids]); U = U.simplify(0.02) if len(pids) > 1 else U
    if U.geom_type != "Polygon": return run_key(lots, zone, flood), {"units": 0, "note": "not one piece"}
    front = _sites[pids[0]]["front_point"]; excl = unary_union([_corr[p] for p in pids if _corr[p] is not None]) if flood else None
    if excl is not None and excl.is_empty: excl = None
    R = devrules.zone_rules(ZN[zone]); b = devlayout.best(U, ZN[zone], UNIT, 3.5, front, R, None, excl, ("end", "side")); top = b["compliant"][0] if b["compliant"] else None; bind = devlayout.binding_constraint(b)
    res = {"units": top["unit_count"] if top else 0, "binding": bind["binding"], "explanation": bind["explanation"], "envelope_m2": round(b["envelope"].area, 1), "area_m2": round(U.area, 1), "zone": zone,
           "checks": [{k: c[k] for k in ("id", "status", "rule", "measured", "required", "unit")} for c in (top["checks"] if top else [])]}
    if top: res["units_geom"] = [mapping(u["footprint"]) for u in top["units"]]; res["ols_geom"] = [mapping(u["ols"]) if u.get("ols") is not None else None for u in top["units"]]; res["access_geom"] = mapping(top["access"]) if top["access"] is not None else None; res["access_m2"] = round(top["access"].area, 1) if top["access"] is not None else 0.0
    return run_key(lots, zone, flood), res
def needed():
    need = set()
    for reg in REG:
        for label, lots in COMBOS:
            lst = [[n] for n in (2, 4, 6, 8)] if lots is None else None
            for sub in (lst or [lots]):
                for g in groups(sub, reg):
                    for fl in (True, False): need.add((tuple(g["lots"]), g["zone"], fl))
    return sorted(need)
if __name__ == "__main__":
    cache_p = DATA / "scenario_runs.json"; cache = jload(cache_p) if cache_p.exists() else {}
    todo = [a for a in needed() if run_key(*a) not in cache]; print(len(todo), "runs to do of", len(needed()), flush=True)
    with cf.ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3) as ex:
        for k, r in ex.map(run, todo):
            cache[k] = r; jdump(cache, cache_p); print(k, r.get("units"), r.get("binding"), flush=True)
