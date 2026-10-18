"""Dashboard and weekly digest (MASTER_SPEC 8.8): pipeline by stage, human minutes per property by role, cycle time per stage, engineer turnaround, council questions per consent, pack gaps at the completeness check, cash required, beds in the pipeline,
expected opening dates, and the slowest step. Every figure is computed from what has been recorded; where nothing is recorded the figure is null, never a guess. The weekly digest is the dashboard plus the in-app digest, stored; nothing is emailed."""
import json
from collections import Counter
from datetime import date, timedelta
from . import consent_pack, digest, reviews, timeline
from .db import conn

CYCLE_PAIRS = [("lodged", "consent_granted"), ("consent_granted", "works_started"), ("works_started", "works_complete"), ("works_complete", "certified"), ("certified", "first_resident")]

def build() -> dict:
    with conn() as c:
        q = lambda sql, a=(): c.execute(sql, a).fetchall()
        n_screen = {r["beds_tier"]: r["n"] for r in q("SELECT beds_tier, count(*) AS n FROM analytics.rh_screen GROUP BY 1")}
        recs = q("SELECT count(*) AS n FROM core.rh_property")[0]["n"]
        plan_up = q("SELECT count(DISTINCT parcel_id) AS n FROM core.rh_upload WHERE kind='plan'")[0]["n"]
        conf = q("SELECT count(DISTINCT u.parcel_id) AS n FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE x.status='human_confirmed' AND x.superseded_by IS NULL")[0]["n"]
        packs = {r["status"]: r["n"] for r in q("SELECT status, count(*) AS n FROM core.rh_pack WHERE status<>'superseded' GROUP BY 1")}
        ms = q("SELECT parcel_id, key, planned_on, actual_on FROM core.rh_milestone")
        by_role = q("SELECT COALESCE(role,'owner') AS role, sum(minutes)::float AS minutes, count(DISTINCT parcel_id) AS properties FROM core.rh_effort_log GROUP BY 1")
        step_min = q("SELECT step, sum(minutes)::float AS m FROM core.rh_effort_log GROUP BY 1 ORDER BY 2 DESC")
        rfi = q("SELECT count(*) AS rfis, count(DISTINCT pack_id) AS packs FROM core.rh_rfi WHERE pack_id IS NOT NULL")[0]
        lodged = q("SELECT count(*) AS n FROM core.rh_pack WHERE status='lodged'")[0]["n"]
        beds = q("SELECT COALESCE(sum(m),0)::int AS beds FROM (SELECT parcel_id, max(beds) AS m FROM core.rh_layout_option GROUP BY 1) x")[0]["beds"]
        offers = q("SELECT DISTINCT ON (parcel_id) parcel_id, output FROM core.rh_scenario WHERE kind='offer' ORDER BY parcel_id, id DESC")
        pack_ids = [r["id"] for r in q("SELECT id FROM core.rh_pack WHERE status IN ('draft','ready_to_lodge')")]
    # cycle time per stage
    byp = {}
    for r in ms: byp.setdefault(r["parcel_id"], {})[r["key"]] = r["actual_on"]
    cycle = {}
    for a, b in CYCLE_PAIRS:
        d = [(v[b] - v[a]).days for v in byp.values() if v.get(a) and v.get(b)]
        cycle[f"{a}_to_{b}"] = {"n": len(d), "avg_days": round(sum(d) / len(d), 1) if d else None}
    known = {k: v["avg_days"] for k, v in cycle.items() if v["avg_days"] is not None}
    slowest = max(known, key=known.get) if known else (step_min[0]["step"] if step_min else None)
    gaps = Counter()
    for pid in pack_ids:
        for b in consent_pack.completeness(pid)["blockers"]: gaps[b["code"]] += 1
    cash = 0.0; any_cash = False
    for o in offers:
        for mode in (o["output"].get("modes") or {}).values():
            v = ((mode.get("operator") or {}) if isinstance(mode, dict) else {}).get("cash_required")
            if v is not None: cash += v; any_cash = True; break
    opening = [{"parcel_id": p, "first_resident_planned": str(v.get("first_resident"))} for p, v in byp.items() if v.get("first_resident")]
    eng = reviews.metrics(); tot_min = sum(r["minutes"] for r in by_role)
    return {"generated_on": date.today().isoformat(),
            "pipeline": {"screened_candidates_by_tier": n_screen, "property_records": recs, "plan_uploaded": plan_up, "plan_confirmed": conf, "packs_draft": packs.get("draft", 0), "packs_ready_to_lodge": packs.get("ready_to_lodge", 0), "packs_lodged": packs.get("lodged", 0),
                         "certified": sum(1 for v in byp.values() if v.get("certified")), "operating": sum(1 for v in byp.values() if v.get("first_resident"))},
            "human_minutes_by_role": [{**r, "minutes_per_property": round(r["minutes"] / r["properties"], 1) if r["properties"] else None} for r in by_role], "human_minutes_total": round(tot_min, 1),
            "cycle_time_per_stage": cycle, "engineer_turnaround": eng["by_role"], "council_questions": {"rfis": rfi["rfis"], "lodged_packs": lodged, "rfis_per_lodged_pack": round(rfi["rfis"] / lodged, 2) if lodged else None},
            "pack_gaps_at_completeness": dict(gaps), "cash_required_latest_offers": round(cash) if any_cash else None, "beds_in_pipeline": beds, "expected_opening_dates": opening, "slowest_step": slowest,
            "note": "Computed from what you have recorded. Blank means nothing recorded yet."}

def weekly() -> dict:
    d = build(); g = digest.run_and_store(date.today() - timedelta(days=7))
    return {"dashboard": d, "digest": {k: g[k] for k in ("since", "good_new", "price_changes", "due", "source_coverage")}, "note": "Weekly digest in the app; nothing is emailed (outreach is off)."}
