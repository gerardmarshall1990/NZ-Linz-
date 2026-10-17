"""Glue: layout option + Property Record + assumptions -> feasibility, retrofit cost, offer modes. Stores every run in core.rh_scenario so the owner can see the history."""
import json
from fastapi import HTTPException
from . import economics, retrofit, settings
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
    tl = body.get("timeline") or {"consent_weeks": t["consent_weeks"], "works_weeks": t["works_weeks"], "audit_weeks": t["audit_signoff_weeks"]}
    N = sens["N_range"]
    inp = {"asking_rent": body["asking_rent"], "current_net": body.get("current_net"), "N": N, "N_fn": lambda occ: economics.operating(o["beds"], occ, p)["net"], "stabilised_occupancy": p["stabilised_occupancy"],
           "retrofit": rt_range, "allowance_pct": alloc, "timeline": tl, "fill_ramp_by_month": p["fill_ramp_by_month"], "pre_opening_costs": p["pre_opening_costs"], "working_capital": p["working_capital"],
           "funding": "i_fund" if p["retrofit_funding_mode"] == "i_fund" else "owner_funds", "walk_away_rent": feas["walk_away_rent_per_week"], "cash_limit": p["cash_limit"],
           "terms": body.get("terms") or {}, "confidence": {"N": conf, "C": conf}, "downside": body.get("downside")}
    out = economics.run_offer(inp)
    out.update(option_id=option_id, beds=o["beds"], below_target=o["below_target"], walk_away_rent_per_week=feas["walk_away_rent_per_week"], needs_input_feasibility=feas["needs_input"],
               banner_confidence="Screening only: bedrooms/plans not confirmed" if conf in (None, "ESTIMATED") else None)
    out["scenario_id"] = _store(parcel_id, option_id, "offer", {k: v for k, v in inp.items() if k != "N_fn"} | {"assumptions": p}, out, conf)
    return out
