"""Evidence gaps (MASTER_SPEC 7.3 step 4): what a remote plan reading cannot know. Each gap is NEEDS_PROFESSIONAL with who confirms it, unless you record otherwise."""
from fastapi import HTTPException
from .db import conn
from .facts import get_property

GAPS = [  # key, title, why it cannot be known remotely, who confirms, relevant when
    ("wall_construction_fire_ratings", "Wall construction and fire ratings", "Plans rarely show lining, framing or fire resistance ratings; they cannot be read from photos.", "fire engineer / designer", None),
    ("structure_type", "Structural system and condition", "Load-bearing walls, bracing, foundations and any past alterations are not visible on a plan.", "structural engineer", None),
    ("concealed_services", "Concealed services", "Pipes, cables, ducts and their capacity are hidden in walls, ceilings and floors.", "services engineer / electrician / plumber", None),
    ("roof_subfloor_condition", "Roof space and sub-floor condition", "Needs access: moisture, framing, insulation and pests are not on plans.", "building inspector / structural engineer", None),
    ("asbestos", "Asbestos check before alterations", "Buildings built before 2000 may contain asbestos; a survey is required before demolition or alterations.", "licensed asbestos assessor", "pre2000"),
    ("service_capacity", "Service capacity (power, water, wastewater)", "Capacity for the new use is not on the plans and needs the network provider or an engineer.", "services engineer", None),
    ("existing_fire_systems", "Existing fire alarm, sprinklers and emergency lighting", "Presence may be on record, but adequacy and condition need inspection and records.", "fire engineer / IQP", None),
    ("exits_escape_routes", "Exits and escape routes", "Exit counts, travel distances and escape widths are not read from the model in this version.", "fire engineer", None),
    ("levels_not_confirmed", "Levels or buildings not yet confirmed", "Only confirmed plan levels are counted. Anything else on the site is unknown.", "you (upload and confirm remaining plans)", "unconfirmed_levels"),
    ("unscaled_levels", "Levels without a scale", "No scale, no measurements: areas, corridor and door widths stay blank.", "you (calibrate the plan)", "unscaled"),
    ("consented_plans_match", "Do the plans match the building as built?", "Council or owner plans may be out of date or never built as drawn.", "scan visit or designer", "plans_on_file"),
]

def compute(parcel_id: int) -> dict:
    rec = get_property(parcel_id); f = {x["field"]: x for x in rec["facts"]} if isinstance(rec["facts"], list) else rec["facts"]
    with conn() as c:
        x = c.execute("""SELECT x.id, x.calibrated, x.status FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id = x.upload_id WHERE u.parcel_id = %s AND x.superseded_by IS NULL""", (parcel_id,)).fetchall()
        st = {r["gap_key"]: r for r in c.execute("SELECT gap_key, status, note, updated_at FROM core.rh_evidence_gap_status WHERE parcel_id = %s", (parcel_id,)).fetchall()}
        ev = c.execute("SELECT evidence_level FROM core.rh_property WHERE parcel_id = %s", (parcel_id,)).fetchone()["evidence_level"]
    yb = f.get("year_built", {}).get("value")
    cond = {"pre2000": yb is None or int(yb) < 2000, "unconfirmed_levels": any(r["status"] != "human_confirmed" for r in x) or not x,
            "unscaled": any(not r["calibrated"] for r in x if r["status"] == "human_confirmed"), "plans_on_file": ev == "PLANS_ON_FILE"}
    out = []
    for key, title, why, who, when in GAPS:
        if when and not cond[when]: continue
        s = st.get(key)
        extra = " (year built unknown: assume pre-2000 until shown otherwise)" if key == "asbestos" and yb is None else ""
        out.append({"key": key, "title": title, "why": why + extra, "confirmed_by": who, "status": s["status"] if s else "NEEDS_PROFESSIONAL", "note": s["note"] if s else None})
    return {"parcel_id": parcel_id, "evidence_level": ev, "gaps": out, "open": sum(1 for g in out if g["status"] in ("NEEDS_PROFESSIONAL", "REQUESTED"))}

def set_status(parcel_id: int, key: str, status: str, note: str | None):
    if key not in {g[0] for g in GAPS}: raise HTTPException(404, "unknown gap")
    get_property(parcel_id)
    with conn() as c:
        c.execute("""INSERT INTO core.rh_evidence_gap_status (parcel_id, gap_key, status, note) VALUES (%s,%s,%s,%s)
                     ON CONFLICT (parcel_id, gap_key) DO UPDATE SET status = EXCLUDED.status, note = EXCLUDED.note, updated_at = now()""", (parcel_id, key, status, note)); c.commit()
    return compute(parcel_id)
