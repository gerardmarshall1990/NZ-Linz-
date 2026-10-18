"""Digest and alerts (MASTER_SPEC Part 6.3): what changed since a date, in the app only (nothing is emailed: outreach is off). New listings with verdicts and achievable offer multiples, rent changes, removals,
saved-search matches, source coverage, and what is due (plan request follow-ups, overdue RFIs, approvals waiting). DEMO listings are marked."""
from datetime import date, timedelta
from fastapi import HTTPException
from . import approvals, listings, plan_request, rfi
from .db import conn

def save_search(name: str, filters: dict) -> dict:
    allowed = {"min_beds", "max_beds", "min_rent", "max_rent", "suburb", "source", "verdict"}
    bad = [k for k in filters if k not in allowed]
    if bad or not (name or "").strip(): raise HTTPException(422, f"name required; filters may only use {sorted(allowed)}")
    import json
    with conn() as c: r = c.execute("INSERT INTO core.user_saved_search (name, filters) VALUES (%s,%s::jsonb) RETURNING id", (name.strip(), json.dumps(filters))).fetchone(); c.commit()
    return {"id": r["id"], "name": name.strip(), "filters": filters}

def list_searches() -> list[dict]:
    with conn() as c: return c.execute("SELECT id, name, filters FROM core.user_saved_search ORDER BY id").fetchall()

def delete_search(sid: int) -> None:
    with conn() as c: c.execute("DELETE FROM core.user_saved_search WHERE id=%s", (sid,)); c.commit()

def _line(l, v):
    e = v.get("economics") or {}
    return {"listing_id": l["id"], "address": l["raw_address"], "suburb": l["suburb"], "beds": l["bedrooms"], "rent_per_week": float(l["rent_per_week"]) if l["rent_per_week"] is not None else None, "verdict": v["verdict"],
            "offer_multiple": e.get("rent_multiple_possible"), "demo": str(l["source_id"]).startswith("DEMO-"), "placeholder_banner": v.get("placeholder_banner")}

def build(since: date | None = None) -> dict:
    since = since or (date.today() - timedelta(days=1))
    with conn() as c:
        new = c.execute("SELECT * FROM core.user_listing WHERE first_seen >= %s AND status='active' ORDER BY id", (since,)).fetchall()
        removed = c.execute("SELECT * FROM core.user_listing WHERE status<>'active' AND last_seen >= %s ORDER BY id", (since,)).fetchall()
        hist = c.execute("""SELECT h.*, l.raw_address FROM core.user_listing_history h JOIN core.user_listing l ON l.id=h.listing_id WHERE h.changed_on >= %s ORDER BY h.id""", (since,)).fetchall()
        searches = c.execute("SELECT id, name, filters FROM core.user_saved_search ORDER BY id").fetchall()
    scored = [(l, listings.verdict_for(l["id"])) for l in new]
    lines = [_line(l, v) for l, v in scored]
    good = [x for x in lines if x["verdict"] in ("GREEN", "AMBER")]
    new_ids = {x["listing_id"] for x in lines}; matches = []
    for s in searches:
        res = listings.search(s["filters"]); hit = [o["listing"]["id"] for o in res["listings"] if o["listing"]["id"] in new_ids]
        if hit: matches.append({"search": s["name"], "listing_ids": hit})
    follow = []
    with conn() as c: parcels = [r["parcel_id"] for r in c.execute("SELECT DISTINCT parcel_id FROM core.rh_plan_request WHERE status='sent' AND follow_up_on <= current_date").fetchall()]
    for p in parcels: follow += [r for r in plan_request.list_requests(p) if r["follow_up_due"]]
    return {"since": since.isoformat(), "new_listings": lines, "good_new": good, "price_changes": [{"address": h["raw_address"], "field": h["field"], "old": h["old_value"], "new": h["new_value"], "on": h["changed_on"].isoformat()} for h in hist],
            "removed": [{"address": l["raw_address"], "last_seen": l["last_seen"].isoformat()} for l in removed], "saved_search_matches": matches,
            "due": {"plan_request_follow_ups": [{"parcel_id": f["parcel_id"], "recipient": f["recipient"], "follow_up_on": f["follow_up_on"]} for f in follow], "overdue_rfis": [{"id": r["id"], "summary": r["summary"], "due_on": r["due_on"]} for r in rfi.overdue_all()],
                    "approvals_waiting": len(approvals.pending())},
            "source_coverage": listings.sources()["coverage_warning"], "label": "In-app digest. Nothing is emailed. Verdicts are screening labels and show their placeholders."}

def run_and_store(since: date | None = None) -> dict:
    import json
    d = build(since)
    with conn() as c: r = c.execute("INSERT INTO core.user_digest (since, payload) VALUES (%s,%s::jsonb) RETURNING id", (d["since"], json.dumps(d, default=str))).fetchone(); c.commit()
    return {"id": r["id"], **d}

def history(limit: int = 20) -> list[dict]:
    with conn() as c: rows = c.execute("SELECT id, generated_at, since, payload FROM core.user_digest ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
    return [{"id": r["id"], "generated_at": r["generated_at"].isoformat(), "since": r["since"].isoformat(), "new": len(r["payload"]["new_listings"]), "good_new": len(r["payload"]["good_new"])} for r in rows]
