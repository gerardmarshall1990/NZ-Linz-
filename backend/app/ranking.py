"""Ranking and what-if sliders (MASTER_SPEC 6.3, 6.4).
Ranking: stabilised annual profit before rent per effort point, and per dollar of cash at risk, shown separately for each confidence tier (never mixed). Effort weights are the owner's editable assumptions (config/effort_weights.yaml, saved over in user_setting).
A property whose economics still need inputs is listed as 'not ranked' with what is missing: it is never given a guessed score."""
import json
from functools import lru_cache
import yaml
from fastapi import HTTPException
from . import economics, retrofit, settings
from .compliance import _facts, run as run_checks
from .config import ROOT
from .db import conn
from .layout import get_option, list_options

@lru_cache
def _defaults() -> dict: return yaml.safe_load((ROOT / "config" / "effort_weights.yaml").read_text())

def weights() -> dict:
    d = json.loads(json.dumps(_defaults())); s = settings.stored().get("effort:weights") or {}
    d["weights"].update({k: v for k, v in s.items() if k in d["weights"]}); return d

def set_weights(values: dict) -> dict:
    base = _defaults()["weights"]; bad = [k for k in values if k not in base]
    if bad: raise HTTPException(422, f"unknown weight(s): {bad}")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 for v in values.values()): raise HTTPException(422, "weights must be non-negative numbers")
    cur = settings.stored().get("effort:weights") or {}
    with conn() as c: settings._put(c, "effort:weights", {**cur, **values}); c.commit()
    return weights()

def _title_key(t):
    t = (t or "").lower()
    if not t: return "unknown"
    if "unit" in t: return "unit_title"
    if "cross" in t: return "cross_lease"
    if "fee simple" in t: return "fee_simple"
    if "freehold" in t: return "freehold"
    return "unknown"

def effort(option: dict, checks: dict, title_type: str | None, w: dict | None = None) -> dict:
    cfg = w or weights(); wt = cfg["weights"]; rooms = [a for lv in option["levels"] for a in lv["rooms"]]
    comp = {"parties": cfg["title_parties_points"][_title_key(title_type)],
            "retrofit_scope": (sum(1 for a in rooms if a["action"] == "convert") + (option.get("new_work_items") or 0)) / 5,
            "consent_complexity": sum(1 for c in checks["checks"] if c["status"] == "FAIL") + 0.5 * len({c["signs_off"] for c in checks["checks"] if c["status"] in ("FAIL", "NEEDS_PROFESSIONAL")}),
            "beds_to_fill": option["beds"] / 10}
    pts = 1 + sum(wt[k] * v for k, v in comp.items())
    return {"points": round(pts, 2), "components": {k: round(v, 2) for k, v in comp.items()}, "weights": wt}

def _latest_checks(parcel_id, option_id):
    with conn() as c: r = c.execute("SELECT results FROM core.rh_check_run WHERE parcel_id=%s AND option_id=%s ORDER BY id DESC LIMIT 1", (parcel_id, option_id)).fetchone()
    return r["results"] if r else run_checks(parcel_id, option_id)

def rank() -> dict:
    p = settings.assumptions(); cfg = settings.rates_cfg(); rows = []
    with conn() as c:
        props = c.execute("SELECT p.parcel_id, s.address, s.suburb, s.title_type FROM core.rh_property p LEFT JOIN core.sites s ON s.parcel_id = p.parcel_id ORDER BY p.parcel_id").fetchall()
    for pr in props:
        opts = list_options(pr["parcel_id"])
        if not opts: continue
        o = max(opts, key=lambda x: x["beds"]); facts = _facts(pr["parcel_id"])
        from .facts import get_property
        tier = get_property(pr["parcel_id"])["lowest_confidence"] or "ESTIMATED"
        r = retrofit.cost(o, None, facts, cfg); rc = (r["total"] or {}).get("base")
        f = economics.feasibility(o["beds"], p, rc, tier); row = {"parcel_id": pr["parcel_id"], "address": pr["address"], "suburb": pr["suburb"], "option_id": o["id"], "scenario": o["scenario"], "beds": o["beds"], "tier": tier,
                                                                  "retrofit_base": rc, "retrofit_needs_rate": r["total"] is None}
        if (f.get("stabilised") or {}).get("net") is None:
            row.update(ranked=False, missing=sorted(set(f["needs_input"]))); rows.append(row); continue
        e = effort(o, _latest_checks(pr["parcel_id"], o["id"]), pr["title_type"]); profit = f["stabilised_annual_profit_before_rent"]
        cash = None if rc is None or p.get("pre_opening_costs") is None or p.get("working_capital") is None else rc + p["pre_opening_costs"] + p["working_capital"]
        row.update(ranked=True, annual_profit_before_rent=round(profit), effort_points=e["points"], effort_components=e["components"], profit_per_effort_point=round(profit / e["points"]),
                   cash_at_risk=cash, profit_per_cash=round(profit / cash, 3) if cash else None, walk_away_rent_per_week=f.get("walk_away_rent_per_week"))
        row.update(settings.banner_for(settings.used_not_decision_grade(settings.OPEX_NEEDED, None)))
        rows.append(row)
    tiers = {}
    for t in ("CONFIRMED", "DOCUMENTED", "ESTIMATED"):
        inn = [r for r in rows if r["tier"] == t]
        tiers[t] = {"by_profit_per_effort_point": sorted([r for r in inn if r["ranked"]], key=lambda r: -r["profit_per_effort_point"]),
                    "by_profit_per_cash": sorted([r for r in inn if r["ranked"] and r["profit_per_cash"] is not None], key=lambda r: -r["profit_per_cash"]),
                    "not_ranked": [r for r in inn if not r["ranked"]]}
    return {"tiers": tiers, "effort_weights": weights()["weights"], "note": "Profit = stabilised annual profit before rent. Tiers are ranked separately and never mixed. Effort weights are your editable assumptions."}

SLIDERS = {"occupancy_pts": (-30, 30), "fee_pct": (-30, 30), "wage_pct": (-30, 30), "retrofit_pct": (-50, 100)}

def whatif(parcel_id: int, option_id: int, occupancy_pts: float = 0, fee_pct: float = 0, wage_pct: float = 0, retrofit_pct: float = 0) -> dict:
    for k, v in (("occupancy_pts", occupancy_pts), ("fee_pct", fee_pct), ("wage_pct", wage_pct), ("retrofit_pct", retrofit_pct)):
        lo, hi = SLIDERS[k]
        if not lo <= v <= hi: raise HTTPException(422, f"{k} must be between {lo} and {hi}")
    o = get_option(option_id)
    if o["parcel_id"] != parcel_id: raise HTTPException(404, "option belongs to another property")
    p = settings.assumptions(); r = retrofit.cost(o, None, _facts(parcel_id), settings.rates_cfg()); rc = (r["total"] or {}).get("base")
    base = economics.feasibility(o["beds"], p, rc)
    q = dict(p)
    if p.get("stabilised_occupancy") is not None: q["stabilised_occupancy"] = min(1.0, max(0.0, p["stabilised_occupancy"] + occupancy_pts / 100))
    for key, pct in (("fee_per_bed_per_week", fee_pct), ("staff_wage_per_week", wage_pct)):
        if p.get(key) is not None: q[key] = p[key] * (1 + pct / 100)
    rc2 = rc * (1 + retrofit_pct / 100) if rc is not None else None
    new = economics.feasibility(o["beds"], q, rc2)
    pick = lambda f: {"annual_profit_before_rent": f.get("stabilised_annual_profit_before_rent"), "walk_away_rent_per_week": f.get("walk_away_rent_per_week"), "break_even_occupancy": (f.get("break_even_occupancy") or {}).get("profit_zero")}
    b, n = pick(base), pick(new)
    delta = {k: (None if b[k] is None or n[k] is None else n[k] - b[k]) for k in ("annual_profit_before_rent", "walk_away_rent_per_week")}
    out = {"option_id": option_id, "sliders": {"occupancy_pts": occupancy_pts, "fee_pct": fee_pct, "wage_pct": wage_pct, "retrofit_pct": retrofit_pct}, "base": b, "what_if": n, "change": delta,
           "needs_input": sorted(set(new["needs_input"])), "retrofit_base_used": rc, "label": "Illustrative what-if from your assumptions. Not saved. A three-month delay is tested in the Offer Builder timeline, not here."}
    out.update(settings.banner_for(settings.used_not_decision_grade(settings.OPEX_NEEDED, None)))
    return out
