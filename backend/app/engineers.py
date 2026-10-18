"""Batch engineering workflow (MASTER_SPEC 8.5): engineers with a fixed fee per review and a target turnaround, a per-engineer queue sorted by due date, bulk assignment, escalation of stuck items, reusable comment templates and a scorecard (turnaround against target, rework rate,
issues raised). Review packages carry the playbook delta. Targets and fees are YOUR inputs (blank until set); nothing is assumed."""
from datetime import date, timedelta
from fastapi import HTTPException
from . import consent_pack, playbooks
from .db import conn

DISC = ("designer", "fire", "structural", "services", "other")

def add(name: str, company: str | None, discipline: str, fee_per_review: float | None, target_turnaround_days: int | None, review_window: str | None) -> dict:
    if not (name or "").strip() or discipline not in DISC: raise HTTPException(422, f"name required; discipline one of {list(DISC)}")
    if fee_per_review is not None and fee_per_review < 0 or target_turnaround_days is not None and target_turnaround_days < 1: raise HTTPException(422, "fee must be non-negative and the target at least 1 day")
    with conn() as c: r = c.execute("INSERT INTO core.user_engineer (name, company, discipline, fee_per_review, target_turnaround_days, review_window) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id", (name.strip(), company, discipline, fee_per_review, target_turnaround_days, review_window)).fetchone(); c.commit()
    return get(r["id"])

def get(eid: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.user_engineer WHERE id=%s", (eid,)).fetchone()
    if not r: raise HTTPException(404, "no such engineer")
    return {k: (float(v) if hasattr(v, "as_tuple") else v) for k, v in r.items()}

def list_() -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.user_engineer WHERE active ORDER BY name").fetchall()]
    return [get(i) for i in ids]

ROLE_DISC = {"designer": ("designer",), "fire": ("fire",), "structural": ("structural",), "services": ("services",)}

def assign(package_ids: list[int], engineer_id: int) -> list[dict]:
    e = get(engineer_id)
    with conn() as c:
        for pid in package_ids:
            k = c.execute("SELECT role, status FROM core.rh_review_package WHERE id=%s", (pid,)).fetchone()
            if not k: raise HTTPException(404, f"no such review package {pid}")
            if k["status"] in ("returned", "cancelled"): raise HTTPException(409, f"package {pid} is {k['status']}")
            if e["discipline"] not in ("other", k["role"]): raise HTTPException(409, f"package {pid} is a {k['role']} review; {e['name']} is a {e['discipline']} engineer")
        due = date.today() + timedelta(days=e["target_turnaround_days"]) if e["target_turnaround_days"] else None
        for pid in package_ids:
            c.execute("UPDATE core.rh_review_package SET engineer_id=%s, engineer_name=%s, engineer_company=%s, fee=%s, due_on=%s WHERE id=%s", (engineer_id, e["name"], e["company"], e["fee_per_review"], due, pid))
            c.execute("INSERT INTO core.rh_review_event (package_id, kind, author, body) VALUES (%s,'assigned','owner',%s)", (pid, f"assigned to {e['name']}" + (f", due {due}" if due else ""))); c.commit()
    return queue(engineer_id)

def queue(engineer_id: int | None = None) -> list[dict]:
    q, a = ["k.status NOT IN ('returned','cancelled')"], []
    if engineer_id: q.append("k.engineer_id=%s"); a.append(engineer_id)
    with conn() as c: rows = c.execute(f"SELECT k.id, k.pack_id, k.role, k.engineer_id, k.engineer_name, k.status, k.due_on, k.fee, k.escalated_at, p.parcel_id FROM core.rh_review_package k JOIN core.rh_pack p ON p.id=k.pack_id WHERE {' AND '.join(q)} ORDER BY k.due_on NULLS LAST, k.id", a).fetchall()
    today = date.today(); return [{**{k: (v.isoformat() if hasattr(v, "isoformat") else (float(v) if hasattr(v, "as_tuple") else v)) for k, v in r.items()}, "overdue": bool(r["due_on"] and r["due_on"] < today), "days_to_due": (r["due_on"] - today).days if r["due_on"] else None} for r in rows]

def escalate_overdue() -> dict:
    """Mark overdue, not-yet-escalated packages as escalated and record an event. Nothing is sent: the owner chases."""
    done = []
    with conn() as c:
        for r in c.execute("SELECT id FROM core.rh_review_package WHERE status IN ('draft','sent','commented') AND due_on < current_date AND escalated_at IS NULL").fetchall():
            c.execute("UPDATE core.rh_review_package SET escalated_at=now() WHERE id=%s", (r["id"],)); c.execute("INSERT INTO core.rh_review_event (package_id, kind, author, body) VALUES (%s,'escalated','system','overdue against the target turnaround')", (r["id"],)); done.append(r["id"])
        c.commit()
    return {"escalated": done, "note": "Escalation is a flag and an event: the app sends nothing. Chase the engineer yourself."}

def add_template(title: str, body: str, discipline: str | None) -> dict:
    if not (title or "").strip() or not (body or "").strip(): raise HTTPException(422, "title and body required")
    with conn() as c: r = c.execute("INSERT INTO core.user_comment_template (title, body, discipline) VALUES (%s,%s,%s) RETURNING id, title, body, discipline", (title.strip(), body.strip(), discipline)).fetchone(); c.commit()
    return r

def templates(discipline: str | None = None) -> list[dict]:
    with conn() as c: return c.execute("SELECT id, title, body, discipline FROM core.user_comment_template WHERE (%s::text IS NULL OR discipline IS NULL OR discipline=%s) ORDER BY id", (discipline, discipline)).fetchall()

def scorecard() -> list[dict]:
    out = []
    for e in list_():
        with conn() as c:
            ks = c.execute("SELECT k.id, k.pack_id, k.role, k.status, k.sent_at, k.returned_at, k.created_at, k.due_on FROM core.rh_review_package k WHERE k.engineer_id=%s", (e["id"],)).fetchall()
            issues = c.execute("SELECT count(*) AS n FROM core.rh_review_event v JOIN core.rh_review_package k ON k.id=v.package_id WHERE k.engineer_id=%s AND v.kind='comment'", (e["id"],)).fetchone()["n"]
        done = [(k["returned_at"] - (k["sent_at"] or k["created_at"])).total_seconds() / 86400 for k in ks if k["returned_at"]]; tgt = e["target_turnaround_days"]
        ontime = [d <= tgt for d in done] if tgt else []
        seen = {}; rework = 0
        for k in sorted(ks, key=lambda k: k["id"]):
            key = (k["pack_id"], k["role"])
            if key in seen: rework += 1
            seen[key] = 1
        out.append({"engineer": e["name"], "discipline": e["discipline"], "assigned": len(ks), "returned": len(done), "avg_turnaround_days": round(sum(done) / len(done), 1) if done else None, "target_days": tgt,
                    "on_time_rate": round(sum(ontime) / len(ontime), 2) if ontime else None, "rework_rate": round(rework / len(ks), 2) if ks else None, "issues_raised": issues})
    return out

def playbook_delta_text(pack_id: int) -> str:
    p = consent_pack._pack(pack_id); matches = playbooks.match(p["parcel_id"])
    if not matches: return "No archetype playbook matches this property: every item is shown in full."
    d = playbooks.delta(p["parcel_id"], p["option_id"], matches[0]); head = f"Playbook: {matches[0]} ({'reviewed' if d['reviewed_by_engineer'] else 'not yet reviewed by your engineers'})."
    return head + (" " + d.get("reason", "") if not d["delta_available"] else " Differences from the playbook:") + "\n" + "\n".join(f"- {i['id']} [{i['status']}]: {i['detail']}" for i in d["items"][:25])
