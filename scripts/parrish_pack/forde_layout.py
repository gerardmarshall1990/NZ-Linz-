"""Forde Brothers house layout on the real LINZ lots. Houses: Dulwich 25 type (ASSUMED 7 x 12 m, 85 m2 listed), Williams 1 type minor dwelling (ASSUMED 5 x 13 m, 65 m2 listed). One column per lot along the lot axis, solved on the lot polygon in its own frame.
Writes data/hazard/parrish/forde_layout.json."""
import sys, math, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np
from shapely.geometry import Polygon, box, Point
from shapely.ops import transform, unary_union
from shapely.prepared import prep
from common import *
import scenarios as sc
from calc import lot_frame
HOUSE = {"D": {"name": "Dulwich 25 type", "w": 7.0, "l": 12.0, "area_listed": 85, "beds": 3, "baths": 1, "price": "$100,000 + GST incl. delivery within 200 km and placed on foundations (owner's listing, UNVERIFIED here)"},
         "W": {"name": "Williams 1 type", "w": 5.0, "l": 13.0, "area_listed": 65, "beds": 2, "baths": 1, "price": "not supplied"}}
YARDS = {"THAB": (1.5, 1.0, 1.0, 50.0, "H6.6.9, H6.6.11"), "MHU": (2.5, 1.0, 1.0, 45.0, "H5.6.8, H5.6.10"), "SHZ": (3.0, 1.0, 1.0, 35.0, "H3.6.8, H3.6.10"), "USER": (1.5, 1.0, 1.0, None, "owner brief (1.5 front, 1 side/rear)")}
REG = {"A": {2: "THAB", 4: "THAB", 6: "MHU", 8: "MHU"}, "B": {2: "SHZ", 4: "MHU", 6: "MHU", 8: "MHU"}, "C": {2: "SHZ", 4: "MHU", 6: "THAB", 8: "THAB"}, "D": {2: "SHZ", 4: "SHZ", 6: "SHZ", 8: "SHZ"}}
GAP = 0.8
PID = {int(v): k for k, v in NUM.items()}
def to_frame(P, fr):
    ax, ay, ux, uy, vx, vy = fr; return transform(lambda x, y, z=None: ((np.asarray(x) - ax) * ux + (np.asarray(y) - ay) * uy, (np.asarray(x) - ax) * vx + (np.asarray(y) - ay) * vy), P)
def from_frame(P, fr):
    ax, ay, ux, uy, vx, vy = fr; return transform(lambda u, v, z=None: (ax + np.asarray(u) * ux + np.asarray(v) * vx, ay + np.asarray(u) * uy + np.asarray(v) * vy), P)
def buildable(Pf, yf, ys=1.0, yr=1.0):
    B = Pf.buffer(-min(ys, yr)); return B.intersection(box(-1e3, yf, 1e3, 1e3))
def solve(Bf, corr_f, dims, step_u=0.1, step_v=0.02, lmax_extra=0.0):
    """dims: list of (w,l) ordered from the street. -> list of boxes (frame) or None. Column: house centres share u."""
    pB = prep(Bf.buffer(1e-6)); minu, minv, maxu, maxv = Bf.bounds; best = None
    wmax = max(w for w, _ in dims)
    for uc in np.arange(minu + wmax / 2, maxu - wmax / 2 + 1e-9, step_u):
        v0 = minv
        while v0 < maxv:
            v = v0; rects = []; ok = True
            for w, l in dims:
                r = box(uc - w / 2, v, uc + w / 2, v + l)
                if not pB.contains(r) or (corr_f is not None and r.intersects(corr_f)): ok = False; break
                rects.append(r); v += l + GAP
            if ok:
                cand = (v0, abs(uc - (minu + maxu) / 2), uc, rects)
                if best is None or cand[:2] < best[:2]: best = cand
                break
            v0 += step_v
    return None if best is None else best
def main():
    sc.setup(); sites = sc._sites; out = {"houses": HOUSE, "yards": {k: v[:4] for k, v in YARDS.items()}, "gap_m": GAP, "lots": {}, "fits": {}, "maxlen": {}}
    comp = {2: ["D", "W"], 4: ["D", "D", "D"], 6: ["D", "D"], 8: ["D", "D", "D"]}
    for n in (2, 4, 6, 8):
        pid = PID[n]; P = sites[pid]["poly"]; fr = lot_frame(sites[pid]); Pf = to_frame(P, fr); corr = sc._corr[pid]; cf = to_frame(corr, fr) if corr is not None and not corr.is_empty else None
        out["lots"][n] = {"area_m2": round(P.area, 1), "depth_m": round(Pf.bounds[3] - Pf.bounds[1], 2), "width_m": round(Pf.bounds[2] - Pf.bounds[0], 2)}
        for ykey, (yf, ys, yr, cov, ref) in YARDS.items():
            Bf = buildable(Pf, yf, ys, yr)
            for k in range(1, len(comp[n]) + 1):
                dims = [(HOUSE[t]["w"], HOUSE[t]["l"]) for t in comp[n][:k]]
                s = solve(Bf, cf, dims); out["fits"][f"{n}|{ykey}|{k}"] = s is not None
                if s is not None and k == len(comp[n]):
                    # max length scale: extend all houses' length until it fails
                    lo, hi = 0.0, 6.0
                    if solve(Bf, cf, [(w, l + hi) for w, l in dims], 0.2, 0.05) is None:
                        for _ in range(9):
                            mid = (lo + hi) / 2
                            if solve(Bf, cf, [(w, l + mid) for w, l in dims], 0.1, 0.02) is None: hi = mid
                            else: lo = mid
                    else: lo = hi
                    Lx = lo
                    out["maxlen"][f"{n}|{ykey}"] = round(12.0 + Lx, 2) if comp[n][0] == "D" else None
                    if ykey == "USER":
                        v0, _, uc, rects = s
                        out["lots"][n]["houses"] = [{"type": t, "w": w, "l": l, "poly": from_frame(r, fr).wkt, "v0": round(r.bounds[1], 2), "uc": round(uc, 2)} for t, (w, l), r in zip(comp[n], dims, rects)]
                        out["lots"][n]["buildable_user_m2"] = round(Bf.area, 1)
        print(n, out["lots"][n]["depth_m"], out["lots"][n]["width_m"], {k: v for k, v in out["fits"].items() if k.startswith(str(n) + "|")}, {k: v for k, v in out["maxlen"].items() if k.startswith(str(n) + "|")}, flush=True)
    jdump(out, DATA / "forde_layout.json")
if __name__ == "__main__": main()
