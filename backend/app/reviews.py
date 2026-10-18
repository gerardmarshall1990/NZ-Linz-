"""Engineer review workflow (MASTER_SPEC 7.3 step 7, 8.2): a review package per role (designer, fire, structural, services) built from the brief and pack, sent by the owner, comments and return recorded, turnaround measured.
Nothing is emailed by the app (outreach features are off): `send` returns a private link ONCE, for the owner to pass on. The link works only while the `engineer_review_links` flag is ON; otherwise the owner downloads the package zip and sends it themselves.
Engineers' comments are recorded as comments, never as approvals; a producer statement still comes back as an upload to the pack."""
import hashlib, io, secrets, statistics, zipfile
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from . import briefs, consent_pack, flags
from .db import conn
from .pack_pdf import md_to_pdf
from .stamp import STAMP

ROLES = {"designer": "accessibility", "fire": "fire", "structural": "structural", "services": "services"}
LINK_DAYS = 14

def _h(tok: str) -> str: return hashlib.sha256(tok.encode()).hexdigest()

def _pkg(pid: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.rh_review_package WHERE id=%s", (pid,)).fetchone()
    if not r: raise HTTPException(404, "no such review package")
    return r

def _event(pid, kind, author=None, body=None):
    with conn() as c: c.execute("INSERT INTO core.rh_review_event (package_id, kind, author, body) VALUES (%s,%s,%s,%s)", (pid, kind, author, (body or "")[:4000] or None)); c.commit()

def create(pack_id: int, role: str, name: str | None, company: str | None) -> dict:
    if role not in ROLES: raise HTTPException(422, f"role must be one of {list(ROLES)}")
    p = consent_pack._pack(pack_id)
    if p["status"] == "superseded": raise HTTPException(409, "superseded pack")
    with conn() as c:
        r = c.execute("INSERT INTO core.rh_review_package (pack_id, role, engineer_name, engineer_company, version) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                      (pack_id, role, name, company, p["version"])).fetchone(); c.commit()
    _event(r["id"], "created"); return view(r["id"])

def send(pid: int) -> dict:
    k = _pkg(pid)
    if k["status"] in ("returned", "cancelled"): raise HTTPException(409, f"package is {k['status']}")
    tok = secrets.token_urlsafe(32); exp = datetime.now(timezone.utc) + timedelta(days=LINK_DAYS)
    with conn() as c:
        c.execute("UPDATE core.rh_review_package SET token_hash=%s, expires_at=%s, status=CASE WHEN status='commented' THEN status ELSE 'sent' END, sent_at=COALESCE(sent_at, now()) WHERE id=%s", (_h(tok), exp, pid)); c.commit()
    _event(pid, "sent", "owner", "link issued (shown once)")
    live = flags.enabled("engineer_review_links")
    return {**view(pid), "link": f"/review/{tok}" if live else None, "link_note": "Shown once. Send it yourself; the app sends nothing." if live else
            "The engineer_review_links flag is OFF, so no link was issued that works. Download the package zip and send it yourself.", "expires_at": exp.isoformat() if live else None}

def cancel(pid: int) -> dict:
    _pkg(pid)
    with conn() as c: c.execute("UPDATE core.rh_review_package SET status='cancelled', token_hash=NULL WHERE id=%s", (pid,)); c.commit()
    _event(pid, "cancelled", "owner"); return view(pid)

def view(pid: int) -> dict:
    k = _pkg(pid)
    with conn() as c: ev = c.execute("SELECT kind, author, body, at FROM core.rh_review_event WHERE package_id=%s ORDER BY id", (pid,)).fetchall()
    return {"id": k["id"], "pack_id": k["pack_id"], "role": k["role"], "engineer_name": k["engineer_name"], "engineer_company": k["engineer_company"], "status": k["status"], "version": k["version"],
            "sent_at": k["sent_at"].isoformat() if k["sent_at"] else None, "returned_at": k["returned_at"].isoformat() if k["returned_at"] else None,
            "events": [{**e, "at": e["at"].isoformat()} for e in ev]}

def list_for_pack(pack_id: int) -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.rh_review_package WHERE pack_id=%s ORDER BY id", (pack_id,)).fetchall()]
    return [view(i) for i in ids]

def content(pid: int) -> dict:
    k = _pkg(pid); p = consent_pack._pack(k["pack_id"]); disc = {"designer": ("design", "review"), "fire": ("fire",), "structural": ("structural",), "services": ("services",)}[k["role"]]
    b = briefs.build(p["parcel_id"], p["option_id"], ROLES[k["role"]])
    slots = [d for d in consent_pack._docs(p["id"]) if d["kind"] == "upload_slot" and d["discipline"] in disc]
    return {"title": b["title"], "body_md": b["body_md"], "wanted_from_you": [{"document": d["title"], "type": d["statement_type"] or "document"} for d in slots]}

def package_zip(pid: int) -> bytes:
    k = _pkg(pid); p = consent_pack._pack(k["pack_id"]); c = content(pid); buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Brief.pdf", md_to_pdf(c["body_md"], c["title"]))
        z.writestr("Documents wanted from you.txt", f"{STAMP}\n\n" + "\n".join(f"- {w['document']} ({w['type']}): please return as a PDF, signed by you, for the owner to upload." for w in c["wanted_from_you"]) + "\n\nThe app produces no statements or signatures on your behalf.\n")
        files, _ = consent_pack.drawing_files(p)
        for name, pdf_b, dxf_b in files: z.writestr(f"Drawings/{consent_pack.safe_name(name)}.pdf", pdf_b); z.writestr(f"Drawings/{consent_pack.safe_name(name)}.dxf", dxf_b)
    return buf.getvalue()

# ---- engineer side (token gated, flag gated)
def _by_token(tok: str) -> dict:
    if not flags.enabled("engineer_review_links"): raise HTTPException(404, "not found")
    with conn() as c: k = c.execute("SELECT * FROM core.rh_review_package WHERE token_hash=%s", (_h(tok),)).fetchone()
    if not k or k["status"] in ("cancelled", "returned") or (k["expires_at"] and k["expires_at"] < datetime.now(timezone.utc)): raise HTTPException(404, "not found")
    return k

def open_link(tok: str) -> dict:
    k = _by_token(tok); first = False
    with conn() as c: first = not c.execute("SELECT 1 FROM core.rh_review_event WHERE package_id=%s AND kind='viewed'", (k["id"],)).fetchone()
    if first: _event(k["id"], "viewed", k["engineer_name"])
    c = content(k["id"])
    return {"role": k["role"], "title": c["title"], "body_md": c["body_md"], "wanted_from_you": c["wanted_from_you"], "label": STAMP}

def comment_link(tok: str, author: str, body: str) -> dict:
    k = _by_token(tok)
    if not body.strip(): raise HTTPException(422, "empty comment")
    _event(k["id"], "comment", (author or k["engineer_name"] or "engineer")[:120], body)
    with conn() as c: c.execute("UPDATE core.rh_review_package SET status='commented' WHERE id=%s AND status='sent'", (k["id"],)); c.commit()
    return {"ok": True}

def return_link(tok: str, author: str) -> dict:
    k = _by_token(tok)
    with conn() as c: c.execute("UPDATE core.rh_review_package SET status='returned', returned_at=now(), token_hash=NULL WHERE id=%s", (k["id"],)); c.commit()
    _event(k["id"], "returned", author or k["engineer_name"]); return {"ok": True}

def mark_returned(pid: int, note: str | None = None) -> dict:
    """The owner records that the engineer replied outside the app (email, phone)."""
    k = _pkg(pid)
    if k["status"] in ("returned", "cancelled"): raise HTTPException(409, f"package is {k['status']}")
    with conn() as c: c.execute("UPDATE core.rh_review_package SET status='returned', returned_at=now(), token_hash=NULL, sent_at=COALESCE(sent_at, created_at) WHERE id=%s", (pid,)); c.commit()
    _event(pid, "returned", "owner", note or "recorded by the owner"); return view(pid)

def metrics() -> dict:
    with conn() as c: rows = c.execute("SELECT id, role, engineer_name, engineer_company, status, sent_at, returned_at FROM core.rh_review_package").fetchall()
    out = {}
    for role in ROLES:
        rs = [r for r in rows if r["role"] == role]; done = [(r["returned_at"] - r["sent_at"]).total_seconds() / 3600 for r in rs if r["returned_at"] and r["sent_at"]]
        waiting = [(datetime.now(timezone.utc) - r["sent_at"]).total_seconds() / 3600 for r in rs if r["status"] in ("sent", "commented") and r["sent_at"]]
        out[role] = {"packages": len(rs), "returned": len(done), "median_turnaround_hours": round(statistics.median(done), 1) if done else None, "outstanding": len(waiting), "oldest_outstanding_hours": round(max(waiting), 1) if waiting else None}
    return {"by_role": out, "note": "Turnaround = sent to returned. Blank means no data yet."}
