import sys, json, concurrent.futures as cf
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import scenarios as sc
from scenarios import *
def run3(a):
    lots, zone, ola = a; sc.setup(); pids = [PID[n] for n in lots]
    U = unary_union([sc._sites[p]["poly"] for p in pids]); U = U.simplify(0.02) if len(pids) > 1 else U
    front = sc._sites[pids[0]]["front_point"]; R = dict(devrules.zone_rules(ZN[zone])); R["ols_ground_floor_min_area"] = {**(R.get("ols_ground_floor_min_area") or {"parameter":"x","operator":">=","unit":"m2","section_ref":"test"}), "v": ola}
    b = devlayout.best(U, ZN[zone], UNIT, 3.5, front, R, None, None, ("end", "side")); top = b["compliant"][0] if b["compliant"] else None
    return a, (top["unit_count"] if top else 0), devlayout.binding_constraint(b)["binding"], (top["checks"] and [c["id"] + ":" + c["status"] for c in top["checks"] if c["status"] in ("FAIL",)])
if __name__ == "__main__":
    jobs = [((n,), z, ola) for ola in (16, 0) for n, z in ((2, "THAB"), (4, "MHU"), (6, "MHU"), (8, "MHU"), (2, "SHZ"))]
    with cf.ProcessPoolExecutor(3) as ex:
        for r in ex.map(run3, jobs): print(r, flush=True)
