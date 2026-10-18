"""Offer generator (MASTER_SPEC Part 4 section 6, Part 6.5; behind the offer_letters_enabled flag): a one-page offer summary, a letter, an email draft and a JV / lease TERMS SHEET (not a contract) from a saved offer scenario.
Guardrails in code: a 'LAWYER REVIEW REQUIRED' banner on every output; the rent offered is never above the walk-away rent; a lead must be contactable and not on the do-not-contact list; email drafts carry the sender identity and an unsubscribe line; no promise words
(no promise of outcomes, returns or timelines) and consents and certification are described as conditions that may not be met; every version is kept; marking a document as sent needs an approval record. The app sends nothing."""
import json
from fastapi import HTTPException
from . import approvals, audit, crm, proposal
from .db import conn

BANNER = "LAWYER REVIEW REQUIRED. Illustrative terms from stated assumptions, not a contract and not advice. New Zealand's unsolicited electronic messages and privacy rules apply to any outreach: have a lawyer review the process before use."
UNSUB = "If you would prefer not to hear from us again, reply with the word UNSUBSCRIBE and we will not contact you again."
CONDITIONS = ["Building consent granted for the proposed alterations", "Resource consent, if the planner says it is needed", "Certification pathway confirmed with the designated auditing agency", "Finance, where relevant", "Landlord, mortgagee and insurer consents"]
OWNER_COMPANY = "[TO COMPLETE: your company name, address, phone and email]"

def _lead_ok(lead_id: int | None):
    if lead_id is None: return None
    l = crm.get(lead_id)
    if l["do_not_contact"]: audit.log("offer_refused", "lead", lead_id, {"why": "do-not-contact"}); raise HTTPException(409, "do-not-contact: no offer documents for this lead")
    if not l["contactable"]: raise HTTPException(409, "lead is not marked contactable (source and lawful basis first)")
    if l.get("counterparty_type") not in ("owner", "landlord", "property_manager", "trustees"): raise HTTPException(409, "the counterparty must be the owner, landlord, managing agent or trustees: never a tenant")
    return l

def _scenario(sid: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.rh_scenario WHERE id=%s AND kind='offer'", (sid,)).fetchone()
    if not r: raise HTTPException(404, "no such offer scenario")
    return r

def _ceiling_check(r: dict, rent: float | None):
    walk = r["output"].get("walk_away_rent_per_week")
    if rent is not None and (walk is None or rent > walk + 1e-9): raise HTTPException(422, f"the rent offered (${rent:,.0f}/week) is above the walk-away rent ({'not available' if walk is None else '$%s/week' % format(round(walk), ',')}): refused")
    return walk

def _version(kind, lead_id, parcel_id, sid) -> int:
    with conn() as c: return (c.execute("SELECT COALESCE(MAX(version),0)+1 AS v FROM core.user_offer_doc WHERE kind=%s AND COALESCE(lead_id,0)=COALESCE(%s,0) AND COALESCE(scenario_id,0)=COALESCE(%s,0)", (kind, lead_id, sid)).fetchone())["v"]

def create(kind: str, scenario_id: int, mode: str, lead_id: int | None = None, sender: str | None = None, rent_offered: float | None = None, terms: dict | None = None) -> dict:
    if kind not in ("letter", "email", "one_page", "terms_sheet"): raise HTTPException(422, "kind must be letter, email, one_page or terms_sheet")
    _lead_ok(lead_id); r = _scenario(scenario_id); walk = _ceiling_check(r, rent_offered); pk = proposal.build(scenario_id, mode); t = terms or {}
    L = [f"**{BANNER}**", ""]
    if r["output"].get("placeholder_banner"): L += [f"**{r['output']['placeholder_banner']}.**", ""]
    if kind == "terms_sheet":
        L += ["# Terms sheet (not a contract)", "", "| Term | Proposed |", "|--|--|", f"| Structure | {proposal.MODE_NAME[mode]} |", f"| Base rent offered per week | {('$%s' % format(round(rent_offered), ',')) if rent_offered is not None else '[TO COMPLETE]'} (never above the walk-away rent) |",
              f"| Term and renewals | {t.get('term') or '[TO COMPLETE]'} |", f"| Rent-free or reduced rent during works | {t.get('rent_free') or '[TO COMPLETE]'} |", f"| Escalation | {t.get('escalation') or '[TO COMPLETE]'} |", f"| Who funds the retrofit and how it is recovered | {t.get('retrofit_funding') or '[TO COMPLETE]'} |",
              f"| Ownership of fit-out | {t.get('fit_out') or '[TO COMPLETE]'} |", f"| Make-good | {t.get('make_good') or '[TO COMPLETE]'} |", "| Conditions precedent | " + "; ".join(CONDITIONS) + " |", f"| Long-stop dates | {t.get('long_stop') or '[TO COMPLETE]'} |",
              f"| Termination rights | {t.get('termination') or '[TO COMPLETE]'} |", f"| Insurance | {t.get('insurance') or '[TO COMPLETE]'} |", "| Access before the lease goes unconditional | Access for plan capture and for professionals |",
              f"| Māori land approvals | {t.get('maori_land') or '[TO COMPLETE: where relevant]'} |", "", "Net operating profit for any sharing is defined in the assumptions of the attached proposal. Consents and certification are conditions that may not be met."]
    else:
        body = pk["markdown"]
        if kind == "one_page": L += [body]
        else:
            L += [f"{'Subject: A proposal for your property' if kind == 'email' else '# Letter'}", "", "Dear [TO COMPLETE: name],", "", "I am writing about your property and a way it could earn more as a rest home, operated by professionals. A summary is below. Consents and certification are conditions that may not be met, and every figure is an illustration, not a promise.", "",
                  body, "", f"{sender or OWNER_COMPANY}"]
            if kind == "email": L += ["", UNSUB]
    md = "\n".join(L); v = _version(kind, lead_id, r["parcel_id"], scenario_id)
    with conn() as c: d = c.execute("INSERT INTO core.user_offer_doc (lead_id, parcel_id, scenario_id, kind, version, body_md) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id", (lead_id, r["parcel_id"], scenario_id, kind, v, md)).fetchone(); c.commit()
    audit.log("offer_doc", "lead" if lead_id else "parcel", lead_id or r["parcel_id"], {"doc_id": d["id"], "kind": kind, "version": v})
    return {"id": d["id"], "kind": kind, "version": v, "markdown": md, "walk_away_rent_per_week": walk, "label": "Draft only. The app sends nothing."}

def versions(lead_id: int | None = None, scenario_id: int | None = None) -> list[dict]:
    with conn() as c: rows = c.execute("SELECT id, lead_id, scenario_id, kind, version, status, created_at FROM core.user_offer_doc WHERE (%s::bigint IS NULL OR lead_id=%s) AND (%s::bigint IS NULL OR scenario_id=%s) ORDER BY id DESC", (lead_id, lead_id, scenario_id, scenario_id)).fetchall()
    return [{**r, "created_at": r["created_at"].isoformat()} for r in rows]

def get(doc_id: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.user_offer_doc WHERE id=%s", (doc_id,)).fetchone()
    if not r: raise HTTPException(404, "no such document")
    return {**r, "created_at": r["created_at"].isoformat()}

def mark_sent(doc_id: int) -> dict:
    d = get(doc_id)
    if d["status"] == "sent_recorded": raise HTTPException(409, "already recorded as sent")
    if d["lead_id"]: _lead_ok(d["lead_id"])
    approvals.require("owner_message", "offer_doc", doc_id, f"Record offer document {d['kind']} v{d['version']} as sent to the owner", d["body_md"])
    with conn() as c: c.execute("UPDATE core.user_offer_doc SET status='sent_recorded' WHERE id=%s", (doc_id,)); c.commit()
    audit.log("offer_sent_recorded", "offer_doc", doc_id, {}); return get(doc_id)
