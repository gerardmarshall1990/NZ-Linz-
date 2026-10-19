"""Glue: layout option + Property Record + assumptions -> feasibility, retrofit cost, offer modes. Stores every run in core.rh_scenario so the owner can see the history."""
import json
from fastapi import HTTPException
from . import economics, retrofit, settings, timeline
from .compliance import _facts, run as run_checks
from .db import conn
from .facts import get_property
from .layout import get_option

def _store(parcel_id, option_id, kind, inputs, output, confidence):
    with conn() as c:
        r = c.execute("INSERT INTO core.rh_scenario (parcel_id, option_id, kind, inputs, output, confidence, created_by) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,'owner') RETURNING id, created_at",
                      (parcel_id, option_id, kind, json.dumps(inputs, default=str), json.dumps(output, default=str), confidence)).fetchone(); c.commit()
    return r["id"]

def _option(parcel_id, option_id):
    o = get_option(option_id)
    if o["parcel_id"] != parcel_id: raise HTTPException(404, "option belongs to another property")
    return o

def assumptions(overrides: dict | None) -> dict:
    bad = [k for k in (overrides or {}) if k not in economics.default_assumptions()]
    if bad: raise HTTPException(422, f"unknown assumption(s): {bad}")
    return {**settings.assumptions(), **(overrides or {})}

def retrofit_cost(parcel_id: int, option_id: int, rate_cfg: dict | None = None) -> dict:
    o = _option(parcel_id, option_id); checks = run_checks(parcel_id, option_id); facts = _facts(parcel_id)
    out = retrofit.cost(o, checks, facts, rate_cfg or settings.rates_cfg()); out["scenario_id"] = _store(parcel_id, option_id, "retrofit", {"option_id": option_id}, out, get_property(parcel_id)["lowest_confidence"])
    return out

def economics_run(parcel_id: int, option_id: int, overrides: dict | None, retrofit_total: float | None = None) -> dict:
    o = _option(parcel_id, option_id); p = assumptions(overrides); conf = get_property(parcel_id)["lowest_confidence"]
    rc = retrofit_total
    if rc is None:
        r = retrofit.cost(o, None, _facts(parcel_id), settings.rates_cfg()); rc = (r["total"] or {}).get("base")
    f = economics.feasibility(o["beds"], p, rc, conf); f["sensitivity"] = economics.sensitivity(o["beds"], p, rc)
    f.update(option_id=option_id, scenario=o["scenario"], beds=o["beds"], retrofit_cost_used=rc, below_target=o["below_target"], rules_not_applied=o["rules_not_applied"],
             note_beds="Beds come from the layout option; regulatory bed rules not yet applied (see rules_not_applied).")
    f.update(settings.banner_for(settings.used_not_decision_grade(settings.OPEX_NEEDED, overrides) if f.get("stabilised") else []))
    f["scenario_id"] = _store(parcel_id, option_id, "economics", {"assumptions": p, "retrofit": rc}, f, conf)
    return f

def offer_run(parcel_id: int, option_id: int, body: dict) -> dict:
    o = _option(parcel_id, option_id); p = assumptions(body.get("assumptions")); conf = get_property(parcel_id)["lowest_confidence"]
    rt = body.get("retrofit")                                   # {low, base, high} or a number
    if rt is None:
        r = retrofit.cost(o, None, _facts(parcel_id), settings.rates_cfg())
        if r["total"] is None: rt_range, alloc = None, None
        else: rt_range, alloc = r["total"], r["allowance_share_pct"]
    else: rt_range, alloc = ({"low": rt, "base": rt, "high": rt} if not isinstance(rt, dict) else rt), body.get("allowance_pct")
    if rt_range is None:
        return {"needs_input": ["retrofit cost (fill config/rates.yaml with QS rates, or supply a retrofit figure)"], "modes": {}, "label": "Needs input: no offer maths is shown without a retrofit cost."}
    feas = economics.feasibility(o["beds"], p, rt_range["base"], conf); sens = economics.sensitivity(o["beds"], p, rt_range["base"])
    if feas.get("stabilised") is None or feas["stabilised"]["net"] is None:
        return {"needs_input": feas["needs_input"], "modes": {}, "label": "Needs input: the operating model has unset inputs, so no net operating profit is available."}
    t = economics.timeline_defaults()["target"]
    tl = body.get("timeline") or ({k: v for k, v in timeline.weeks_for(body["timeline_scenario"]).items() if k != "fill_weeks"} if body.get("timeline_scenario") else {"consent_weeks": t["consent_weeks"], "works_weeks": t["works_weeks"], "audit_weeks": t["audit_signoff_weeks"]})
    N = sens["N_range"]
    inp = {"asking_rent": body["asking_rent"], "current_net": body.get("current_net"), "N": N, "N_fn": lambda occ: economics.operating(o["beds"], occ, p)["net"], "stabilised_occupancy": p["stabilised_occupancy"],
           "retrofit": rt_range, "allowance_pct": alloc, "timeline": tl, "fill_ramp_by_month": p["fill_ramp_by_month"], "pre_opening_costs": p["pre_opening_costs"], "working_capital": p["working_capital"],
           "funding": "i_fund" if p["retrofit_funding_mode"] == "i_fund" else "owner_funds", "walk_away_rent": feas["walk_away_rent_per_week"], "cash_limit": p["cash_limit"],
           "terms": body.get("terms") or {}, "confidence": {"N": conf, "C": conf}, "downside": body.get("downside")}
    out = economics.run_offer(inp)
    out.update(option_id=option_id, beds=o["beds"], below_target=o["below_target"], walk_away_rent_per_week=feas["walk_away_rent_per_week"], needs_input_feasibility=feas["needs_input"],
               banner_confidence="Screening only: bedrooms/plans not confirmed" if conf in (None, "ESTIMATED") else None)
    out.update(settings.banner_for(settings.used_not_decision_grade(settings.OFFER_NEEDED, body.get("assumptions"))))
    out["scenario_id"] = _store(parcel_id, option_id, "offer", {k: v for k, v in inp.items() if k != "N_fn"} | {"assumptions": p}, out, conf)
    return out


def offer_for_listing(listing_id: int, body: dict) -> dict:
    """Offer Builder for a listing with no plans yet (screening tier): beds = listed bedrooms (an upper bound), retrofit = beds x your screening retrofit cost per bed with a +/-20% range,
    all of it an allowance (so the 'mostly allowances' banner shows), rent = the listing's asking rent."""
    with conn() as c:
        l = c.execute("SELECT * FROM core.user_listing WHERE id = %s", (listing_id,)).fetchone()
        if not l: raise HTTPException(404, "no such listing")
        tier = c.execute("SELECT confidence FROM core.rh_property_fact WHERE parcel_id = %s AND field = 'bedrooms_total'", (l["parcel_id"],)).fetchone() if l["parcel_id"] else None
    if l["parcel_id"] is None or l["match_confidence"] in ("low", "none"): return {"needs_input": ["address matched to a parcel (review the match in Import)"], "modes": {}, "label": "Needs input."}
    if not l["bedrooms"]: return {"needs_input": ["bedrooms"], "modes": {}, "label": "Needs input."}
    rent = body.get("asking_rent") or (float(l["rent_per_week"]) if l["rent_per_week"] else None)
    if not rent: return {"needs_input": ["asking_rent"], "modes": {}, "label": "Needs input."}
    p = assumptions(body.get("assumptions")); beds = int(l["bedrooms"]); conf = (tier or {}).get("confidence", "DOCUMENTED")
    per = p.get("retrofit_cost_per_bed_screening")
    if body.get("retrofit") is None and per is None: return {"needs_input": ["retrofit_cost_per_bed_screening (or give a retrofit figure)"], "modes": {}, "label": "Needs input: no retrofit cost."}
    base = float(body["retrofit"]) if body.get("retrofit") is not None else beds * per
    rt = {"low": base * 0.8, "base": base, "high": base * 1.2}
    feas = economics.feasibility(beds, p, base, conf)
    if feas.get("stabilised") is None or feas["stabilised"]["net"] is None: return {"needs_input": feas["needs_input"], "modes": {}, "label": "Needs input: the operating model has unset inputs."}
    sens = economics.sensitivity(beds, p, base); t = economics.timeline_defaults()["target"]
    tl = body.get("timeline") or {"consent_weeks": t["consent_weeks"], "works_weeks": t["works_weeks"], "audit_weeks": t["audit_signoff_weeks"]}
    inp = {"asking_rent": rent, "current_net": body.get("current_net"), "N": sens["N_range"], "N_fn": lambda occ: economics.operating(beds, occ, p)["net"], "stabilised_occupancy": p["stabilised_occupancy"],
           "retrofit": rt, "allowance_pct": 100.0, "timeline": tl, "fill_ramp_by_month": p["fill_ramp_by_month"], "pre_opening_costs": p["pre_opening_costs"], "working_capital": p["working_capital"],
           "funding": "i_fund" if p["retrofit_funding_mode"] == "i_fund" else "owner_funds", "walk_away_rent": feas["walk_away_rent_per_week"], "cash_limit": p["cash_limit"],
           "terms": body.get("terms") or {}, "confidence": {"N": conf, "C": conf}, "downside": body.get("downside")}
    out = economics.run_offer(inp)
    out.update(listing_id=listing_id, beds=beds, below_target=beds < 50, walk_away_rent_per_week=feas["walk_away_rent_per_week"], needs_input_feasibility=feas["needs_input"],
               basis="screening: beds = listed bedrooms (upper bound), retrofit = beds x screening cost per bed, entirely an allowance", banner_confidence="Screening only: bedrooms/plans not confirmed")
    out.update(settings.banner_for(settings.used_not_decision_grade(settings.OFFER_NEEDED, body.get("assumptions"))))
    with conn() as c:
        c.execute("INSERT INTO core.rh_property (parcel_id, created_by) VALUES (%s, 'listing') ON CONFLICT DO NOTHING", (l["parcel_id"],))      # the scenario belongs to a Property Record; creating an empty one changes no fact
        r = c.execute("INSERT INTO core.rh_scenario (parcel_id, option_id, kind, inputs, output, confidence, created_by) VALUES (%s,NULL,'offer',%s::jsonb,%s::jsonb,%s,'owner') RETURNING id",
                      (l["parcel_id"], json.dumps({k: v for k, v in inp.items() if k != "N_fn"} | {"assumptions": p, "listing_id": listing_id}, default=str), json.dumps(out, default=str), conf)).fetchone(); c.commit()
    out["scenario_id"] = r["id"]; return out


SCALED_PER_30_BEDS = ["cook_cleaner_laundry_per_week", "utilities_per_week", "insurance_per_year", "repairs_maintenance_per_year", "compliance_and_certification_per_year",
                      "minimum_acceptable_profit_per_year", "target_profit_per_year"]

def quick_offer_for_listing(listing_id: int, body: dict) -> dict:
    """Simple view: current rent in, net revenue out, what you could offer. Uses the same operating model as the Offer Builder, but the saved figures sized for a ~30-bed home
    (whole-home running costs and the profit floor) are scaled by beds/30, so a small home is not charged a big home's costs. Placeholders stay flagged."""
    with conn() as c:
        l = c.execute("SELECT * FROM core.user_listing WHERE id = %s", (listing_id,)).fetchone()
    if not l: raise HTTPException(404, "no such listing")
    beds = int(body.get("beds") or l["bedrooms"] or 0); cur = body.get("current_rent") or (float(l["rent_per_week"]) if l["rent_per_week"] else None)
    if not beds: return {"needs_input": ["bedrooms"]}
    if not cur: return {"needs_input": ["current_rent"]}
    p = assumptions(body.get("assumptions")); ov = {k: body[k] for k in ("fee_per_bed_per_week", "stabilised_occupancy") if body.get(k) is not None}; p = {**p, **ov}
    scale = min(beds / 30.0, 1.0)
    for k in SCALED_PER_30_BEDS:
        if p.get(k) is not None and k not in (body.get("assumptions") or {}): p[k] = p[k] * scale
    per = p.get("retrofit_cost_per_bed_screening"); retro = float(body["retrofit"]) if body.get("retrofit") is not None else (beds * per if per is not None else None)
    op = economics.operating(beds, p["stabilised_occupancy"], p) if p.get("stabilised_occupancy") is not None else {"needs_input": ["stabilised_occupancy"], "net": None}
    if op["net"] is None: return {"needs_input": op["needs_input"]}
    ch = economics.retrofit_charge_weekly(retro, p)
    if ch["weekly"] is None: return {"needs_input": ch["needs_input"]}
    floor = (p.get("minimum_acceptable_profit_per_year") or 0.0) / economics.W
    most = op["net"] - ch["weekly"] - floor
    costs = op["food"] + op["staffing"] + op["supplies"] + op["fixed_other"]
    offers = [{"multiple": m, "rent": cur * m, "my_net_per_week": op["net"] - ch["weekly"] - cur * m, "affordable": cur * m <= most} for m in (1.0, 1.1, 1.25, 1.5)]
    out = {"beds": beds, "current_rent": cur, "occupancy": op["occupancy"], "revenue": op["revenue"], "running_costs": costs, "cost_lines": {"Staff": op["staffing"], "Food": op["food"], "Supplies": op["supplies"], "Cook, cleaner, laundry": p["cook_cleaner_laundry_per_week"], "Everything else (managers, utilities, insurance, repairs, audits)": op["fixed_other"] - p["cook_cleaner_laundry_per_week"]}, "net_before_rent": op["net"], "retrofit_charge": ch["weekly"],
           "my_minimum_profit_per_week": floor, "most_you_could_pay": most, "most_as_multiple_of_current": most / cur if cur else None, "offers": offers, "scaled_by_beds_over_30": scale,
           "label": "Illustrative, from your saved assumptions (whole-home costs and the profit floor scaled to the number of beds). A quantity surveyor and an accountant must confirm. Not advice."}
    out.update(settings.banner_for(settings.used_not_decision_grade(settings.OFFER_NEEDED, body.get("assumptions"))))
    return out
