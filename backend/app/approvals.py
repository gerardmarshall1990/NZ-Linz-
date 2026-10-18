"""Approval records. Nothing leaves the app, and nothing is recorded as sent or lodged, without an approval the owner made with one tap (MASTER_SPEC Part 8, decision 15).
Flow: an action that would issue something asks `require(...)`; with no approved, unused record it creates a pending one (with the draft text) and refuses with 409 {approval_required}. The owner approves or rejects in the app;
the action then succeeds once and consumes the approval. The app sends nothing itself: approval permits the app to issue a link or record the step; the owner still sends or lodges."""
from fastapi import HTTPException
from .db import conn

KINDS = {"review_link_issue": "Issue a private review link to an engineer", "plan_request_sent": "Record a plan request as sent to an owner or agent", "council_lodgement": "Record that the consent pack was lodged with the Council",
         "rfi_response_sent": "Record a response to a Council request for information as sent", "owner_message": "Send or record a message to a property owner"}

def _view(r: dict) -> dict: return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}

def request(kind: str, subject_type: str, subject_id: int, summary: str, draft_text: str | None = None) -> dict:
    if kind not in KINDS: raise HTTPException(422, f"unknown approval kind {kind!r}")
    with conn() as c:
        r = c.execute("SELECT * FROM core.rh_approval WHERE kind=%s AND subject_type=%s AND subject_id=%s AND status='pending' ORDER BY id DESC LIMIT 1", (kind, subject_type, subject_id)).fetchone()
        if not r: r = c.execute("INSERT INTO core.rh_approval (kind, subject_type, subject_id, summary, draft_text) VALUES (%s,%s,%s,%s,%s) RETURNING *", (kind, subject_type, subject_id, summary, draft_text)).fetchone(); c.commit()
    return _view(r)

def require(kind: str, subject_type: str, subject_id: int, summary: str, draft_text: str | None = None) -> int:
    """Return the id of an approved, unused record and mark it used; otherwise create a pending one and raise 409."""
    with conn() as c:
        r = c.execute("SELECT id FROM core.rh_approval WHERE kind=%s AND subject_type=%s AND subject_id=%s AND status='approved' AND used_at IS NULL ORDER BY id LIMIT 1", (kind, subject_type, subject_id)).fetchone()
        if r: c.execute("UPDATE core.rh_approval SET used_at = now() WHERE id=%s", (r["id"],)); c.commit(); return r["id"]
    a = request(kind, subject_type, subject_id, summary, draft_text)
    raise HTTPException(409, {"approval_required": True, "approval_id": a["id"], "kind": kind, "message": f"Needs your approval first: {KINDS[kind]}. Approve it in the approval list, then repeat the action."})

def decide(aid: int, approve: bool, note: str | None = None) -> dict:
    with conn() as c:
        r = c.execute("UPDATE core.rh_approval SET status=%s, decided_at=now(), decided_by='owner', note=%s WHERE id=%s AND status='pending' RETURNING *", ("approved" if approve else "rejected", note, aid)).fetchone(); c.commit()
    if not r: raise HTTPException(409, "no such pending approval (already decided?)")
    return _view(r)

def pending() -> list[dict]:
    with conn() as c: return [_view(r) for r in c.execute("SELECT * FROM core.rh_approval WHERE status='pending' ORDER BY id").fetchall()]

def history(limit: int = 100) -> list[dict]:
    with conn() as c: return [_view(r) for r in c.execute("SELECT * FROM core.rh_approval ORDER BY id DESC LIMIT %s", (limit,)).fetchall()]
