"""Owner proposal pack (MASTER_SPEC Part 6.5): plain English, one page plus an assumptions appendix, 'Lawyer review required' banner, downside cases always shown.
Wording rules: a payment the owner of this tool chooses to offer is a 'minimum payment'; the pack never uses promise words, never states or implies that consent, certification or occupancy will be achieved."""
import json
from fastapi import HTTPException
from .db import conn

BANNER = "LAWYER REVIEW REQUIRED. Illustrative projections from stated assumptions, not a contract and not advice."
MODE_NAME = {"fixed": "Fixed rent", "jv": "Profit share", "hybrid": "Minimum payment plus profit share"}
CONDITIONS = ["Building consent granted for the proposed alterations", "Resource consent if the planner says it is needed", "Certification pathway confirmed with the designated auditing agency",
              "Finance and lender consent where relevant", "Landlord, mortgagee and insurer consents"]
NEEDS_FROM_OWNER = ["Access for plan capture and for professionals before the agreement goes unconditional", "Your landlord, mortgagee and insurer confirmations",
                    "Vacant possession, with any tenancy ended lawfully by you (we never contact tenants)"]

def _money(x): return "n/a" if x is None else f"${x:,.0f}"

def build(scenario_id: int, mode: str, address: str | None = None) -> dict:
    with conn() as c:
        r = c.execute("SELECT * FROM core.rh_scenario WHERE id = %s AND kind = 'offer'", (scenario_id,)).fetchone()
        if not r: raise HTTPException(404, "no such offer scenario")
        site = c.execute("SELECT address FROM core.sites WHERE parcel_id = %s", (r["parcel_id"],)).fetchone()
    o = r["output"]; m = (o.get("modes") or {}).get(mode)
    if not m or m.get("blocked"): raise HTTPException(422, f"mode '{mode}' is not available for this scenario (inputs missing or blocked)")
    own, cur = m["owner"], m["owner"]["current_income_used"]
    L = [f"**{BANNER}**", "", f"# Proposal summary: {site['address'] if site else address}", "",
         f"## What is proposed\n{MODE_NAME[mode]}. " + {
             "fixed": lambda: f"We would pay a fixed rent of {_money(own['weekly_at_stabilisation'])} per week, which is {own['multiple_of_current']:.1f} times your current income of {_money(cur)} per week.",
             "jv": lambda: f"You would receive {m['terms']['s']:.0%} of the net operating profit once the home is operating (about {_money(own['weekly_at_stabilisation'])} per week at stabilisation in our base case, {own['multiple_of_current']:.1f} times {_money(cur)}).",
             "hybrid": lambda: f"We would pay a minimum payment of {_money(m['terms']['floor'])} per week from the start, plus {m['terms']['s_h']:.0%} of net operating profit above {_money(m['terms']['threshold'])} per week."}[mode](),
         "", "## What you receive at each stage (per week)", "| Stage | Your income | Your current income |", "|---|---|---|",
         f"| During consent, works, audit and fill | {_money(own['weekly_during_conversion'])} | {_money(cur)} |", f"| Stabilised (base case) | {_money(own['weekly_at_stabilisation'])} | {_money(cur)} |",
         f"| Downside: occupancy 60% | {_money(own['cases']['occ_60'])} | {_money(cur)} |", f"| Downside: net operating profit 30% lower | {_money(own['cases']['n_lower'])} | {_money(cur)} |",
         "", f"Over the first 12 months your income would be {_money(own['cumulative_12m'])} compared with {_money(cur * 52)} if you leave the property as it is; over 24 months, {_money(own['cumulative_24m'])} compared with {_money(cur * 104)}.",
         "", "## What happens during consent, works, audit and sign-off", "The building is altered under a building consent prepared by qualified professionals and the operator applies for certification. " + (
             "During this period " + (f"you would receive the minimum payment shown above." if own["weekly_during_conversion"] else "you would not receive any payment under a pure profit share.")),
         "", "## What we need from you"] + [f"- {x}" for x in NEEDS_FROM_OWNER] + ["", "## Conditions before the agreement becomes unconditional"] + [f"- {x}" for x in CONDITIONS] + [
         "- A long-stop date; if a condition is not met by then, the agreement ends on the terms the lawyers agree.",
         "", "## Important", "Every number is an illustration from the assumptions below and may be wrong. Consents, certification and occupancy are decided by others, and this document makes no promise about them.",
         "", "---", "## Assumptions appendix"] + [f"- {a}" for a in o.get("assumptions", [])] + [f"- Confidence tier of the inputs: {o.get('confidence') or 'not stated'}.",
         f"- Net operating profit shared is defined as: revenue minus food, staffing (with roster coverage), clinical lead and manager, utilities, insurance, compliance and certification, supplies, repairs and maintenance and other agreed operating costs, before the owner's share.",
         "- " + o["legal_flags"]]
    if o.get("banner_confidence"): L.insert(1, f"*{o['banner_confidence']}*")
    return {"scenario_id": scenario_id, "mode": mode, "markdown": "\n".join(L)}

def pdf(markdown: str) -> bytes:
    import pymupdf
    doc = pymupdf.open(); rect = pymupdf.Rect(48, 48, 547, 794); page = doc.new_page(); lines = markdown.replace("**", "").replace("#", "").split("\n"); y = 48
    for ln in lines:
        for chunk in (pymupdf.get_text_length(ln, fontsize=9) // 495 + 1,):
            h = 12 * int(chunk)
            if y + h > 794: page = doc.new_page(); y = 48
            page.insert_textbox(pymupdf.Rect(48, y, 547, y + h + 2), ln, fontsize=9); y += h
    return doc.tobytes()
