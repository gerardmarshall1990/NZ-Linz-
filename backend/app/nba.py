"""Next Best Action queue (MASTER_SPEC 8.2 level 3): properties whose estimated profit exceeds your threshold and whose data tier is at least DOCUMENTED, ranked by expected profit per human minute, each with exactly what it needs next.
Expected profit = annual profit before rent x the product of your stage probabilities (BLANK until you set them: stage_prob:<stage>); human minutes come from the minutes YOU have logged per step (blank until logged). Until both exist the queue is ordered by profit and says what to set.
The threshold is your minimum acceptable profit per year (blank = no threshold applied, and it says so)."""
from fastapi import HTTPException
from . import settings
from .db import conn

STAGES = ["owner_agrees", "plans_received", "engineers_ok", "consent_ok", "certification_ok"]
ACTION_STEP = {"approve_outreach": "owner_contact", "request_plans": "owner_contact", "review_model": "plan_review", "build_pack": "pack_review", "send_to_engineers": "engineer_coordination", "lodge": "council_liaison", "none": "other"}
NEXT_FOR_STAGE = {"approve_outreach": ["owner_agrees", "plans_received", "engineers_ok", "consent_ok", "certification_ok"], "request_plans": ["plans_received", "engineers_ok", "consent_ok", "certification_ok"], "review_model": ["engineers_ok", "consent_ok", "certification_ok"],
                  "build_pack": ["engineers_ok", "consent_ok", "certification_ok"], "send_to_engineers": ["engineers_ok", "consent_ok", "certification_ok"], "lodge": ["consent_ok", "certification_ok"], "none": []}

def probs() -> dict:
    s = settings.stored(); return {k: s.get(f"stage_prob:{k}") for k in STAGES}

def set_prob(stage: str, p: float | None) -> dict:
    if stage not in STAGES: raise HTTPException(422, f"stage must be one of {STAGES}")
    if p is not None and (isinstance(p, bool) or not 0 <= p <= 1): raise HTTPException(422, "a probability is between 0 and 1")
    with conn() as c:
        if p is None: c.execute("DELETE FROM core.user_setting WHERE key=%s", (f"stage_prob:{stage}",))
        else: settings._put(c, f"stage_prob:{stage}", p)
        c.commit()
    return probs()

def state(c, parcel_id: int) -> tuple[str, str]:
    """-> (next action, why)"""
    if not c.execute("SELECT 1 FROM core.rh_property WHERE parcel_id=%s", (parcel_id,)).fetchone(): return "approve_outreach", "no Property Record yet: approve outreach to the owner or agent to get plans"
    ext = c.execute("SELECT x.status FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id=%s AND x.superseded_by IS NULL ORDER BY x.id DESC LIMIT 1", (parcel_id,)).fetchone()
    if not ext: return "request_plans", "no plan uploaded: send the plan request pack"
    if ext["status"] != "human_confirmed": return "review_model", "plan reading awaits your confirmation (uncertainties highlighted)"
    pk = c.execute("SELECT p.id, p.status FROM core.rh_pack p WHERE p.parcel_id=%s AND p.status<>'superseded' ORDER BY p.id DESC LIMIT 1", (parcel_id,)).fetchone()
    if not pk: return "build_pack", "confirmed plan: generate layout options and the consent pack"
    if pk["status"] == "ready_to_lodge": return "lodge", "pack is ready to lodge: lodge through the portal and record it"
    if pk["status"] == "lodged": return "none", "lodged: waiting on the Council"
    rv = c.execute("SELECT count(*) FILTER (WHERE status IN ('sent','commented')) AS out, count(*) FILTER (WHERE status='returned') AS back, count(*) AS n FROM core.rh_review_package WHERE pack_id=%s", (pk["id"],)).fetchone()
    if rv["n"] == 0 or rv["out"] == 0 and rv["back"] < 4: return "send_to_engineers", "send review packages to the engineers (needs your approval)"
    return "none", "waiting on engineers or professional documents"

def queue(limit: int = 50) -> dict:
    p = settings.assumptions(); thr = p.get("minimum_acceptable_profit_per_year"); pr = probs(); miss = [k for k, v in pr.items() if v is None]
    with conn() as c:
        rows = c.execute("""SELECT parcel_id, address, suburb, beds_base, beds_tier, profit_before_rent_annual::float AS profit, uses_placeholders FROM analytics.rh_screen
                            WHERE beds_tier IN ('DOCUMENTED','CONFIRMED') AND profit_before_rent_annual IS NOT NULL AND (%s::float IS NULL OR profit_before_rent_annual >= %s) ORDER BY profit_before_rent_annual DESC LIMIT %s""", (thr, thr, limit * 4)).fetchall()
        avg = {r["step"]: float(r["a"]) for r in c.execute("SELECT step, avg(minutes) AS a FROM core.rh_effort_log GROUP BY step").fetchall()}
        out = []
        for r in rows:
            act, why = state(c, r["parcel_id"]); stages = NEXT_FOR_STAGE[act]; mins = avg.get(ACTION_STEP[act]) if act != "none" else None
            prob = None if any(pr[s] is None for s in stages) else __import__("math").prod(pr[s] for s in stages)
            exp = None if prob is None else r["profit"] * prob; per_min = None if exp is None or not mins else exp / mins
            out.append({**r, "next_action": act, "why": why, "stage_probability": prob, "expected_profit": exp, "minutes_estimate": mins, "expected_profit_per_human_minute": per_min})
    ranked = all(o["expected_profit_per_human_minute"] is not None for o in out if o["next_action"] != "none") and bool(out)
    out.sort(key=lambda o: -(o["expected_profit_per_human_minute"] if ranked and o["expected_profit_per_human_minute"] is not None else (o["profit"] or 0)))
    return {"queue": out[:limit], "ranked_by": "expected profit per human minute" if ranked else "profit only", "threshold": thr,
            "needs": ([f"set stage probabilities: {', '.join(miss)}"] if miss else []) + (["log some human minutes per step (Track tab) so minutes per action are known"] if not avg else []) + ([] if thr is not None else ["set minimum_acceptable_profit_per_year to apply a profit threshold"]),
            "note": "Only properties at DOCUMENTED tier or better appear. Probabilities and minutes are yours; nothing is assumed."}
