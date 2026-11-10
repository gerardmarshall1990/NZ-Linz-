"""Complete preliminary design on an ADOPTED conservative basis (all inputs ASSUMED, stated). Writes data/hazard/parrish/design.json."""
import sys, math
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
E_ = jload(DATA / "eng_results.json")
B = dict(depth=1.2, v=2.0, su=25.0, alpha=0.5, phi_geo=0.5, scour=1.0, pier_D=0.30, conc_sub_kNm3=14.0, post_OD=114.3, post_t=5.4, fy=350.0, phi_s=0.9, E=200e3, K=2.0, debris_kg=200.0, debris_dt=0.1, bolt_As=157.0, bolt_fu=800.0, bolt_phi=0.8, nbolts=2, brace_A=480.0, brace_fy=250.0)
def chs(D, t):
    d = D - 2 * t; A = math.pi / 4 * (D ** 2 - d ** 2); I = math.pi / 64 * (D ** 4 - d ** 4); Z = I / (D / 2); return A, I, Z
A, I, Z = chs(B["post_OD"], B["post_t"])
units = E_["units"]; hexp = max(u["levels"]["1.2"]["pile_exposed_max_m"] for u in units); worst = next(u["id"] for u in units if u["levels"]["1.2"]["pile_exposed_max_m"] == hexp)
Ueff = max(x["per_pile_kN"] for x in E_["uplift"]); VULS = E_["gravity"]["per_pile_kN"]
# debris
Fd = B["debris_kg"] * B["v"] / B["debris_dt"] / 1000.0           # kN, impulse-momentum
h_app = hexp + B["scour"] * 0.5                                    # lever arm to fixity (m)
Mdeb = Fd * h_app + 0.0
Mdrag = E_["lookup"]["1.2|2.0"]["max_pile_moment_kNm"]
Mtot = Mdeb + E_["lookup"]["1.2|2.0"]["max_pile_moment_kNm"]
Mcap = B["phi_s"] * B["fy"] * Z / 1e6                                 # kNm
# buckling (Euler, K=2.0 over exposed + scour)
Le = B["K"] * (hexp + B["scour"]); Pcr = math.pi ** 2 * B["E"] * I / (Le * 1000) ** 2 / 1000        # kN
Pyield = B["phi_s"] * B["fy"] * A / 1000
# embedment: uplift (skin friction + submerged weight), start at below-scour length
def upl_cap(Lem):
    Ls = max(Lem - B["scour"], 0); shaft = B["phi_geo"] * B["alpha"] * B["su"] * math.pi * B["pier_D"] * Ls
    w = 0.9 * math.pi / 4 * B["pier_D"] ** 2 * Lem * B["conc_sub_kNm3"]; return shaft + w
L_up = next(L / 100 for L in range(100, 2000) if upl_cap(L / 100) >= Ueff)
# lateral (Broms short pile, cohesive, free head): H = 9 su D (L - 1.5D - f), f = H/(9 su D)
def broms_H(Lem):
    D = B["pier_D"]; cu = B["su"]; best = 0
    for k in range(0, 4000):
        Hh = k * 0.005
        f = Hh / (9 * cu * D); Lc = Lem - 1.5 * D - f
        if Lc <= 0: break
        e = hexp / 2 + B["scour"]                                  # load height above fixity
        Mmax = Hh * (e + 1.5 * D + 0.5 * f); Mres = 2.25 * D * cu * (Lem - 1.5 * D) ** 2 - 0.5 * 9 * cu * D * f ** 2 + 0 * 1
        Hu = 9 * cu * D * (Lem - 1.5 * D - f)
        if Hh <= Hu * 0.5: best = Hh                                # factor of 2 on lateral capacity (ASSUMED)
    return best
H_dem = E_["lookup"]["1.2|2.0"]["unit_total_drag_kN_max"] / 10 + Fd
L_lat = next(L / 100 for L in range(100, 2000) if broms_H(L / 100) >= H_dem)
Lem = max(L_up, L_lat, 2.5)
# bearing
qa = 9 * B["su"] * math.pi / 4 * B["pier_D"] ** 2 * B["phi_geo"]; shaft_down = B["phi_geo"] * B["alpha"] * B["su"] * math.pi * B["pier_D"] * (Lem - B["scour"])
Rdown = qa + shaft_down
# connection
Nt = B["bolt_phi"] * B["bolt_fu"] * B["bolt_As"] * B["nbolts"] / 1000
brace = B["phi_s"] * B["brace_fy"] * B["brace_A"] / 1000
# afflux (momentum): per unit, flow width W = 10 m
W = 10.0; aff = {}
for d in DEPTHS:
    for v in VELS:
        F = E_["lookup"][f"{d}|{v}"]["unit_total_drag_kN_max"]; aff[f"{d}|{v}"] = round(F * 1000 / (RHO * G * W * d) * 1000, 1)     # mm per unit
runoff = {f"{mm} mm": [round(a * mm / 1000, 2) for a in (240 + 140.8 + 100, 480.8 * 2)] for mm in (10, 20, 30)}
res = {"basis": B, "section": {"A_mm2": round(A, 0), "I_mm4": round(I, 0), "Z_mm3": round(Z, 0)}, "worst_pile_unit": worst, "exposed_max_m": hexp,
       "debris": {"F_kN": round(Fd, 1), "lever_m": round(h_app, 2), "M_debris_kNm": round(Mdeb, 2), "M_drag_kNm": Mdrag, "M_total_kNm": round(Mtot, 2), "M_cap_kNm": round(Mcap, 2), "util": round(Mtot / Mcap, 2)},
       "buckling": {"Le_m": round(Le, 2), "Pcr_kN": round(Pcr, 1), "Pyield_kN": round(Pyield, 1), "demand_kN": VULS, "util_Pcr": round(VULS / Pcr, 2), "util_yield": round(VULS / Pyield, 2)},
       "embedment": {"uplift_demand_kN": Ueff, "L_uplift_m": L_up, "L_lateral_m": L_lat, "L_adopted_m": round(max(L_up, L_lat, 2.5) + 0.0, 2), "lateral_demand_kN": round(H_dem, 2), "uplift_cap_at_adopted_kN": round(upl_cap(Lem), 1), "down_capacity_kN": round(Rdown, 1), "down_demand_kN": VULS},
       "connection": {"tie_cap_kN": round(Nt, 1), "tie_demand_kN": Ueff, "brace_cap_kN": round(brace, 1), "brace_demand_kN": E_["lookup"]["1.2|2.0"]["brace_axial_kN"]},
       "afflux_mm_per_unit": aff, "runoff_m3": runoff}
jdump(res, DATA / "design.json"); print(json.dumps(res, indent=0)[:2500])
