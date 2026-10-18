"""RFI tracker (MASTER_SPEC Part 3 section 8): the Council's requests for information on a lodged consent. Each RFI has items with an owner role, a due date the OWNER enters from the Council's letter (no statutory period is assumed here)
and a response. Marking a response as sent needs an approval record. The app answers nothing for you."""
from datetime import date
from fastapi import HTTPException
from . import approvals
from .db import conn
from .facts import get_property

def _view(rid: int) -> dict:
    with conn() as c:
        r = c.execute("SELECT * FROM core.rh_rfi WHERE id=%s", (rid,)).fetchone()
        if not r: raise HTTPException(404, "no such RFI")
        items = c.execute("SELECT * FROM core.rh_rfi_item WHERE rfi_id=%s ORDER BY id", (rid,)).fetchall()
    today = date.today(); open_items = [i for i in items if i["status"] == "open"]
    return {**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}, "items": items, "open_items": len(open_items),
            "days_to_due": (r["due_on"] - today).days if r["due_on"] and r["status"] == "open" else None, "overdue": bool(r["due_on"] and r["status"] == "open" and r["due_on"] < today)}

def add(parcel_id: int, received_on: date, summary: str, items: list[dict], due_on: date | None = None, council_ref: str | None = None, pack_id: int | None = None) -> dict:
    get_property(parcel_id)
    if received_on > date.today(): raise HTTPException(422, "received date is in the future")
    if not (summary or "").strip() or not items: raise HTTPException(422, "an RFI needs a summary and at least one item")
    if due_on and due_on < received_on: raise HTTPException(422, "due date is before the received date")
    with conn() as c:
        r = c.execute("INSERT INTO core.rh_rfi (parcel_id, pack_id, council_ref, received_on, due_on, summary) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id", (parcel_id, pack_id, council_ref, received_on, due_on, summary.strip())).fetchone()
        for it in items: c.execute("INSERT INTO core.rh_rfi_item (rfi_id, text, owner_role) VALUES (%s,%s,%s)", (r["id"], it["text"], it.get("owner_role")))
        c.commit()
    return _view(r["id"])

def answer_item(item_id: int, status: str, response: str | None) -> dict:
    if status not in ("open", "answered", "not_applicable"): raise HTTPException(422, "bad status")
    if status == "answered" and not (response or "").strip(): raise HTTPException(422, "an answered item needs the response text")
    with conn() as c:
        r = c.execute("UPDATE core.rh_rfi_item SET status=%s, response=%s WHERE id=%s RETURNING rfi_id", (status, response, item_id)).fetchone(); c.commit()
    if not r: raise HTTPException(404, "no such item")
    return _view(r["rfi_id"])

def mark_responded(rid: int, responded_on: date | None = None) -> dict:
    v = _view(rid)
    if v["open_items"]: raise HTTPException(409, f"{v['open_items']} item(s) still open")
    approvals.require("rfi_response_sent", "rfi", rid, f"Record the response to Council RFI {v['council_ref'] or rid} as sent", "\n".join(f"- {i['text']}: {i['response'] or 'N/A'}" for i in v["items"]))
    with conn() as c: c.execute("UPDATE core.rh_rfi SET status='responded', responded_on=%s WHERE id=%s", (responded_on or date.today(), rid)); c.commit()
    return _view(rid)

def close(rid: int) -> dict:
    with conn() as c: c.execute("UPDATE core.rh_rfi SET status='closed' WHERE id=%s", (rid,)); c.commit()
    return _view(rid)

def list_for(parcel_id: int) -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.rh_rfi WHERE parcel_id=%s ORDER BY id DESC", (parcel_id,)).fetchall()]
    return [_view(i) for i in ids]

def overdue_all() -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.rh_rfi WHERE status='open' AND due_on < current_date ORDER BY due_on").fetchall()]
    return [_view(i) for i in ids]
