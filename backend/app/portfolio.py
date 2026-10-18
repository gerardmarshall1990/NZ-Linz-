"""House-scale and portfolio economics (MASTER_SPEC Part 4 section 3). Pure functions over the economics engine; every input is yours (blank = 'needs input', never a number).
- Shared staff: one manager and one clinical lead may cover N homes (your ratio); the saving is the cost of the managers and clinical leads you no longer need.
- Certification: a provider certifies per service/site. Multi-site certificates are NOT assumed and costs are NOT shared: `certification_cost_per_site` is your input, charged to each home, and how multiple homes are certified is a NEEDS_PROFESSIONAL item to confirm with HealthCERT or a designated auditing agency.
- Roll-out: homes open in order of profit per dollar of cash needed, when your cash limit and staffing limit allow; the monthly cash curve starts with your cash limit and includes retrofit, pre-opening, certification, working capital and each home's profit while it fills."""
import math
from fastapi import HTTPException
from . import economics as E, settings, timeline
from .db import conn

W = E.W; M = W / 12

def _needs(p: dict, extra: dict) -> list[str]:
    n = E.missing(p, E.OPEX_KEYS) + E.missing(p, ["stabilised_occupancy", "pre_opening_costs", "working_capital", "lease_term_years", "cost_of_capital_pct"])
    if not p.get("fill_ramp_by_month"): n.append("fill_ramp_by_month")
    n += [k for k in ("cash_limit_dollars",) if extra.get(k) is None]
    return sorted(set(n))

def homes_from_screen(parcel_ids: list[int]) -> list[dict]:
    with conn() as c: rows = c.execute("SELECT parcel_id, address, beds_base, beds_tier, retrofit_est FROM analytics.rh_screen WHERE parcel_id = ANY(%s)", (parcel_ids,)).fetchall()
    got = {r["parcel_id"]: r for r in rows}; miss = [i for i in parcel_ids if i not in got]
    if miss: raise HTTPException(404, f"not in the screening table: {miss[:5]}")
    return [{"parcel_id": r["parcel_id"], "address": r["address"], "beds": r["beds_base"], "tier": r["beds_tier"], "retrofit": float(r["retrofit_est"]) if r["retrofit_est"] is not None else None} for i in parcel_ids for r in [got[i]]]

def home_economics(beds: int, retrofit: float | None, p: dict, occ: float | None = None) -> dict:
    occ = p["stabilised_occupancy"] if occ is None else occ; op = E.operating(beds, occ, p); ch = E.retrofit_charge_weekly(retrofit, p)
    return {"net_week": op["net"], "staff_positions": beds / 8 * p["staff_positions_per_8_beds"] * p["roster_coverage_multiplier"], "revenue_week": op["revenue"], "retrofit_charge_week": ch["weekly"], "fixed_other_week": op["fixed_other"]}

def occ_at(p: dict, m: int) -> float:
    r = p["fill_ramp_by_month"]; return r[m] if m < len(r) else p["stabilised_occupancy"]

def evaluate(homes: list[dict], overrides: dict | None = None, extra: dict | None = None) -> dict:
    p = settings.assumptions(); p.update(overrides or {}); extra = extra or {}
    need = _needs(p, extra)
    if need or not homes: return {"status": "needs_input", "needs_input": need or ["at least one home"], "label": "Needs input: no portfolio figure is shown with blank inputs."}
    if any(h.get("retrofit") is None for h in homes): return {"status": "needs_input", "needs_input": ["retrofit cost for every home (screening cost per bed in My inputs, or rates)"], "label": "Needs input."}
    n = len(homes); ratio = extra.get("homes_per_manager") or 1; cert = extra.get("certification_cost_per_site"); shared_unit = p["clinical_lead_cost_per_week"] + p["manager_cost_per_week"]
    per = [home_economics(h["beds"], h["retrofit"], p) for h in homes]; leads = math.ceil(n / ratio); saving_w = shared_unit * (n - leads)
    if any(x["retrofit_charge_week"] is None for x in per): return {"status": "needs_input", "needs_input": ["lease_term_years / cost_of_capital_pct"], "label": "Needs input."}
    net_w = sum(x["net_week"] for x in per) + saving_w; charge_w = sum(x["retrofit_charge_week"] for x in per); rev_w = sum(x["revenue_week"] for x in per)
    tl = timeline.weeks_for("target"); build_months = math.ceil((tl["consent_weeks"] + tl["works_weeks"] + tl["audit_weeks"]) / (W / 12))
    order = sorted(range(n), key=lambda i: -((per[i]["net_week"] - per[i]["retrofit_charge_week"]) * W / (homes[i]["retrofit"] + p["pre_opening_costs"] + p["working_capital"] + (cert or 0))))
    cash = float(extra["cash_limit_dollars"]); staff_limit = extra.get("staff_positions_limit"); horizon = int(extra.get("horizon_months", 36)); curve = []; opened = {}; building = {}; staff_used = 0.0; peak_draw = 0.0; start_cash = cash
    pending = list(order)
    for m in range(horizon):
        for i in list(building):
            if m >= building[i]["open"]: opened[i] = m; del building[i]
        # start a home when the cash for it (retrofit + pre-opening + certification + working capital) is available and staffing allows
        for i in list(pending):
            need_cash = homes[i]["retrofit"] + p["pre_opening_costs"] + p["working_capital"] + (cert or 0)
            if need_cash <= cash and (staff_limit is None or staff_used + per[i]["staff_positions"] <= staff_limit + 1e-9):
                cash -= need_cash; staff_used += per[i]["staff_positions"]; building[i] = {"open": m + build_months}; pending.remove(i)
        inflow = 0.0
        for i, om in opened.items(): inflow += E.operating(homes[i]["beds"], occ_at(p, m - om), p)["net"] * M      # retrofit was paid up front, so no retrofit charge here
        inflow += saving_w * M * (1 if opened else 0)
        cash += inflow; curve.append(round(cash)); peak_draw = max(peak_draw, start_cash - cash)
    roles = {"care_staff_positions": round(sum(x["staff_positions"] for x in per), 1), "managers": leads, "clinical_leads": leads, "cook_cleaner_laundry": f"cost only ({n} home(s)): headcount not specified"}
    return {"status": "ok", "homes": n, "beds": sum(h["beds"] for h in homes), "tiers": sorted({h["tier"] for h in homes if h.get("tier")}), "revenue_per_year": rev_w * W, "net_operating_profit_per_year": net_w * W, "profit_after_retrofit_charge_per_year": (net_w - charge_w) * W,
            "shared_staff_saving_per_year": saving_w * W, "retrofit_total": sum(h["retrofit"] for h in homes), "certification_cost_total": (cert or 0) * n if cert is not None else None, "staff_to_hire": roles,
            "timeline_stagger": [{"parcel_id": homes[i]["parcel_id"], "address": homes[i].get("address"), "opens_in_month": (building.get(i) or {}).get("open", opened.get(i)), "status": "opened" if i in opened else ("building" if i in building else "not started within horizon")} for i in order],
            "cash_curve_by_month": curve, "lowest_cash": min(curve), "peak_cash_drawn": round(peak_draw), "months_modelled": horizon, "build_months": build_months,
            "sensitivity_fill_minus_10pts": _fill_sens(homes, p, extra), "needs_professional": ["How multiple homes are certified (per service or site, and whether any cost is shared) must be confirmed with HealthCERT or a designated auditing agency: nothing is assumed."],
            "assumptions": ["Retrofit, pre-opening, certification and working capital are paid up front when a home starts; homes open after consent, works and audit weeks from the target timeline", "Profit while filling follows your fill ramp", "Beds are the screening estimates unless confirmed"],
            "label": "Illustrative projection from your inputs. A QS and an accountant must confirm. Not advice."}

def _fill_sens(homes, p, extra) -> dict:
    q = {**p, "stabilised_occupancy": max(0.0, p["stabilised_occupancy"] - 0.10)}; net = sum(home_economics(h["beds"], h["retrofit"], q)["net_week"] for h in homes) + (q["clinical_lead_cost_per_week"] + q["manager_cost_per_week"]) * (len(homes) - math.ceil(len(homes) / (extra.get("homes_per_manager") or 1)))
    base = sum(home_economics(h["beds"], h["retrofit"], p)["net_week"] for h in homes) + (p["clinical_lead_cost_per_week"] + p["manager_cost_per_week"]) * (len(homes) - math.ceil(len(homes) / (extra.get("homes_per_manager") or 1)))
    return {"net_operating_profit_per_year": net * W, "change": (net - base) * W}
