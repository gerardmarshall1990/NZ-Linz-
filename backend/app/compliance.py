"""Compliance gap analysis (MASTER_SPEC Part 3 section 4.2, Part 7 step 6). Statuses: PASS, FAIL, NEEDS_PROFESSIONAL, UNKNOWN, NOT_APPLICABLE.
A numeric requirement with no loaded value is never PASS: it is UNKNOWN with 'requirement not loaded'. Hazard data is not read (decision 13: information only for conversions).
Zone and activity status comes from the plan rules corpus with its citation; which AUP activity a rest home falls under is a planner's call."""
import json
from . import bedrules
from .db import conn
from .facts import get_property
from .layout import get_option

ACT_PATTERNS = ("Supported residential care%", "Healthcare facilities%", "Conversion of a building or part of a building to%", "Visitor accommodation%", "Boarding houses%")

def _facts(parcel_id):
    rec = get_property(parcel_id); fs = rec["facts"]
    return {x["field"]: x for x in fs} if isinstance(fs, list) else fs

def _req(r): return {"id": r["id"], "topic": r["topic"], "clause": r["clause"], "source": r["source"], "signs_off": r["signs_off"], "evidence": r["evidence"]}

def run(parcel_id: int, option_id: int | None = None) -> dict:
    facts = _facts(parcel_id); opt = get_option(option_id) if option_id else None
    if opt and opt["parcel_id"] != parcel_id: raise ValueError("option belongs to another property")
    val = lambda k: (facts.get(k) or {}).get("value"); conf = lambda k: (facts.get(k) or {}).get("confidence")
    checks = []
    def add(r, status, detail, quantity=None, **kw):
        checks.append({**_req(r), "status": status, "detail": detail, "quantity": quantity, "inputs_confidence": kw.get("conf"), "deal_breaker": kw.get("deal_breaker", False)})
    for r in bedrules.requirements():
        k = r["check"]; thr = r.get("value")
        if k == "min_numeric":
            v = val(r["fact"])
            if v is None: add(r, "UNKNOWN", f"{r['fact']} is not known: needs a calibrated, confirmed plan or a measurement")
            elif thr is None: add(r, "NEEDS_PROFESSIONAL", f"measured {v} {r['unit']} ({conf(r['fact'])}); the requirement value is not loaded (official document not available to the tool)", conf=conf(r["fact"]))
            else: add(r, "PASS" if float(v) >= float(thr) else "FAIL", f"measured {v} vs required {thr} {r['unit']}", conf=conf(r["fact"]))
        elif k == "ensuite_per_room":
            if not opt: add(r, "UNKNOWN", "generate layout options first")
            else:
                need = sum(1 for lv in opt["levels"] for a in lv["rooms"] if a["items"] and any("ensuite" in i for i in a["items"]))
                add(r, "FAIL" if need else "PASS", f"{need} resident room(s) need a new or converted ensuite in option '{opt['scenario']}'" if need else "every resident room in this option has an existing adjacent ensuite", quantity={"ensuites_to_add": need})
        elif k == "room_area":
            m = bedrules.reg("min_resident_room_m2")
            if m is None: add(r, "NEEDS_PROFESSIONAL", "minimum resident room area: not stated in the standard (you checked your copy); a professional confirms what applies" if bedrules.state("min_resident_room_m2") == "not_stated" else "minimum resident room area not loaded (Ngā Paerewa not available to the tool)")
            else: add(r, "UNKNOWN", "applied in the layout engine")
        elif k == "communal_area":
            add(r, "NEEDS_PROFESSIONAL" if bedrules.reg("communal_area_per_bed_m2") is None else "UNKNOWN", "communal area per bed requirement not loaded" if bedrules.reg("communal_area_per_bed_m2") is None else "compute from calibrated plan")
        elif k == "roles_present":
            have = {"kitchen": val("kitchens"), "laundry": val("laundries"), "lounge/dining": val("lounge_dining_areas"), "office": val("staff_office_rooms")}
            unk = [a for a, b in have.items() if b is None]; missing = [a for a, b in have.items() if b == 0]
            if unk: add(r, "UNKNOWN", f"counts not known for: {', '.join(unk)}")
            elif missing: add(r, "FAIL", f"missing: {', '.join(missing)}: a room will be converted (see option)", quantity={"missing_roles": missing})
            else: add(r, "NEEDS_PROFESSIONAL", "all present; size and fit-out adequacy need the designer", conf=conf("kitchens"))
        elif k == "presence_then_professional":
            vals = {f: val(f) for f in r["facts"]}
            unk = [f for f, v in vals.items() if v is None]
            if unk: add(r, "UNKNOWN", f"not recorded: {', '.join(unk)}")
            elif any(v in ("none", False) for v in vals.values()): add(r, "FAIL", f"recorded: {vals}; the new use likely needs this: fire engineer to confirm", quantity={"absent": [f for f, v in vals.items() if v in ("none", False)]})
            else: add(r, "NEEDS_PROFESSIONAL", f"recorded: {vals}; adequacy for the new use needs a professional")
        elif k == "lift":
            levels = len(opt["levels"]) if opt else None; lifts = (val("lifts") or {}).get("count") if val("lifts") else None
            st = val("storeys_per_building")
            if levels is None and st is None: add(r, "UNKNOWN", "number of levels not known")
            elif (levels or 0) > 1 or (st and str(st) not in ("1", "[1]")):
                if lifts is None: add(r, "UNKNOWN", "multi-level: lift presence not recorded")
                elif lifts == 0: add(r, "FAIL", "more than one level and no lift recorded; whether one is required depends on where residents are housed", deal_breaker=True, quantity={"lifts_to_add": "tbd"})
                else: add(r, "NEEDS_PROFESSIONAL", f"{lifts} lift(s) recorded; size, capacity and access need a professional")
            else: add(r, "NOT_APPLICABLE", "single level")
        elif k == "fact_present":
            v = val(r["fact"]); add(r, "UNKNOWN" if v is None else "NEEDS_PROFESSIONAL", "not recorded" if v is None else f"recorded: {v}")
        elif k == "unit_title":
            tt = val("title_type")
            if tt is None: add(r, "UNKNOWN", "title type not known")
            elif "unit" in str(tt).lower() or "cross lease" in str(tt).lower(): add(r, "FAIL", f"title type '{tt}': several owners may need to agree; legal path to certification must be checked", deal_breaker=True)
            else: add(r, "PASS", f"title type: {tt}", conf=conf("title_type"))
        else: add(r, "NEEDS_PROFESSIONAL", "engineering judgement: brief generated for the named professional")
    # zone and activity status (plan rules corpus, cited)
    with conn() as c:
        site = c.execute("SELECT zone_name, pc120_depends FROM core.sites WHERE parcel_id = %s", (parcel_id,)).fetchone()
        zone = (site or {}).get("zone_name"); acts = []
        if zone:
            acts = c.execute("""SELECT activity, status_class, section_ref, source_url FROM analytics.rules WHERE topic = 'activity_status' AND status = 'operative' AND zone = %s
                                AND (activity ILIKE ANY (%s)) ORDER BY section_ref LIMIT 12""", (zone, list(ACT_PATTERNS))).fetchall()
    z = {"id": "zone_activity", "topic": "Planning", "clause": None, "source": "Auckland Unitary Plan operative activity tables", "signs_off": "planner", "evidence": "planning assessment"}
    if not zone: add(z, "UNKNOWN", "zone not known")
    else: add(z, "NEEDS_PROFESSIONAL", f"zone: {zone}. Related activity rows are listed; which one a rest home falls under is a planner's call, not decided here. Plan Change 120 may change this." + (" PC120 flagged for this site." if (site or {}).get("pc120_depends") else ""),
              quantity={"activity_rows": [{"activity": a["activity"], "status": a["status_class"], "ref": a["section_ref"]} for a in acts]})
    counts = {s: sum(1 for c_ in checks if c_["status"] == s) for s in ("PASS", "FAIL", "NEEDS_PROFESSIONAL", "UNKNOWN", "NOT_APPLICABLE")}
    res = {"parcel_id": parcel_id, "option_id": option_id, "scenario": opt["scenario"] if opt else None, "counts": counts, "checks": checks,
           "deal_breakers": [c_["id"] for c_ in checks if c_["deal_breaker"]],
           "hazard_note": "Natural hazard flags are information only for conversions of existing buildings and do not affect these checks.",
           "label": "Screening result. Not a compliance opinion: every NEEDS_PROFESSIONAL item must be confirmed by the named professional."}
    with conn() as c:
        row = c.execute("INSERT INTO core.rh_check_run (parcel_id, option_id, results) VALUES (%s,%s,%s::jsonb) RETURNING id", (parcel_id, option_id, json.dumps(res))).fetchone(); c.commit()
    return {"id": row["id"], **res}
