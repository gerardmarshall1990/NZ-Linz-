"""Plan request pack (MASTER_SPEC Part 3 section 1.3): an email to the owner or agent, the Council property file / LIM request guidance, and a site-visit form that writes to the Property Record at CONFIRMED.
Drafts only: the app sends nothing (outreach is off); the owner copies the text. Council fees and turnaround are quoted from the Council's pages as found, with the date, and flagged to be checked before paying."""
from datetime import date
from fastapi import HTTPException
from .config import field_catalogue
from .db import conn
from . import approvals
from .facts import get_property, set_fact

COUNCIL = {
    "last_verified": "2026-10-18",
    "how_verified": "Search-result summaries of aucklandcouncil.govt.nz pages. The pages themselves were not opened (the site refuses scripted requests). Check each figure on the page before paying.",
    "pages": {"order_property_report": "https://www.aucklandcouncil.govt.nz/en/buying-property/order-property-report.html", "order_lim": "https://www.aucklandcouncil.govt.nz/en/buying-property/order-property-report/order-lim.html",
              "about_property_files_and_lims": "https://www.aucklandcouncil.govt.nz/en/buying-property/order-property-report/about-property-files-and-lim-reports.html"},
    "lim": {"how": "online application only (libraries with council services can help)", "standard": {"fee_nzd": 387, "turnaround": "up to 10 working days"}, "urgent": {"fee_nzd": 522, "turnaround": "up to 3 working days"},
            "card_fee": "1.75% payment fee for cards", "delivery": "digital link, expires 28 days after issue (no hard copy)"},
    "property_file": {"contents": "building and resource consent documents and correspondence not included in a LIM; the Council suggests ordering both", "fee_nzd": None, "turnaround": None,
                      "note": "Fee and turnaround for a property file were NOT found: open the 'order a property file' page and read them there. Do not rely on a guess."},
    "warning": "Third-party websites offer to order for you and add fees; the Council does not work with them.",
}
WANT = ["Floor plans of all levels and a site plan", "Building consent and code compliance certificate history", "Current compliance schedule and BWOF", "Fire engineer reports", "Any previous change-of-use consents",
        "Room schedule", "Services details (sprinkler, alarm and emergency lighting certificates)", "Photos of each room, corridors, exits and the exterior", "Recent rates or valuation notice", "Lease terms (if leased)"]

SITE_VISIT = [("corridor_width_min_m", "Narrowest corridor clear width (m)"), ("door_width_min_m", "Narrowest door clear width (m)"), ("bedrooms_total", "Number of bedrooms"), ("rooms_with_ensuite", "Rooms with an ensuite"),
              ("shared_bathrooms", "Shared bathrooms"), ("kitchens", "Kitchens"), ("laundries", "Laundries"), ("stairs_count", "Stairs"), ("level_access_entrances", "Entrances with level access"),
              ("sprinklers", "Sprinklers (none / partial / full)"), ("fire_alarm", "Fire alarm (none / smoke alarms / addressable system)"), ("emergency_lighting", "Emergency lighting present"), ("storeys_per_building", "Storeys")]

def email(parcel_id: int, sender: str | None = None) -> dict:
    rec = get_property(parcel_id); s = rec["site"]
    body = [f"Subject: Information request: {s['address']}, {s['suburb']}", "", "Hello,", "",
            f"I am looking at {s['address']} and would like to understand the building before going further. Could you please send, where you have them:", ""] + [f"{i}. {w}" for i, w in enumerate(WANT, 1)] + [
            "", "Anything you have helps, even if partial. I will treat the information as confidential and will not contact tenants.", "", "Thank you,", sender or "[your name and phone]"]
    return {"parcel_id": parcel_id, "kind": "owner_agent", "text": "\n".join(body), "wanted": WANT, "label": "Draft only: nothing is sent from the app. Copy it into your own email."}

def council_guidance(parcel_id: int) -> dict:
    rec = get_property(parcel_id); s = rec["site"]
    with conn() as c: leg = c.execute("SELECT appellation, title_no FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone()
    return {"parcel_id": parcel_id, "prefill": {"address": f"{s['address']}, {s['suburb']}", "legal_description": leg["appellation"], "record_of_title": leg["title_no"]},
            "council": COUNCIL, "steps": ["Open the LIM page and the property file page above in your browser", "Enter the address and legal description shown", "Read the current fee and turnaround on the page, then pay as the page says",
                                          "Record the request below (date sent, follow-up date) and upload what arrives to this property"], "label": "Process, fees and turnaround are as found on the date shown; the property file fee was not found."}

def site_visit_form(parcel_id: int) -> dict:
    get_property(parcel_id); cat = field_catalogue()["fields"]
    return {"parcel_id": parcel_id, "fields": [{"field": f, "label": l, "type": cat[f]["type"], **({"values": cat[f]["values"]} if "values" in cat[f] else {})} for f, l in SITE_VISIT if f in cat],
            "note": "Each value you enter is written to the Property Record at CONFIRMED with source 'site visit <date>'. Leave a box blank if you did not measure it: blanks are never written."}

def submit_site_visit(parcel_id: int, values: dict, visitor: str | None = None) -> dict:
    get_property(parcel_id); allowed = {f for f, _ in SITE_VISIT}; bad = [k for k in values if k not in allowed]
    if bad: raise HTTPException(422, f"not on the site visit form: {bad}")
    written = []
    with conn() as c:
        for f, v in values.items():
            if v in (None, ""): continue
            set_fact(c, parcel_id, f, v, f"site visit {date.today().isoformat()}" + (f" by {visitor}" if visitor else ""), "CONFIRMED", "site visit form"); written.append(f)
        c.commit()
    return {"written": written, "record": get_property(parcel_id)["lowest_confidence"]}

def log_request(parcel_id: int, kind: str, recipient: str | None, sent_on: date | None, follow_up_on: date | None, note: str | None) -> dict:
    get_property(parcel_id)
    if kind not in ("owner_agent", "council_file"): raise HTTPException(422, "kind must be owner_agent or council_file")
    if sent_on: approvals.require("plan_request_sent", "property", parcel_id, f"Record a {kind} plan request as sent on {sent_on}" + (f" to {recipient}" if recipient else ""), email(parcel_id)["text"] if kind == "owner_agent" else None)
    with conn() as c:
        r = c.execute("INSERT INTO core.rh_plan_request (parcel_id, kind, recipient, sent_on, follow_up_on, status, note) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                      (parcel_id, kind, recipient, sent_on, follow_up_on, "sent" if sent_on else "drafted", note)).fetchone(); c.commit()
    return list_requests(parcel_id)

def set_request_status(rid: int, status: str) -> dict:
    if status not in ("drafted", "sent", "received", "reviewed", "closed"): raise HTTPException(422, "bad status")
    with conn() as c:
        r = c.execute("UPDATE core.rh_plan_request SET status=%s WHERE id=%s RETURNING parcel_id", (status, rid)).fetchone(); c.commit()
    if not r: raise HTTPException(404, "no such request")
    return list_requests(r["parcel_id"])

def list_requests(parcel_id: int) -> list[dict]:
    with conn() as c: rows = c.execute("SELECT * FROM core.rh_plan_request WHERE parcel_id=%s ORDER BY id DESC", (parcel_id,)).fetchall()
    today = date.today()
    return [{**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}, "follow_up_due": bool(r["follow_up_on"] and r["status"] == "sent" and r["follow_up_on"] <= today)} for r in rows]
