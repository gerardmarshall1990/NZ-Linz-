"""Briefs for the engineers (MASTER_SPEC 7.3 step 6): fire, structural, accessibility, services. Draft text built only from recorded facts, the chosen layout option, the compliance run and
the evidence gaps. They ask questions; they do not answer them. No signature, registration number, producer statement or conclusion is ever written."""
import json
from fastapi import HTTPException
from . import gaps
from .compliance import run as run_checks, _facts
from .db import conn
from .layout import get_option
from .stamp import STAMP

KINDS = {
    "fire": ("Fire engineering brief", "fire engineer", ["exits_and_escape", "fire_risk_group", "sprinklers_alarm", "emergency_lighting"], ["wall_construction_fire_ratings", "existing_fire_systems", "exits_escape_routes"],
             ["What fire risk group applies to the proposed rest home use, and how does it compare with the current use?", "Are the existing exits, travel distances and escape widths adequate for residents who need assistance to evacuate?",
              "Is a sprinkler or detection system required or upgradable, and what compartmentation or fire-rated linings are needed?", "Is an alternative solution (fire engineering design) needed? If so, what information do you need from site?"]),
    "structural": ("Structural brief", "structural engineer", ["structure", "lift_levels"], ["structure_type", "roof_subfloor_condition"],
                   ["Are the walls proposed for removal or opening load-bearing or bracing walls?", "What investigation do you need (drawings, opening-up, site visit) to assess the building for the new use?", "Is the building's structure adequate for the new occupancy loads?"]),
    "accessibility": ("Accessibility brief", "designer / accessibility consultant", ["corridor_width", "door_width", "level_access", "lift_levels", "min_resident_room_area"], ["levels_not_confirmed", "unscaled_levels"],
                      ["Do corridor and door clear widths, turning space and thresholds meet the access requirements for the new use?", "Where does a ramp, lift or platform lift fit, if needed?", "Which entrances and communal areas need level access?"]),
    "services": ("Services brief", "services engineer", ["nurse_call", "kitchen_laundry_communal", "compliance_schedule"], ["concealed_services", "service_capacity", "asbestos"],
                 ["Is the electrical supply and switchboard adequate for the new use, including nurse call and emergency lighting?", "Are water, hot water, drainage and ventilation adequate for ensuites, kitchen and laundry?", "What is the current compliance schedule / BWOF status and what systems must be added?"]),
}

def build(parcel_id: int, option_id: int, kind: str) -> dict:
    if kind not in KINDS: raise HTTPException(422, f"kind must be one of {list(KINDS)}")
    opt = get_option(option_id)
    if opt["parcel_id"] != parcel_id: raise HTTPException(404, "option belongs to another property")
    title, who, req_ids, gap_keys, qs = KINDS[kind]
    facts = _facts(parcel_id); chk = run_checks(parcel_id, option_id); gp = gaps.compute(parcel_id)
    site = None
    with conn() as c: site = c.execute("SELECT address, suburb, zone_name, title_type FROM core.sites WHERE parcel_id = %s", (parcel_id,)).fetchone()
    L = [f"**{STAMP}**", "", f"# {title} (draft, for {who})", f"Property: {site['address']} ({site['suburb']}), parcel {parcel_id}. Zone: {site['zone_name']}.", "",
         "This is a request for professional input prepared from recorded information. It states no conclusion on compliance. Producer statements, reports and signatures are NOT produced here: they are upload slots, completed by the professional.", "",
         "## Proposed change", f"Rest home layout option '{opt['scenario']}': {opt['description']} Beds in option: {opt['beds']} across {opt['resident_rooms']} resident rooms. Binding constraint: {opt['binding_constraint']}.",
         f"New-work items listed on the plan: {opt['new_work_items']}. Rooms changing use: {sum(1 for lv in opt['levels'] for a in lv['rooms'] if a['action'] == 'convert')}."]
    if opt["warnings"]: L += ["", "Caveats on the option:"] + [f"- {w}" for w in opt["warnings"]]
    L += ["", "## What is recorded (value, source, confidence)"]
    for f, v in sorted(facts.items()): L.append(f"- {f}: {json.dumps(v['value'])} ({v['source']}; {v['confidence']})")
    L += ["", "## Screening checks relevant to you"]
    for c_ in chk["checks"]:
        if c_["id"] in req_ids: L.append(f"- **{c_['topic']}: {c_['id']}** [{c_['status']}] {c_['detail']} (source to confirm: {c_['source']})")
    L += ["", "## What cannot be known remotely"]
    for g in gp["gaps"]:
        if g["key"] in gap_keys: L.append(f"- {g['title']} [{g['status']}]: {g['why']}")
    L += ["", "## Questions for you"] + [f"{i}. {q}" for i, q in enumerate(qs, 1)]
    L += ["", "## Attachments to send", "- Drawing set for the option (DXF and PDF, stamped DRAFT)", "- Confirmed plan reading and Property Record export (CSV)",
          "", "## Upload slots (to be completed by the professional; status starts as requested)", "- Signed statement / report from the author: `requested`", "- Author's registration check against the Council register: `not yet checked`"]
    body = "\n".join(L)
    with conn() as c:
        r = c.execute("INSERT INTO core.rh_brief (parcel_id, option_id, kind, body_md) VALUES (%s,%s,%s,%s) RETURNING id, created_at", (parcel_id, option_id, kind, body)).fetchone(); c.commit()
    return {"id": r["id"], "kind": kind, "title": title, "for": who, "body_md": body}
