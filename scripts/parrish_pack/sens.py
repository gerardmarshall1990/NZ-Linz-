import sys, json, concurrent.futures as cf
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import scenarios as sc
from scenarios import *
def run2(a):
    lots, zone, spu = a; sc.setup(); pids = [PID[n] for n in lots]
    U = unary_union([sc._sites[p]["poly"] for p in pids]); U = U.simplify(0.02) if len(pids) > 1 else U
    front = sc._sites[pids[0]]["front_point"]; R = devrules.zone_rules(ZN[zone])
    b = devlayout.best(U, ZN[zone], UNIT, 3.5, front, R, spu, None, ("end", "side")); top = b["compliant"][0] if b["compliant"] else None
    mx = max([c["unit_count"] for c in b["candidates"]] or [0])
    return a, (top["unit_count"] if top else 0), mx, devlayout.binding_constraint(b)["binding"]
if __name__ == "__main__":
    jobs = []
    for spu in (1, 0):
        for lots, z in (([2], "THAB"), ([4], "MHU"), ([6], "MHU"), ([8], "MHU"), ([2, 4], "THAB"), ([6, 8], "MHU"), ([4, 6, 8], "MHU")): jobs.append((tuple(lots), z, spu))
    with cf.ProcessPoolExecutor(3) as ex:
        for r in ex.map(run2, jobs): print(r, flush=True)
