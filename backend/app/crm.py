"""CRM link (MASTER_SPEC Part 4 section 5, Part 6): a lead created from a listing or parcel. Guardrails enforced here and in the database: a lead cannot be marked contactable without a source, a lawful basis and a counterparty type
(also a CHECK constraint); a do-not-contact match blocks every outreach activity; tenants are never a counterparty; outreach activities (visit, call, email, letter, meeting) need a contactable lead. The whole module sits behind the
outreach_enabled flag (routes /api/crm answer 403 while it is false). Nothing here sends anything."""
from datetime import date
from fastapi import HTTPException
from .db import conn

OUTREACH_KINDS = ("visit", "call", "email", "letter", "meeting")
STAGES = ("new", "researched", "contacted", "meeting", "loi_offer", "negotiation", "conditional_signed", "consent_certification", "live", "lost")

def _norm(x): return (x or "").strip().lower()

def on_do_not_contact(lead: dict) -> dict | None:
    with conn() as c: rows = c.execute("SELECT * FROM core.user_crm_do_not_contact").fetchall()
    for r in rows:
        if (r["parcel_id"] and r["parcel_id"] == lead.get("parcel_id")) or (r["contact_name"] and _norm(r["contact_name"]) == _norm(lead.get("contact_name"))) or (r["business_detail"] and _norm(r["business_detail"]) == _norm(lead.get("contact_business_detail"))): return r
    return None

def create_lead(listing_id: int | None = None, parcel_id: int | None = None, notes: str | None = None) -> dict:
    if listing_id is None and parcel_id is None: raise HTTPException(422, "give a listing or a parcel")
    with conn() as c:
        if listing_id:
            l = c.execute("SELECT parcel_id FROM core.user_listing WHERE id=%s", (listing_id,)).fetchone()
            if not l: raise HTTPException(404, "no such listing")
            parcel_id = parcel_id or l["parcel_id"]
        r = c.execute("INSERT INTO core.user_crm_lead (parcel_id, listing_id, notes) VALUES (%s,%s,%s) RETURNING *", (parcel_id, listing_id, notes)).fetchone(); c.commit()
    return r

def get(lead_id: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.user_crm_lead WHERE id=%s", (lead_id,)).fetchone()
    if not r: raise HTTPException(404, "no such lead")
    return {**r, "do_not_contact": bool(on_do_not_contact(r))}

def update_lead(lead_id: int, fields: dict) -> dict:
    allowed = {"counterparty_type", "contact_name", "contact_business_detail", "source", "lawful_basis", "assigned_rep", "priority", "next_action", "next_action_on", "notes"}
    bad = [k for k in fields if k not in allowed]
    if bad: raise HTTPException(422, f"cannot set {bad} here")
    if fields.get("counterparty_type") not in (None, "owner", "landlord", "property_manager", "trustees"): raise HTTPException(422, "counterparty must be owner, landlord, property_manager or trustees (tenants are never approached)")
    get(lead_id); sets = ", ".join(f"{k}=%s" for k in fields)
    if sets:
        with conn() as c: c.execute(f"UPDATE core.user_crm_lead SET {sets} WHERE id=%s", (*fields.values(), lead_id)); c.commit()
    return get(lead_id)

def set_contactable(lead_id: int, value: bool) -> dict:
    l = get(lead_id)
    if value:
        miss = [k for k in ("source", "lawful_basis", "counterparty_type") if not l.get(k)]
        if miss: raise HTTPException(422, f"cannot mark contactable: {miss} required (where the contact came from and the lawful basis)")
        if l["do_not_contact"]: raise HTTPException(409, "this contact is on the do-not-contact list")
    with conn() as c: c.execute("UPDATE core.user_crm_lead SET contactable=%s WHERE id=%s", (value, lead_id)); c.commit()
    return get(lead_id)

def add_do_not_contact(reason: str, contact_name: str | None = None, business_detail: str | None = None, parcel_id: int | None = None) -> dict:
    if not (reason or "").strip() or not (contact_name or business_detail or parcel_id): raise HTTPException(422, "a reason and a name, contact detail or parcel are required")
    with conn() as c:
        r = c.execute("INSERT INTO core.user_crm_do_not_contact (contact_name, business_detail, parcel_id, reason) VALUES (%s,%s,%s,%s) RETURNING *", (contact_name, business_detail, parcel_id, reason)).fetchone()
        c.execute("UPDATE core.user_crm_lead SET contactable=false WHERE (parcel_id IS NOT NULL AND parcel_id=%s) OR (contact_name IS NOT NULL AND lower(contact_name)=lower(%s))", (parcel_id, contact_name)); c.commit()
    return r

def add_activity(lead_id: int, kind: str, outcome: str | None, notes: str | None) -> dict:
    l = get(lead_id)
    if kind not in OUTREACH_KINDS + ("note",): raise HTTPException(422, f"kind must be one of {list(OUTREACH_KINDS) + ['note']}")
    if kind in OUTREACH_KINDS:
        if l["do_not_contact"]: raise HTTPException(409, "do-not-contact: outreach refused")
        if not l["contactable"]: raise HTTPException(409, "lead is not marked contactable (source and lawful basis first)")
    with conn() as c: r = c.execute("INSERT INTO core.user_crm_activity (lead_id, kind, outcome, notes) VALUES (%s,%s,%s,%s) RETURNING *", (lead_id, kind, outcome, notes)).fetchone(); c.commit()
    return r

def set_stage(lead_id: int, stage: str, lost_reason: str | None = None) -> dict:
    if stage not in STAGES: raise HTTPException(422, f"stage must be one of {list(STAGES)}")
    if stage == "lost" and not (lost_reason or "").strip(): raise HTTPException(422, "a lost lead needs a reason")
    if stage in ("contacted", "meeting", "loi_offer", "negotiation") and not get(lead_id)["contactable"]: raise HTTPException(409, "lead is not marked contactable")
    with conn() as c: c.execute("UPDATE core.user_crm_lead SET stage=%s, lost_reason=%s WHERE id=%s", (stage, lost_reason, lead_id)); c.commit()
    return get(lead_id)

def funnel() -> dict:
    with conn() as c: rows = c.execute("SELECT stage, count(*) AS n FROM core.user_crm_lead GROUP BY stage").fetchall()
    d = {r["stage"]: r["n"] for r in rows}; return {s: d.get(s, 0) for s in STAGES}
