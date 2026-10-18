"""Best Use (MASTER_SPEC Part 9): three options for one parcel side by side. Reuses existing engines; adds none.
(a) rest home conversion of the existing building (layout option, retrofit, rest home economics); (b) development or subdivision (latest development run); (c) new-build rest home (beds from the zone's coverage and height limits, rest home economics).
Rules: natural hazard flags are information only for (a) and change (b) and (c) (they cannot be called best until a geotechnical / hydrology review is recorded); an option with blank key inputs shows 'needs input' and is never ranked;
nothing is labelled best unless all three can be compared, which needs your comparison horizon (years) because (a) and (c) earn annual profit and (b) is one-off; every column carries its lowest confidence tier."""
import json
from fastapi import HTTPException
from . import devrules, devscenarios, economics, retrofit, settings
from .compliance import _facts
from .db import conn
from .facts import get_property
from .layout import list_options
from .tiers import lowest

W = 52

def _hazard(parcel_id: int) -> dict:
    with conn() as c: s = c.execute("SELECT hazard_flags, flood_plain, flood_prone, flood_sensitive, coastal_inundation, landslide_susceptibility, liquefaction_vulnerability, tsunami_zone FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone()
    hz = (s or {}).get("hazard_flags") or []
    flagged = bool(hz) or any((s or {}).get(k) for k in ("flood_plain", "flood_prone", "flood_sensitive", "coastal_inundation", "tsunami_zone"))
    return {"flagged": flagged, "flags": hz}

def _reviewed(parcel_id: int) -> bool:
    with conn() as c: r = c.execute("SELECT value FROM core.user_setting WHERE key=%s", (f"hazard_reviewed:{parcel_id}",)).fetchone()
    return bool(r and r["value"])

def set_hazard_reviewed(parcel_id: int, reviewed: bool) -> dict:
    get_property_or_site(parcel_id)
    with conn() as c: settings._put(c, f"hazard_reviewed:{parcel_id}", bool(reviewed)); c.commit()
    return {"parcel_id": parcel_id, "hazard_reviewed": bool(reviewed)}

def get_property_or_site(parcel_id: int):
    with conn() as c:
        if not c.execute("SELECT 1 FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone(): raise HTTPException(404, "no such parcel")

def _col(name, **kw): return {"option": name, "status": "needs_input", "needs_input": [], "profit": None, "profit_basis": None, "cash_required": None, "timeline_weeks": None, "risks": [], "confidence": None, "unknowns": [], **kw}

def conversion(parcel_id: int) -> dict:
    col = _col("a_conversion", title="Rest home conversion of the existing building", hazard_effect="information only: does not change this option")
    try: rec = get_property(parcel_id)
    except HTTPException: col["needs_input"] = ["a Property Record with a confirmed plan"]; return col
    opts = list_options(parcel_id)
    if not opts: col["needs_input"] = ["a confirmed plan and layout options (Rest Home tab)"]; return col
    o = max(opts, key=lambda x: x["beds"]); p = settings.assumptions(); r = retrofit.cost(o, None, _facts(parcel_id), settings.rates_cfg()); rc = (r["total"] or {}).get("base")
    col["confidence"] = rec["lowest_confidence"] or "ESTIMATED"; col["beds"] = o["beds"]; col["unknowns"] = list(o.get("rules_not_applied") or [])
    f = economics.feasibility(o["beds"], p, rc, col["confidence"]); st = f.get("stabilised") or {}
    if st.get("net") is None or rc is None or (f.get("retrofit_charge") or {}).get("weekly") is None:
        col["needs_input"] = sorted(set((f.get("needs_input") or []) + ([] if rc is not None else ["retrofit rates (config/rates.yaml or My inputs)"]))); return col
    annual = (st["net"] - f["retrofit_charge"]["weekly"]) * W
    cash = None if p.get("pre_opening_costs") is None or p.get("working_capital") is None else rc + p["pre_opening_costs"] + p["working_capital"]
    t = economics.timeline_defaults()["target"]; col.update(status="ok", profit=annual, profit_basis="annual, stabilised, after the retrofit charge, before any rent", cash_required=cash, timeline_weeks=t["consent_weeks"] + t["works_weeks"] + t["audit_signoff_weeks"] + t["fill_weeks"],
                                                                risks=["structure, fire and certification are for professionals", "unit-titled or multiple owners is a deal-breaker flag"], eligible_for_best=True)
    if cash is None: col["unknowns"].append("pre-opening costs or working capital not set: cash required unknown")
    return col

def development(parcel_id: int) -> dict:
    col = _col("b_development", title="Development or subdivision", hazard_effect="counts: flagged hazards need a review before this option can be called best")
    run = devscenarios.latest(parcel_id)
    if not run or run.get("status") != "ok": col["needs_input"] = (run or {}).get("needs_input") or ["run the development feasibility (Develop tab) with unit sizes and finance inputs"]; return col
    fin = run.get("financials") or {}; haz = _hazard(parcel_id); col["confidence"] = "ESTIMATED"; col["unknowns"] = ["rule values not yet confirmed by you", "vehicle access standards not loaded"]
    if fin.get("status") != "ok": col["needs_input"] = fin.get("needs_input", []); return col
    tl = run["inputs"].get("timeline_weeks") or {}; weeks = None if any(v is None for v in tl.values()) else sum(tl.values())
    col.update(status="ok", profit=fin["profit"], profit_basis="one-off, after all costs and selling costs", cash_required=fin["peak_funding_approx"], timeline_weeks=weeks, units=fin["units"],
               risks=["planning outcome for any infringed standard", "servicing capacity unknown until confirmed"] + (["natural hazard flagged: " + ", ".join(map(str, haz["flags"]))] if haz["flagged"] else []))
    if weeks is None: col["unknowns"].append("timeline stages not all set")
    col["hazard_flagged"] = haz["flagged"]; col["eligible_for_best"] = (not haz["flagged"]) or _reviewed(parcel_id)
    return col

def newbuild(parcel_id: int, nb: dict) -> dict:
    col = _col("c_new_build_rest_home", title="New-build rest home", hazard_effect="counts: flagged hazards need a review before this option can be called best")
    need = [k for k in ("gfa_per_bed_m2", "storey_height_m", "build_cost_per_m2") if not nb.get(k)]
    if need: col["needs_input"] = [f"new build: {k}" for k in need]; return col
    with conn() as c: s = c.execute("SELECT zone_name, area_m2::float AS area FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone()
    R = devrules.zone_rules(s["zone_name"]); cov, hmax = R.get("building_coverage_max_pct"), R.get("building_height_max")
    if not cov or not hmax: col["needs_input"] = ["zone coverage and height rules (not loaded for this zone)"]; return col
    storeys = int(hmax["v"] // nb["storey_height_m"]); footprint = s["area"] * cov["v"] / 100; gfa = footprint * storeys; beds = int(gfa // nb["gfa_per_bed_m2"])
    p = settings.assumptions(); build = gfa * nb["build_cost_per_m2"]; haz = _hazard(parcel_id)
    f = economics.feasibility(beds, p, build, "ESTIMATED"); st = f.get("stabilised") or {}
    col.update(confidence="ESTIMATED", beds=beds, unknowns=["coverage used as the footprint (the envelope after yards may allow less)", "storeys from the height limit and your storey height", "rule values not yet confirmed by you"], hazard_flagged=haz["flagged"])
    if st.get("net") is None or (f.get("retrofit_charge") or {}).get("weekly") is None: col["needs_input"] = sorted(set(f.get("needs_input") or [])); return col
    cash = None if p.get("pre_opening_costs") is None or p.get("working_capital") is None else build + p["pre_opening_costs"] + p["working_capital"]
    col.update(status="ok", profit=(st["net"] - f["retrofit_charge"]["weekly"]) * W, profit_basis="annual, stabilised, after the build-cost charge, before any rent", cash_required=cash, timeline_weeks=None,
               risks=["consent, design and certification pathway", "build cost is your input"] + (["natural hazard flagged: " + ", ".join(map(str, haz["flags"]))] if haz["flagged"] else []), eligible_for_best=(not haz["flagged"]) or _reviewed(parcel_id))
    col["unknowns"].append("timeline not modelled for a new build")
    return col

def compare(parcel_id: int, nb: dict | None = None, horizon_years: float | None = None) -> dict:
    get_property_or_site(parcel_id); cols = [conversion(parcel_id), development(parcel_id), newbuild(parcel_id, nb or {})]
    ok = [c for c in cols if c["status"] == "ok"]; reasons = []
    if len(ok) < 3: reasons += [f"{c['title']}: needs input ({'; '.join(c['needs_input'][:3])})" for c in cols if c["status"] != "ok"]
    if horizon_years is None or horizon_years <= 0: reasons.append("a comparison horizon in years is needed: annual and one-off profits are not comparable without one")
    blocked = [c["title"] for c in ok if c.get("eligible_for_best") is False]
    if blocked: reasons.append("natural hazard flagged and not yet reviewed for: " + ", ".join(blocked))
    best = None
    if not reasons:
        for c in cols: c["profit_over_horizon"] = c["profit"] * horizon_years if "annual" in c["profit_basis"] else c["profit"]
        best = max(cols, key=lambda c: c["profit_over_horizon"])["option"]
    return {"parcel_id": parcel_id, "columns": cols, "lowest_confidence": lowest([c["confidence"] for c in cols if c["confidence"]]), "best": best, "best_blocked_because": reasons, "horizon_years": horizon_years,
            "note": "No option is labelled best unless all three can be compared. Profit figures use their stated bases; confidence is the lowest of the inputs. Natural hazard flags do not affect option (a).",
            "label": "Screening comparison. Not advice."}
