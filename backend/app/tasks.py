"""Task assignment to a local assistant or project manager with due dates and status (MASTER_SPEC 8.6)."""
from datetime import date
from fastapi import HTTPException
from .db import conn

def create(title: str, assignee: str | None, due_on: date | None, subject_type: str | None = None, subject_id: int | None = None) -> dict:
    if not (title or "").strip(): raise HTTPException(422, "a task needs a title")
    with conn() as c: r = c.execute("INSERT INTO core.user_task (title, assignee, due_on, subject_type, subject_id) VALUES (%s,%s,%s,%s,%s) RETURNING id", (title.strip(), assignee, due_on, subject_type, subject_id)).fetchone(); c.commit()
    return get(r["id"])

def get(tid: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.user_task WHERE id=%s", (tid,)).fetchone()
    if not r: raise HTTPException(404, "no such task")
    return {**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}, "overdue": bool(r["due_on"] and r["status"] == "open" and r["due_on"] < date.today())}

def set_status(tid: int, status: str) -> dict:
    if status not in ("open", "done", "cancelled"): raise HTTPException(422, "status must be open, done or cancelled")
    with conn() as c: c.execute("UPDATE core.user_task SET status=%s, done_at=CASE WHEN %s='done' THEN now() ELSE NULL END WHERE id=%s", (status, status, tid)); c.commit()
    return get(tid)

def list_(assignee: str | None = None, status: str | None = "open") -> list[dict]:
    q, a = ["TRUE"], []
    if assignee: q.append("assignee=%s"); a.append(assignee)
    if status: q.append("status=%s"); a.append(status)
    with conn() as c: ids = [r["id"] for r in c.execute(f"SELECT id FROM core.user_task WHERE {' AND '.join(q)} ORDER BY due_on NULLS LAST, id", a).fetchall()]
    return [get(i) for i in ids]
