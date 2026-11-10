import sys, json, concurrent.futures as cf
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import scenarios as sc
from scenarios import *
def run4(a):
    lots, zone, ola, spu = a; sc.setup(); pids = [PID[n] for n in lots]
    U = unary_union([sc._sites[p]["poly"] for p in pids]); U = U.simplify(0.02) if len(pids) > 1 else U
    front = sc._sites[pids[0]]["front_point"]; R = dict(devrules.zone_rules(ZN[zone]))
    if ola is not None: R["ols_ground_floor_min_area"] = {**R["ols_ground_floor_min_area"], "v": ola}
    excl = unary_union([sc._corr[p] for p in pids if sc._corr[p] is not None]) if any(sc._corr[p] is not None for p in pids) else None
    b = devlayout.best(U, ZN[zone], UNIT, 3.5, front, R, spu, excl, ("end", "side")); top = b["compliant"][0] if b["compliant"] else None
    mx = max([c["unit_count"] for c in b["candidates"]] or [0])
    return a, (top["unit_count"] if top else 0), mx, devlayout.binding_constraint(b)["binding"]
if __name__ == "__main__":
    jobs = [(l, "MHU", o, sp) for l in ((4, 6, 8), (2, 4, 6, 8)) for o in (None, 16, 0) for sp in (1, 0)]
    with cf.ProcessPoolExecutor(3) as ex:
        for r in ex.map(run4, jobs): print(r, flush=True)
