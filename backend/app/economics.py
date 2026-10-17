"""Rest home economics and Offer Builder maths (MASTER_SPEC Part 3 section 6 and Part 6.4). Pure functions: no database, no network, and no environmental or site-risk data goes in (decision 13).
Rules: an unset input makes every output that depends on it None with a 'needs_input' list; nothing is silently defaulted. Every output carries the lowest confidence tier of its inputs.
All money is NZD; 'weekly' means per week; a year is 52 weeks. Projections are illustrative."""
from __future__ import annotations
import math
from functools import lru_cache
import yaml
from .config import ROOT
from .tiers import lowest

W = 52
OPEX_KEYS = ["fee_per_bed_per_week", "food_per_occupied_bed_per_week", "staff_wage_per_week", "staff_positions_per_8_beds", "roster_coverage_multiplier", "clinical_lead_cost_per_week",
             "manager_cost_per_week", "cook_cleaner_laundry_per_week", "utilities_per_week", "insurance_per_year", "supplies_per_occupied_bed_per_week",
             "repairs_maintenance_per_year", "compliance_and_certification_per_year", "other_opex_per_week"]

@lru_cache
def default_assumptions() -> dict: return yaml.safe_load((ROOT / "config/deal_assumptions.yaml").read_text())
@lru_cache
def timeline_defaults() -> dict: return yaml.safe_load((ROOT / "config/timeline_defaults.yaml").read_text())

FORMULAS = [
    "occupied beds = beds x occupancy",
    "revenue per week = occupied beds x fee per bed per week",
    "food per week = occupied beds x food per occupied bed per week",
    "staffing per week = (beds / 8) x staff positions per 8 beds x wage per position x roster coverage multiplier (fixed to the roster, does not fall with occupancy)",
    "supplies per week = occupied beds x supplies per occupied bed per week (assumption: variable with occupancy)",
    "fixed other per week = clinical lead + manager + cook/cleaner/laundry + utilities + other + (insurance + repairs + compliance) / 52",
    "net operating profit N per week (before rent or any owner share) = revenue - food - staffing - supplies - fixed other",
    "retrofit charge per week: I fund = retrofit amortised over the lease term at the cost of capital; owner funds = retrofit x owner required yield, as a rent uplift",
    "walk-away rent per week = N - retrofit charge - minimum acceptable profit per week; rent headroom is the same with target profit",
]

def missing(p: dict, keys) -> list[str]: return [k for k in keys if p.get(k) is None]

def operating(beds: float, occupancy: float, p: dict) -> dict:
    """Weekly operating figures at a given occupancy. net is None when any required input is unset."""
    need = missing(p, OPEX_KEYS)
    if need: return {"needs_input": need, "net": None}
    occ_beds = beds * occupancy
    revenue = occ_beds * p["fee_per_bed_per_week"]; food = occ_beds * p["food_per_occupied_bed_per_week"]
    staff = (beds / 8) * p["staff_positions_per_8_beds"] * p["staff_wage_per_week"] * p["roster_coverage_multiplier"]
    supplies = occ_beds * p["supplies_per_occupied_bed_per_week"]
    fixed = (p["clinical_lead_cost_per_week"] + p["manager_cost_per_week"] + p["cook_cleaner_laundry_per_week"] + p["utilities_per_week"] + p["other_opex_per_week"]
             + (p["insurance_per_year"] + p["repairs_maintenance_per_year"] + p["compliance_and_certification_per_year"]) / W)
    net = revenue - food - staff - supplies - fixed
    return {"needs_input": [], "beds": beds, "occupancy": occupancy, "occupied_beds": occ_beds, "revenue": revenue, "food": food, "staffing": staff, "supplies": supplies, "fixed_other": fixed, "net": net}

def amortised_weekly(cost: float, years: float, rate_pct: float) -> float:
    """Level weekly payment repaying `cost` over `years` at `rate_pct` per year (monthly-compounded annuity paid weekly-equivalent)."""
    n = years * 12; r = rate_pct / 100 / 12
    monthly = cost / n if r == 0 else cost * r / (1 - (1 + r) ** -n)
    return monthly * 12 / W

def retrofit_charge_weekly(retrofit: float | None, p: dict) -> dict:
    if retrofit is None: return {"needs_input": ["retrofit_cost"], "weekly": None}
    mode = p.get("retrofit_funding_mode") or "i_fund"
    if mode == "i_fund":
        need = missing(p, ["lease_term_years", "cost_of_capital_pct"])
        return {"needs_input": need, "weekly": None if need else amortised_weekly(retrofit, p["lease_term_years"], p["cost_of_capital_pct"]), "mode": mode}
    need = missing(p, ["owner_required_yield_on_capex_pct"])
    return {"needs_input": need, "weekly": None if need else retrofit * p["owner_required_yield_on_capex_pct"] / 100 / W, "mode": mode}

def feasibility(beds: float, p: dict, retrofit: float | None, confidence: str | None = None) -> dict:
    """Stabilised economics, rent headroom, walk-away rent and break-even occupancy (Part 3 section 6.2)."""
    out = {"formulas": FORMULAS, "confidence": confidence, "banner": "Screening only: bedrooms/plans not confirmed" if confidence in (None, "ESTIMATED") else None,
           "label": "Illustrative projection from my assumptions; a quantity surveyor and an accountant must confirm. Not advice.", "needs_input": []}
    if p.get("stabilised_occupancy") is None: out["needs_input"].append("stabilised_occupancy")
    if out["needs_input"]: out.update(stabilised=None, walk_away_rent_per_week=None, rent_headroom_per_week=None); return out
    st = operating(beds, p["stabilised_occupancy"], p)
    out["stabilised"] = st; out["needs_input"] = list(st["needs_input"])
    if st["net"] is None: out.update(walk_away_rent_per_week=None, rent_headroom_per_week=None); return out
    ch = retrofit_charge_weekly(retrofit, p); out["retrofit_charge"] = ch
    out["stabilised_annual_profit_before_rent"] = st["net"] * W; out["margin"] = st["net"] / st["revenue"] if st["revenue"] else None
    tgt, mn = p.get("target_profit_per_year"), p.get("minimum_acceptable_profit_per_year")
    out["walk_away_rent_per_week"] = out["rent_headroom_per_week"] = None
    if ch["weekly"] is None: out["needs_input"] += ch["needs_input"]
    else:
        if mn is None: out["needs_input"].append("minimum_acceptable_profit_per_year")
        else: out["walk_away_rent_per_week"] = st["net"] - ch["weekly"] - mn / W
        if tgt is None: out["needs_input"].append("target_profit_per_year")
        else: out["rent_headroom_per_week"] = st["net"] - ch["weekly"] - tgt / W
    out["break_even_occupancy"] = breakeven_occupancy(beds, p, ch["weekly"] or 0.0, rent=None)
    return out

def solve_occupancy(f, target: float = 0.0, hi: float = 1.0) -> float | None:
    """Smallest occupancy in [0, hi] where f(occ) = target for an increasing f; None if not reached by `hi`."""
    if f(hi) < target: return None
    if f(0.0) >= target: return 0.0
    lo, up = 0.0, hi
    for _ in range(80):
        mid = (lo + up) / 2
        if f(mid) >= target: up = mid
        else: lo = mid
    return up

def breakeven_occupancy(beds: float, p: dict, retrofit_charge_w: float, rent: float | None) -> dict:
    """Occupancy at which profit after rent and retrofit charge is 0, and equals the target (solved numerically)."""
    if missing(p, OPEX_KEYS): return {"needs_input": missing(p, OPEX_KEYS)}
    f = lambda o: operating(beds, o, p)["net"] - (rent or 0.0) - retrofit_charge_w
    tgt = p.get("target_profit_per_year")
    return {"profit_zero": solve_occupancy(f, 0.0), "profit_target": solve_occupancy(f, tgt / W) if tgt is not None else None, "rent_assumed": rent,
            "note": "None means not reached even at 100% occupancy"}

# ----------------------------------------------------------------------------------- Offer Builder (Part 6.4)
def _tier(*tiers): return lowest([t for t in tiers if t])

def _weekly_cash(mode: str, t: dict, N_of_occ, occupancy_by_week, weeks_conv: dict, C: float, i_fund: bool, pre_opening: float, wc: float, current_rent: float, horizon: int) -> dict:
    """Week-by-week operator cash. Returns the curve, cash required components, peak cash, owner receipts and full-timeline payback."""
    consent, works, audit = weeks_conv["consent"], weeks_conv["works"], weeks_conv["audit"]
    conv = consent + works + audit
    curve, cum, peak = [], 0.0, 0.0
    comp = {"retrofit": C if i_fund else 0.0, "owner_payments_during_conversion": 0.0, "pre_opening": pre_opening, "ramp_deficits": 0.0, "working_capital": wc}
    owner_cum = []; owner_total = 0.0
    rent_free = t.get("rent_free_weeks") or 0
    for wk in range(horizon):
        flow = 0.0
        if wk < conv:
            pay = 0.0
            if mode == "fixed": pay = 0.0 if wk < rent_free else t["rent"]
            elif mode == "hybrid": pay = t["floor"]
            elif mode == "jv": pay = t.get("conversion_payment_per_week") or 0.0
            flow -= pay; comp["owner_payments_during_conversion"] += pay; owner_total += pay
            if wk >= consent and wk < consent + works and i_fund and works: flow -= C / works          # retrofit drawn evenly over the works weeks
            span = works + audit
            if span and wk >= consent and wk < conv: flow -= pre_opening / span                         # pre-opening costs spread over works and audit
        else:
            occ = occupancy_by_week(wk - conv); N = N_of_occ(occ)
            if mode == "fixed": share = t["rent"]
            elif mode == "jv": share = t["s"] * N
            else: share = t["floor"] + t["s_h"] * max(0.0, N - t["threshold"])
            flow += N - share; owner_total += share
            if flow < 0: comp["ramp_deficits"] += -flow
        if wk == conv: flow -= wc
        cum += flow; curve.append(cum); peak = min(peak, cum)
        owner_cum.append(owner_total)
    return {"curve": curve, "peak_cash": -peak, "components": comp, "owner_cumulative": owner_cum}

def run_offer(inp: dict) -> dict:
    """Compute all three offer modes and rank them. See tests/test_economics.py (worked example) for a minimal input.
    inp: asking_rent R0; current_net (owner's current income, else R0 is used and labelled); N: number | {low, base, high} weekly net at stabilised_occupancy; stabilised_occupancy;
    retrofit C: number | {low, base, high}; allowance_pct (share of C from allowances); timeline {consent_weeks, works_weeks, audit_weeks}; fill_ramp_by_month; pre_opening_costs; working_capital;
    funding 'i_fund'|'owner_funds'; walk_away_rent (weekly, from feasibility, else None = needs input); cash_limit; confidence tiers {N, C}; terms {multiple, s, floor, s_h, threshold, conversion_payment_per_week,
    rent_free_weeks, retrofit_recovery_first, lease_term_years}; N_fn: optional occupancy -> weekly net (from the operating model); downside {occupancy, n_haircut}."""
    R0 = inp["asking_rent"]; cur = inp.get("current_net")
    cur_used = cur if cur is not None else R0
    tr = lambda v, k: v[k] if isinstance(v, dict) else v
    N = lambda k: tr(inp["N"], k); C = lambda k: tr(inp["retrofit"], k)
    occ_stab = inp["stabilised_occupancy"]; tl = inp["timeline"]; terms = inp["terms"]; funding = inp.get("funding", "i_fund")
    ramp = inp.get("fill_ramp_by_month") or []
    flags, needs = [], []
    for k in ("timeline", "stabilised_occupancy"):
        if inp.get(k) is None: needs.append(k)
    pre = inp.get("pre_opening_costs"); wc = inp.get("working_capital")
    for k, v in (("pre_opening_costs", pre), ("working_capital", wc)):
        if v is None: needs.append(k)
    if needs: return {"needs_input": needs, "modes": {}, "label": "Needs input: no offer maths is shown with unset inputs."}
    weeks_conv = {"consent": tl["consent_weeks"], "works": tl["works_weeks"], "audit": tl["audit_weeks"]}
    conv = sum(weeks_conv.values())
    def occ_week(wk_after_open):
        if not ramp: return occ_stab
        m = int(wk_after_open * 12 / W)
        return min(ramp[m], occ_stab) if m < len(ramp) else occ_stab
    base_fn = inp.get("N_fn")
    def make_N(nk):
        if base_fn and nk == "base": return base_fn
        scale = N(nk) / N("base") if N("base") else 1.0
        if base_fn: return lambda o: base_fn(o) * scale
        return lambda o: N(nk) * o / occ_stab   # proportional approximation: real fixed staffing makes low occupancy worse (stated in assumptions)
    ds = inp.get("downside") or {"occupancy": 0.6, "n_haircut": 0.30}
    Nb = make_N("base"); N_stab = Nb(occ_stab)
    horizon = int(inp.get("horizon_weeks") or 156)
    i_fund = funding == "i_fund"
    wa = inp.get("walk_away_rent")
    allowance = inp.get("allowance_pct")
    if allowance is not None and allowance > 30: flags.append({"level": "red", "text": f"{allowance:.0f}% of retrofit cost comes from allowances: mostly allowances, get QS pricing before relying on this"})
    modes = {}
    def finish(mode, t, owner_stab, owner_fn):
        """owner_stab: owner weekly at stabilisation (base); owner_fn(N) -> owner weekly given a net."""
        mflags = []
        op_net = N_stab - owner_stab
        cash = _weekly_cash(mode, t, Nb, occ_week, weeks_conv, C("base"), i_fund, pre, wc, cur_used, horizon)
        comp = cash["components"]; required = sum(comp.values())
        payback_simple = C("base") / op_net if (i_fund and op_net > 0) else None
        full = next((i + 1 for i, v in enumerate(cash["curve"]) if i >= conv and v >= 0), None)      # weeks from lease start until cumulative cash is back to zero
        owner_at = lambda occ: owner_fn(Nb(occ))
        cases = {"occ_60": owner_at(0.6), "occ_80": owner_at(0.8), "occ_100": owner_at(1.0),
                 "occ_downside": owner_at(ds["occupancy"]), "n_lower": owner_fn(N_stab * (1 - ds["n_haircut"]))}
        cumul = lambda w: cash["owner_cumulative"][min(w, horizon) - 1]
        out = {"owner": {"weekly_at_stabilisation": owner_stab, "multiple_of_current": owner_stab / cur_used, "current_income_used": cur_used,
                         "current_income_note": None if cur is not None else "owner's current income not entered: asking rent used as the comparison",
                         "weekly_during_conversion": (cash["owner_cumulative"][0] if conv else None), "cases": cases,
                         "cumulative_12m": cumul(52), "cumulative_24m": cumul(104), "vs_leaving_as_is_12m": cumul(52) - cur_used * 52, "vs_leaving_as_is_24m": cumul(104) - cur_used * 104},
               "operator": {"stabilised_weekly_net_after_owner": op_net, "payback_weeks_stabilised_only": payback_simple,
                            "payback_weeks_full_timeline_from_lease_start": full, "cash_required": required, "cash_components": comp, "peak_cash": cash["peak_cash"],
                            "cash_curve_by_month": [round(cash["curve"][min(int(m * W / 12), horizon - 1)], 2) for m in range(0, int(horizon * 12 / W))],
                            "excludes_note_for_simple_payback": "The simple payback excludes the conversion period, any payments to the owner during it, the fill ramp and pre-opening costs. The full-timeline figures include them."}}
        # break-even occupancy for each party (solved numerically)
        if base_fn:   # break-even needs the real cost structure (fixed staffing); the proportional approximation would say zero
            out["break_even_occupancy"] = {"operator_zero_profit": solve_occupancy(lambda o: Nb(o) - owner_fn(Nb(o)), 0.0, 1.0),
                                           "owner_equals_current": solve_occupancy(lambda o: owner_fn(Nb(o)), cur_used, 1.0),
                                           "note": "None = not reached even at 100% occupancy"}
        else: out["break_even_occupancy"] = {"needs_input": ["operating model (N as a function of occupancy)"]}
        if cash["peak_cash"] is not None and inp.get("cash_limit") is not None and required > inp["cash_limit"]: mflags.append({"level": "red", "text": "cash required is above your stated cash limit"})
        out["flags"] = mflags; out["terms"] = t
        return out
    # A. fixed rent
    if terms.get("multiple") is not None:
        if wa is None: modes["fixed"] = {"needs_input": ["walk_away_rent (needs the operating inputs, retrofit cost, lease term, cost of capital and minimum profit)"], "blocked": True}
        else:
            rent = min(terms["multiple"] * R0, wa); t = {"rent": rent, "rent_free_weeks": terms.get("rent_free_weeks")}
            m = finish("fixed", t, rent, lambda n: rent)
            m["multiple_achieved"] = rent / R0; m["capped_at_walk_away"] = terms["multiple"] * R0 > wa
            m["flags"].append({"level": "info", "text": "Rent is never above the walk-away rent: capped" if m["capped_at_walk_away"] else "Rent is within the walk-away rent"})
            if R0 > wa: m["flags"].append({"level": "red", "text": "asking rent is above the walk-away rent: not viable at the asking rent"})
            modes["fixed"] = m
    # B. JV share
    if terms.get("s") is not None:
        s = terms["s"]; t = {"s": s, "conversion_payment_per_week": terms.get("conversion_payment_per_week"), "retrofit_recovery_first": bool(terms.get("retrofit_recovery_first"))}
        m = finish("jv", t, s * N_stab, lambda n: s * n)
        m["owner"]["multiple_at_cases"] = {k: v / cur_used for k, v in m["owner"]["cases"].items()}
        if not terms.get("conversion_payment_per_week"):
            m["flags"].append({"level": "amber", "text": "profit share with no minimum payment: the owner receives nothing during consent, works, audit and fill" + (" and is below current income at a downside case" if min(m["owner"]["cases"].values()) < cur_used else "")})
        elif min(m["owner"]["cases"].values()) < cur_used: m["flags"].append({"level": "amber", "text": "owner's share is below current income at a downside case"})
        # treatment with retrofit recovered first: operator keeps all net until C is repaid, then sharing begins
        if i_fund and N_stab > 0: m["retrofit_recovery_first"] = {"weeks_before_sharing_starts": C("base") / N_stab, "owner_income_until_then": t["conversion_payment_per_week"] or 0.0,
                                                                  "note": "shown beside the default treatment; the switch is off by default"}
        m["note_net_definition"] = ("Net operating profit shared = revenue minus food, staffing (with roster coverage), clinical lead and manager, utilities, insurance, compliance and certification, supplies, repairs and maintenance and other agreed operating costs, before the JV share.")
        modes["jv"] = m
    # C. hybrid
    if terms.get("floor") is not None and terms.get("s_h") is not None:
        t = {"floor": terms["floor"], "s_h": terms["s_h"], "threshold": terms.get("threshold") or 0.0}
        fn = lambda n: t["floor"] + t["s_h"] * max(0.0, n - t["threshold"])
        m = finish("hybrid", t, fn(N_stab), fn)
        m["flags"].append({"level": "info", "text": "the minimum payment starts at lease commencement and runs through consent, works, audit and fill"})
        modes["hybrid"] = m
    for k, m in modes.items():
        if wa is not None and not m.get("blocked") and m["owner"]["weekly_at_stabilisation"] > wa + 1e-9: m["flags"].append({"level": "red", "text": "offer is above the walk-away rent"})
        m["flags"] = m.get("flags", []) + flags
    # rank: fewest red flags first, then the operator's stabilised net after the owner's share
    ranked = sorted((k for k, m in modes.items() if not m.get("blocked")), key=lambda k: (sum(f["level"] == "red" for f in modes[k]["flags"]), -modes[k]["operator"]["stabilised_weekly_net_after_owner"]))
    return {"needs_input": [], "confidence": _tier(inp.get("confidence", {}).get("N"), inp.get("confidence", {}).get("C")), "modes": modes, "ranking": ranked,
            "range": {"retrofit": {"low": C("low"), "base": C("base"), "high": C("high")}, "N": {"low": N("low"), "base": N("base"), "high": N("high")}},
            "assumptions": ["N is the weekly net operating profit at the stabilised occupancy; below that it is " + ("taken from the operating model (fixed staffing)." if base_fn else "scaled in proportion to occupancy, which flatters low occupancy because staffing is fixed."),
                            f"Downside cases: occupancy {ds['occupancy']:.0%}, and N lower by {ds['n_haircut']:.0%}.", "Weeks per year = 52. Projections are illustrative and may be wrong.", f"Conversion period = {conv} weeks (consent {weeks_conv['consent']}, works {weeks_conv['works']}, audit and sign-off {weeks_conv['audit']})."],
            "banner": "Lawyer review required. Illustrative projections from the stated assumptions; no outcome is promised.",
            "legal_flags": "A profit share or JV can change legal, tax, liability, lender and insurer treatment. Questions for a lawyer and an accountant: lease with a profit-share rent, a JV entity, or a management agreement; the operator must be the certified legal entity; the owner's lender and insurer may need to consent. This tool recommends no structure.",
            "flags": flags}

# ----------------------------------------------------------------------------------- sensitivity (Part 3 section 6.3)
def sensitivity(beds: float, p: dict, retrofit: float | None) -> dict:
    """Stabilised weekly net N and walk-away rent under the spec's variations: occupancy +/-10 points, fee +/-10%, wage +/-10%, retrofit +/-20%. None where an input is unset."""
    def run(pp, rc): f = feasibility(beds, pp, rc); return {"N": (f.get("stabilised") or {}).get("net"), "walk_away_rent_per_week": f.get("walk_away_rent_per_week")}
    occ = p.get("stabilised_occupancy"); grid = {"base": run(p, retrofit)}
    if occ is None: return {"needs_input": ["stabilised_occupancy"], "grid": grid}
    for name, pp, rc in (("occupancy_minus_10pts", {**p, "stabilised_occupancy": max(0.0, occ - 0.10)}, retrofit), ("occupancy_plus_10pts", {**p, "stabilised_occupancy": min(1.0, occ + 0.10)}, retrofit),
                         ("fee_minus_10pct", {**p, "fee_per_bed_per_week": (p["fee_per_bed_per_week"] or 0) * 0.9 if p.get("fee_per_bed_per_week") is not None else None}, retrofit),
                         ("fee_plus_10pct", {**p, "fee_per_bed_per_week": (p["fee_per_bed_per_week"] or 0) * 1.1 if p.get("fee_per_bed_per_week") is not None else None}, retrofit),
                         ("wage_minus_10pct", {**p, "staff_wage_per_week": (p["staff_wage_per_week"] or 0) * 0.9 if p.get("staff_wage_per_week") is not None else None}, retrofit),
                         ("wage_plus_10pct", {**p, "staff_wage_per_week": (p["staff_wage_per_week"] or 0) * 1.1 if p.get("staff_wage_per_week") is not None else None}, retrofit),
                         ("retrofit_minus_20pct", p, retrofit * 0.8 if retrofit is not None else None), ("retrofit_plus_20pct", p, retrofit * 1.2 if retrofit is not None else None)):
        grid[name] = run(pp, rc)
    low = run({**p, "stabilised_occupancy": max(0.0, occ - 0.10), "fee_per_bed_per_week": (p["fee_per_bed_per_week"] or 0) * 0.9 if p.get("fee_per_bed_per_week") is not None else None,
               "staff_wage_per_week": (p["staff_wage_per_week"] or 0) * 1.1 if p.get("staff_wage_per_week") is not None else None}, retrofit)["N"]
    high = run({**p, "stabilised_occupancy": min(1.0, occ + 0.10), "fee_per_bed_per_week": (p["fee_per_bed_per_week"] or 0) * 1.1 if p.get("fee_per_bed_per_week") is not None else None,
                "staff_wage_per_week": (p["staff_wage_per_week"] or 0) * 0.9 if p.get("staff_wage_per_week") is not None else None}, retrofit)["N"]
    return {"grid": grid, "N_range": {"low": low, "base": grid["base"]["N"], "high": high},
            "N_range_definition": "low = occupancy -10 points, fee -10%, wage +10% together; high = the opposite. Three-month delay is in the cash plan (add 13 weeks to the timeline)."}
