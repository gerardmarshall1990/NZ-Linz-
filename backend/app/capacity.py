"""Capacity planner (MASTER_SPEC 8.7): rolls out N homes through engineer review, lodgement admin, Council processing, builder starts, works, auditor slots and hiring, week by week, orders them for the fastest cash-positive opening, draws the monthly cash curve and names the BINDING CONSTRAINT
(the resource whose queueing cost the portfolio the most weeks). Every capacity is YOUR input (blank = that resource is not modelled and is listed under 'not modelled', never assumed unlimited silently). Cash and per-home economics come from the portfolio engine.
At scale the limits are usually staffing, cash and certification per site, not the consent paperwork: the plan says so."""
import math
from fastapi import HTTPException
from . import economics as E, portfolio, settings, timeline

RESOURCES = {"engineer_reviews_per_week": "engineer review capacity", "lodgement_admin_hours_per_week": "lodgement admin capacity", "builder_starts_per_month": "builder start capacity", "auditor_audits_per_month": "auditor availability",
             "manager_hires_per_month": "hiring (managers and clinical leads)", "care_staff_hires_per_month": "hiring (care staff)"}
M = E.W / 12

def plan(homes: list[dict], caps: dict, overrides: dict | None = None, horizon_weeks: int = 156, opening_target: str | None = None) -> dict:
    p = settings.assumptions(); p.update(overrides or {})
    need = portfolio._needs(p, {"cash_limit_dollars": caps.get("cash_limit_dollars")})
    if need or not homes: return {"status": "needs_input", "needs_input": need or ["at least one home"], "label": "Needs input."}
    if any(h.get("retrofit") is None for h in homes): return {"status": "needs_input", "needs_input": ["retrofit cost for every home"], "label": "Needs input."}
    tl = timeline.weeks_for("target"); consent_w, works_w, audit_w = tl["consent_weeks"], tl["works_weeks"], tl["audit_weeks"]
    per = [portfolio.home_economics(h["beds"], h["retrofit"], p) for h in homes]; cert = caps.get("certification_cost_per_site") or 0
    order = sorted(range(len(homes)), key=lambda i: -((per[i]["net_week"]) * E.W / (homes[i]["retrofit"] + p["pre_opening_costs"] + p["working_capital"] + cert)))
    wk = E.W / 12
    rate = {"engineer_reviews_per_week": caps.get("engineer_reviews_per_week") or 0,
            "lodgement_admin_hours_per_week": ((caps.get("lodgement_admin_hours_per_week") or 0) / caps["lodgement_hours_per_pack"]) if caps.get("lodgement_hours_per_pack") else 0,
            "builder_starts_per_month": (caps.get("builder_starts_per_month") or 0) / wk, "auditor_audits_per_month": (caps.get("auditor_audits_per_month") or 0) / wk,
            "manager_hires_per_month": (caps.get("manager_hires_per_month") or 0) / wk, "care_staff_hires_per_month": (caps.get("care_staff_hires_per_month") or 0) / wk}
    modelled = [k for k in RESOURCES if rate[k] > 0]; not_modelled = [RESOURCES[k] for k in RESOURCES if rate[k] <= 0]
    cap_credit = {k: max(1.0, rate[k] * wk) for k in RESOURCES}            # unused capacity banks for at most a month
    credit = {k: 0.0 for k in RESOURCES}
    stage = {i: {"state": "waiting_review"} for i in range(len(homes))}; sched = {i: {} for i in range(len(homes))}; wait = {k: 0.0 for k in list(RESOURCES) + ["cash"]}
    cash = float(caps["cash_limit_dollars"]); start_cash = cash; monthly = []; open_since = {}
    def take(k):
        if k not in modelled: return True
        if credit[k] >= 1 - 1e-9: credit[k] -= 1; return True
        wait[k] += 1; return False
    for w in range(horizon_weeks):
        for k in credit: credit[k] = min(cap_credit[k] if k not in ("manager_hires_per_month", "care_staff_hires_per_month") else max(cap_credit[k], 50.0), credit[k] + rate[k])
        for i in order:
            s = stage[i]; st = s["state"]
            if st == "waiting_review":
                if take("engineer_reviews_per_week"): sched[i]["review_week"] = w; s["state"] = "waiting_lodgement"
            elif st == "waiting_lodgement":
                if take("lodgement_admin_hours_per_week"): sched[i]["lodged_week"] = w; s["state"] = "in_consent"; s["until"] = w + consent_w
            elif st == "in_consent":
                if w >= s["until"]: s["state"] = "waiting_start"; sched[i]["consent_week"] = w
            elif st == "waiting_start":
                need_cash = homes[i]["retrofit"] + p["pre_opening_costs"] + cert; mgr, care = 2, per[i]["staff_positions"]
                if need_cash > cash: wait["cash"] += 1; continue
                if "manager_hires_per_month" in modelled and credit["manager_hires_per_month"] < mgr - 1e-9: wait["manager_hires_per_month"] += 1; continue
                if "care_staff_hires_per_month" in modelled and credit["care_staff_hires_per_month"] < care - 1e-9: wait["care_staff_hires_per_month"] += 1; continue
                if not take("builder_starts_per_month"): continue
                if "manager_hires_per_month" in modelled: credit["manager_hires_per_month"] -= mgr
                if "care_staff_hires_per_month" in modelled: credit["care_staff_hires_per_month"] -= care
                cash -= need_cash; sched[i]["works_start_week"] = w; s["state"] = "works"; s["until"] = w + works_w
            elif st == "works":
                if w >= s["until"]: s["state"] = "waiting_audit"; sched[i]["works_end_week"] = w
            elif st == "waiting_audit":
                if take("auditor_audits_per_month"): sched[i]["audit_week"] = w; s["state"] = "audit"; s["until"] = w + audit_w
            elif st == "audit":
                if w >= s["until"]:
                    if p["working_capital"] > cash: wait["cash"] += 1; continue
                    cash -= p["working_capital"]; s["state"] = "open"; sched[i]["open_week"] = w; open_since[i] = w
        for i, ow in open_since.items(): cash += E.operating(homes[i]["beds"], portfolio.occ_at(p, int((w - ow) / wk)), p)["net"]
        if w % 4 == 3: monthly.append(round(cash))
    opened = [i for i in range(len(homes)) if "open_week" in sched[i]]
    binding = max(wait, key=wait.get) if any(wait.values()) else None
    label = {**RESOURCES, "cash": "cash limit"}
    return {"status": "ok", "homes": len(homes), "opened_within_horizon": len(opened), "schedule": [{"parcel_id": homes[i]["parcel_id"], "address": homes[i].get("address"), **sched[i]} for i in order], "cash_curve_by_4_weeks": monthly, "lowest_cash": min(monthly) if monthly else None,
            "binding_constraint": None if binding is None else {"key": binding, "name": label[binding], "blocked_home_weeks": round(wait[binding], 1), "all": {label[k]: round(v, 1) for k, v in wait.items() if v}},
            "not_modelled": not_modelled, "weeks_modelled": horizon_weeks, "starting_cash": start_cash, "readiness": readiness(opening_target),
            "note": "At scale the limits are usually staffing, cash and certification per site, not the consent paperwork. Resources you left blank are not modelled (listed above), so the binding constraint can only be one you entered.",
            "label": "Illustrative simulation from your inputs. Not advice."}

def readiness(opening: str | None) -> list[dict]:
    from datetime import date, timedelta
    tracks = timeline.tracks_cfg(); od = date.fromisoformat(opening) if opening else None; items = ["legal entity and certification steps", "manager", "clinical lead", "staff roster", "policies", "waitlist", "supplies"]
    out = []
    for key, t in tracks.items():
        out.append({"track": t["title"], "lead_weeks": t["lead_weeks"], "start_date": (od - timedelta(weeks=t["lead_weeks"])).isoformat() if od and t["lead_weeks"] is not None else None, "note": None if t["lead_weeks"] is not None else "set lead time"})
    return [{"checklist": items, "tracks": out}]
