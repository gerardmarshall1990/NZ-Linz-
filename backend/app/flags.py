"""Feature flags (stored in core.user_flag). Every flag defaults OFF: a flag that is not in the table is off."""
import yaml
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from .config import ROOT
from .db import conn

# Features that stay disabled until the owner sets the flag in config/feature_flags.yaml (the app has no switch for these: only the owner edits the file, after the validation report passes).
GATED = {"outreach_enabled": ("/api/outreach", "/api/crm", "/crm", "/api/call-sheets", "/api/routes", "/api/leads"),
         "field_capture_enabled": ("/api/field", "/field"),
         "offer_letters_enabled": ("/api/offer-letters",)}

def gated_flags() -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "feature_flags.yaml").read_text()) or {}
    return {k: cfg.get(k) is True for k in GATED}        # anything but a literal true is off

def blocked_by(path: str) -> str | None:
    """-> the name of the flag that is off and covers this path, else None."""
    g = gated_flags()
    for flag, prefixes in GATED.items():
        if not g[flag] and any(path == p or path.startswith(p + "/") for p in prefixes): return flag
    return None

def gate_response(flag: str) -> JSONResponse:
    return JSONResponse({"detail": f"this feature is switched off ({flag} is false in config/feature_flags.yaml)"}, 403)

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
    g = [{"key": k, "description": "Disabled until you set it in config/feature_flags.yaml, after the validation report passes.", "enabled": v, "changeable_in_app": False} for k, v in gated_flags().items()]
    with conn() as c: rows = {r["key"]: r for r in c.execute("SELECT key, enabled, changed_at FROM core.user_flag").fetchall()}
    return g + [{"key": k, "changeable_in_app": True, "description": d, "enabled": bool(rows.get(k) and rows[k]["enabled"]), "changed_at": rows[k]["changed_at"].isoformat() if k in rows else None} for k, d in KNOWN.items()]
