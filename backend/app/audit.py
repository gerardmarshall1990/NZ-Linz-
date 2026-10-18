"""Audit log of lead views, exports and contact attempts (MASTER_SPEC Part 4 section 5.5 item 5)."""
import json
from .db import conn

def log(action: str, subject_type: str, subject_id: int | None = None, detail: dict | None = None) -> None:
    with conn() as c: c.execute("INSERT INTO core.user_audit_log (action, subject_type, subject_id, detail) VALUES (%s,%s,%s,%s::jsonb)", (action, subject_type, subject_id, json.dumps(detail or {}, default=str))); c.commit()

def recent(limit: int = 100) -> list[dict]:
    with conn() as c: return [{**r, "at": r["at"].isoformat()} for r in c.execute("SELECT id, action, subject_type, subject_id, detail, at FROM core.user_audit_log ORDER BY id DESC LIMIT %s", (limit,)).fetchall()]
