"""Timeline and parallel tracks (MASTER_SPEC Part 3 section 7), milestones, and the human-minutes metrics log.
Scenarios: `target` (config/timeline_defaults.yaml), `delay` (target plus 13 weeks on consent: the spec's three-month delay test), `contract` (total months only: the phase split is not specified, so it cannot feed the Offer Builder).
`can_hit_target` is true only when every condition is known and light; unknown conditions give 'unknown' with what to find out. Lead times of the parallel tracks are blank until you set them."""
import json
from datetime import date, timedelta
import yaml
from fastapi import HTTPException
from . import economics, settings
from .compliance import _facts
from .config import ROOT
from .db import conn
from .facts import get_property

DELAY_WEEKS = 13

def tracks_cfg() -> dict:
    t = yaml.safe_load((ROOT / "config" / "parallel_tracks.yaml").read_text())["tracks"]; s = settings.stored()
    for k, v in t.items():
        o = s.get(f"track:{k}")
        if o: v.update(o)
    return t

def set_track(key: str, lead_weeks: float | None, source: str | None) -> dict:
    if key not in tracks_cfg(): raise HTTPException(404, "unknown track")
    if lead_weeks is not None and (isinstance(lead_weeks, bool) or lead_weeks < 0): raise HTTPException(422, "lead weeks must be non-negative")
    if lead_weeks is not None and not (source or "").strip(): raise HTTPException(422, "a lead time needs a source (who told you, which page)")
    with conn() as c: settings._put(c, f"track:{key}", {"lead_weeks": lead_weeks, "source": (source or None)}); c.commit()
    return tracks_cfg()[key]

def weeks_for(scenario: str) -> dict:
    t = economics.timeline_defaults()["target"]
    if scenario == "target": return {"consent_weeks": t["consent_weeks"], "works_weeks": t["works_weeks"], "audit_weeks": t["audit_signoff_weeks"], "fill_weeks": t["fill_weeks"]}
    if scenario == "delay": w = weeks_for("target"); w["consent_weeks"] += DELAY_WEEKS; return w
    if scenario == "contract": raise HTTPException(422, "the contract scenario has a total (months) but no phase split: set consent, works and audit weeks explicitly")
    raise HTTPException(422, "scenario must be target, delay or contract")

def can_hit_target(parcel_id: int, structural_light: bool | None = None) -> dict:
    f = _facts(parcel_id); v = lambda k: (f.get(k) or {}).get("value")
    unknown, blockers = [], []
    lifts = v("lifts"); storeys = v("storeys_per_building")
    if storeys is None: unknown.append("storeys")
    elif str(storeys) not in ("1", "[1]") and lifts is None: unknown.append("lift presence on a multi-storey building")
    elif str(storeys) not in ("1", "[1]") and (lifts or {}).get("count") == 0: blockers.append("a lift would have to be added")
    for k in ("sprinklers", "fire_alarm"):
        x = v(k)
        if x is None: unknown.append(k)
        elif x in ("none", False): blockers.append(f"no {k.replace('_', ' ')} in place")
    if structural_light is None: unknown.append("structural work: needs the structural engineer's view (mark it on the Timeline screen)")
    elif structural_light is False: blockers.append("major structural work")
    verdict = "contract_only" if blockers else ("unknown" if unknown else "can_hit_target")
    return {"verdict": verdict, "blockers": blockers, "unknown": unknown, "rule": "light retrofit only: no lift to add, no major structural work, sprinklers and alarm largely in place (spec Part 3 section 7)"}

def plan(parcel_id: int, scenario: str = "target", opening: date | None = None) -> dict:
    get_property(parcel_id); w = weeks_for(scenario) if scenario != "contract" else None
    with conn() as c: sl = (c.execute("SELECT value FROM core.user_setting WHERE key=%s", (f"structure_light:{parcel_id}",)).fetchone() or {}).get("value")
    out = {"parcel_id": parcel_id, "scenario": scenario, "can_hit_target": can_hit_target(parcel_id, sl)}
    if scenario == "contract":
        m = economics.timeline_defaults()["contract"]["total_months"]; out.update(total_months=m, total_weeks=round(m * 52 / 12), stages=None, note="Total only; the phase split is not specified. Set it before using this in the Offer Builder.")
    else:
        stages, cur = [], 0
        for key, label in (("consent_weeks", "Building consent (from a complete lodgement)"), ("works_weeks", "Works"), ("audit_weeks", "Audit and sign-off"), ("fill_weeks", "Fill")):
            stages.append({"key": key, "label": label, "start_week": cur, "weeks": w[key], "end_week": cur + w[key]}); cur += w[key]
        out.update(stages=stages, total_weeks=cur)
        if opening:
            start = opening - timedelta(weeks=cur)
            for s in stages: s["start_date"] = (start + timedelta(weeks=s["start_week"])).isoformat(); s["end_date"] = (start + timedelta(weeks=s["end_week"])).isoformat()
            out["start_date"] = start.isoformat()
    tr = []
    for k, t in tracks_cfg().items():
        row = {"key": k, "title": t["title"], "owner": t["owner"], "lead_weeks": t["lead_weeks"], "source": t.get("source")}
        if t["lead_weeks"] is None: row["start_date"] = None; row["note"] = "set lead time"
        elif opening: row["start_date"] = (opening - timedelta(weeks=t["lead_weeks"])).isoformat()
        tr.append(row)
    out["parallel_tracks"] = tr; out["opening"] = opening.isoformat() if opening else None
    out["label"] = "Planning aid from editable durations (assumptions in config/timeline_defaults.yaml); not a promise of any Council, auditor or builder timeframe."
    return out

def set_structure_light(parcel_id: int, light: bool | None) -> dict:
    get_property(parcel_id)
    with conn() as c:
        if light is None: c.execute("DELETE FROM core.user_setting WHERE key=%s", (f"structure_light:{parcel_id}",))
        else: settings._put(c, f"structure_light:{parcel_id}", light)
        c.commit()
    return can_hit_target(parcel_id, light)

# ---- milestones
MILESTONES = ["lodged", "rfi_received", "consent_granted", "works_started", "works_complete", "audit_booked", "certified", "first_resident"]
def set_milestone(parcel_id: int, key: str, planned_on: date | None, actual_on: date | None, note: str | None) -> list[dict]:
    if key not in MILESTONES: raise HTTPException(422, f"milestone must be one of {MILESTONES}")
    get_property(parcel_id)
    if actual_on and actual_on > date.today(): raise HTTPException(422, "actual date is in the future")
    with conn() as c:
        c.execute("""INSERT INTO core.rh_milestone (parcel_id, key, planned_on, actual_on, note) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (parcel_id, key)
                     DO UPDATE SET planned_on=EXCLUDED.planned_on, actual_on=EXCLUDED.actual_on, note=EXCLUDED.note""", (parcel_id, key, planned_on, actual_on, note)); c.commit()
    return milestones(parcel_id)

def milestones(parcel_id: int) -> list[dict]:
    with conn() as c: rows = {r["key"]: r for r in c.execute("SELECT * FROM core.rh_milestone WHERE parcel_id=%s", (parcel_id,)).fetchall()}
    out = []
    for k in MILESTONES:
        r = rows.get(k); late = (r["actual_on"] - r["planned_on"]).days if r and r["actual_on"] and r["planned_on"] else None
        out.append({"key": k, "planned_on": r["planned_on"].isoformat() if r and r["planned_on"] else None, "actual_on": r["actual_on"].isoformat() if r and r["actual_on"] else None, "days_late": late, "note": r["note"] if r else None})
    return out

# ---- human minutes metrics
STEPS = ["plan_review", "layout_review", "pack_review", "engineer_coordination", "owner_contact", "council_liaison", "site_capture_review", "other"]
def log_minutes(parcel_id: int | None, step: str, minutes: float, note: str | None = None) -> dict:
    if step not in STEPS: raise HTTPException(422, f"step must be one of {STEPS}")
    if isinstance(minutes, bool) or minutes < 0 or minutes > 1440: raise HTTPException(422, "minutes must be between 0 and 1440")
    with conn() as c: c.execute("INSERT INTO core.rh_effort_log (parcel_id, step, minutes, note) VALUES (%s,%s,%s,%s)", (parcel_id, step, minutes, note)); c.commit()
    return metrics()

def metrics() -> dict:
    with conn() as c: rows = c.execute("SELECT step, count(*) AS n, sum(minutes)::float AS total, avg(minutes)::float AS avg FROM core.rh_effort_log GROUP BY step ORDER BY step").fetchall()
    per_prop = None
    with conn() as c: r = c.execute("SELECT avg(t)::float AS a FROM (SELECT sum(minutes) AS t FROM core.rh_effort_log WHERE parcel_id IS NOT NULL GROUP BY parcel_id) x").fetchone(); per_prop = r["a"]
    return {"by_step": [{**r, "total": round(r["total"], 1), "avg": round(r["avg"], 1)} for r in rows], "avg_minutes_per_property": round(per_prop, 1) if per_prop is not None else None,
            "note": "Human minutes you log per step. Blank until you log some: nothing is estimated."}
