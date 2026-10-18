"""Feature flags (stored in core.user_flag). Every flag defaults OFF: a flag that is not in the table is off."""
from fastapi import HTTPException
from .db import conn

KNOWN = {
    "engineer_review_links": "Lets an engineer open a read-only review page through a private link you send them. OFF: nothing is reachable without the app login.",
}

def enabled(key: str) -> bool:
    with conn() as c: r = c.execute("SELECT enabled FROM core.user_flag WHERE key = %s", (key,)).fetchone()
    return bool(r and r["enabled"])

def set_flag(key: str, on: bool, by: str = "owner", note: str | None = None) -> dict:
    if key not in KNOWN: raise HTTPException(404, f"unknown flag {key!r}")
    with conn() as c:
        c.execute("""INSERT INTO core.user_flag (key, enabled, changed_by, note) VALUES (%s,%s,%s,%s)
                     ON CONFLICT (key) DO UPDATE SET enabled = EXCLUDED.enabled, changed_at = now(), changed_by = EXCLUDED.changed_by, note = EXCLUDED.note""", (key, on, by, note)); c.commit()
    return {"key": key, "enabled": on}

def all_flags() -> list[dict]:
    with conn() as c: rows = {r["key"]: r for r in c.execute("SELECT key, enabled, changed_at FROM core.user_flag").fetchall()}
    return [{"key": k, "description": d, "enabled": bool(rows.get(k) and rows[k]["enabled"]), "changed_at": rows[k]["changed_at"].isoformat() if k in rows else None} for k, d in KNOWN.items()]
