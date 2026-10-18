"""Building consent pack (MASTER_SPEC Part 7 step 4, 7.1, 8.4). Built to config/building_consent_checklist.yaml, which is NOT yet Council-verified (council_verified: false), so 'ready to lodge' is refused until it is.
Every document this module generates carries the DRAFT stamp. Producer statements, fire reports, certificates and signatures are upload slots only: no code path writes one.
Auckland Council's lodgement is a portal: the Application data sheet lists every field in a fixed order for typing in; the order is NOT verified against the live portal."""
import hashlib, io, json, re, zipfile
from datetime import date, datetime
from functools import lru_cache
import yaml
from fastapi import HTTPException
from . import drawings, ps_register
from .compliance import run as run_checks, _facts
from .config import ROOT, upload_dir
from .db import conn
from .facts import get_property
from .layout import get_option
from .model_view import confirmed_levels
from .pack_pdf import md_to_pdf
from .stamp import STAMP
from .uploads import detect_type, safe_name, MAX_UPLOAD_BYTES

DYNAMIC = {"cover_index", "lodgement_checklist", "drawings", "fee_estimate"}      # no [TO COMPLETE] scan: they describe the pack itself (or have their own rule)
TC = re.compile(r"\[TO COMPLETE: [^\]]+\]")
def tc(what: str) -> str: return f"[TO COMPLETE: {what}]"

@lru_cache
def checklist() -> dict: return yaml.safe_load((ROOT / "config" / "building_consent_checklist.yaml").read_text())
@lru_cache
def clauses() -> list[dict]: return yaml.safe_load((ROOT / "config" / "building_code_clauses.yaml").read_text())["clauses"]

# Fields typed in by the owner / agent / designer. Portal order is assumed (unverified): applicant, property, work, then professionals.
FIELD_SECTIONS = [
    ("Applicant (owner)", [("owner_name", "Owner full name"), ("owner_address", "Owner postal address"), ("owner_email", "Owner email"), ("owner_phone", "Owner phone")]),
    ("Agent (if any)", [("agent_name", "Agent name"), ("agent_email", "Agent email"), ("agent_phone", "Agent phone")]),
    ("Project", [("existing_use", "Existing use of the building"), ("estimated_work_value", "Estimated value of the building work (a QS's or builder's figure, not the screening estimate)"),
                 ("pim_reference", "Project Information Memorandum reference (if one was obtained)"), ("intended_start_date", "Intended start date")]),
    ("Professionals", [("designer_name", "Designer / architect name and company"), ("lbp_name", "Licensed building practitioner (restricted building work) name and LBP number")]),
]
# Entered by or for the designer / fire engineer (the app never fills these in for them)
PRO_FIELDS = {"cou_fire_group_existing": "fire engineer: existing fire risk group", "cou_fire_group_proposed": "fire engineer: proposed fire risk group", "cou_sprinklers_proposed": "fire engineer: sprinkler requirement",
              "cou_alarm_proposed": "fire engineer: alarm requirement", "cou_exits_proposed": "fire engineer: exits and escape", "spec_doors": "designer: door schedule", "spec_windows": "designer: window schedule",
              "spec_finishes": "designer: finishes schedule", "spec_fixtures": "designer: fixtures and fittings"}
FIELD_KEYS = {k for _, fs in FIELD_SECTIONS for k, _ in fs} | set(PRO_FIELDS)
def field_key_ok(k: str) -> bool: return k in FIELD_KEYS or bool(re.fullmatch(r"clause_(method|evidence)\.[A-Z]\d{0,2}", k))

# ------------------------------------------------------------------ build
def _pack(pack_id: int) -> dict:
    with conn() as c: p = c.execute("SELECT * FROM core.rh_pack WHERE id = %s", (pack_id,)).fetchone()
    if not p: raise HTTPException(404, "no such pack")
    return p

def _docs(pack_id: int) -> list[dict]:
    with conn() as c: return c.execute("SELECT * FROM core.rh_pack_doc WHERE pack_id = %s ORDER BY id", (pack_id,)).fetchall()

def build(parcel_id: int, option_id: int) -> dict:
    rec = get_property(parcel_id); opt = get_option(option_id)
    if opt["parcel_id"] != parcel_id: raise HTTPException(404, "option belongs to another property")
    cl = checklist(); run = run_checks(parcel_id, option_id)
    facts = {k: {"value": v["value"], "source": v["source"], "confidence": v["confidence"]} for k, v in rec["facts"].items()}
    inputs = {"site": rec["site"], "option": {k: opt[k] for k in ("id", "scenario", "beds", "resident_rooms", "description", "binding_constraint", "new_work_items", "warnings", "levels")},
              "facts": facts, "compliance_run_id": run["id"], "compliance": run["checks"], "fields": {}, "resolutions": {}, "built_at": datetime.now().isoformat(timespec="seconds")}
    with conn() as c:
        ver = (c.execute("SELECT COALESCE(MAX(version),0)+1 AS v FROM core.rh_pack WHERE parcel_id = %s", (parcel_id,)).fetchone())["v"]
        p = c.execute("INSERT INTO core.rh_pack (parcel_id, option_id, version, checklist_version, inputs) VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING id",
                      (parcel_id, option_id, ver, cl["checklist_version"], json.dumps(inputs, default=str))).fetchone()
        c.execute("UPDATE core.rh_pack SET status='superseded', superseded_by=%s WHERE parcel_id=%s AND id<>%s AND status<>'superseded'", (p["id"], parcel_id, p["id"]))
        for d in cl["documents"]:
            c.execute("""INSERT INTO core.rh_pack_doc (pack_id, doc_key, title, kind, folder, file_name, required, owner, source, statement_type, discipline) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                      (p["id"], d["key"], d["title"], d["kind"], d["folder"], d["file_name"], d["required"], d.get("owner"), d.get("source"), d.get("statement_type"), d.get("discipline")))
        c.commit()
    return get(p["id"])

def set_fields(pack_id: int, fields: dict, resolutions: dict | None = None) -> dict:
    p = _pack(pack_id)
    if p["status"] == "superseded": raise HTTPException(409, "this pack version is superseded: edit the current version")
    bad = [k for k in fields if not field_key_ok(k)]
    if bad: raise HTTPException(422, f"unknown field(s): {bad}")
    inp = p["inputs"]
    for k, v in fields.items():
        if v in (None, ""): inp["fields"].pop(k, None)
        else: inp["fields"][k] = str(v)[:500]
    for k, v in (resolutions or {}).items():
        if v: inp["resolutions"][k] = str(v)[:500]
        else: inp["resolutions"].pop(k, None)
    with conn() as c:
        c.execute("UPDATE core.rh_pack SET inputs=%s::jsonb, status=CASE WHEN status='ready_to_lodge' THEN 'draft' ELSE status END, ready_marked_at=NULL WHERE id=%s", (json.dumps(inp, default=str), pack_id)); c.commit()
    return get(pack_id)

def set_not_required(pack_id: int, doc_key: str, required: bool, reason: str | None) -> dict:
    p = _pack(pack_id)
    if p["status"] == "superseded": raise HTTPException(409, "superseded pack")
    if not required and not (reason or "").strip(): raise HTTPException(422, "a reason is required to mark a document not required")
    with conn() as c:
        r = c.execute("UPDATE core.rh_pack_doc SET required=%s, not_required_reason=%s WHERE pack_id=%s AND doc_key=%s RETURNING id", (required, None if required else reason.strip(), pack_id, doc_key)).fetchone()
        if not r: raise HTTPException(404, "no such document in this pack")
        c.execute("UPDATE core.rh_pack SET status='draft', ready_marked_at=NULL WHERE id=%s AND status='ready_to_lodge'", (pack_id,)); c.commit()
    return get(pack_id)

# ------------------------------------------------------------------ rendering (generated documents)
def _v(inp, k, fmt=lambda x: x):
    f = inp["facts"].get(k); return fmt(f["value"]) if f and f["value"] is not None else tc(f"{k.replace('_', ' ')}: not recorded")

def _pf(inp, k): return inp["fields"].get(k) or tc(PRO_FIELDS[k])

def _field(inp, k, label): return inp["fields"].get(k) or tc(label)

def _statement_line(doc, sts):
    live = [s for s in sts if s["doc_id"] == doc["id"] and not s["superseded"]]
    if not live: return "not uploaded"
    ok, why = statement_valid(live[0], doc)
    return "uploaded, valid" if ok else "uploaded, NOT valid: " + "; ".join(why)

def render(pack_id: int, doc_key: str) -> str:
    p = _pack(pack_id); inp = p["inputs"]; docs = _docs(pack_id); doc = next((d for d in docs if d["doc_key"] == doc_key), None)
    if not doc: raise HTTPException(404, "no such document in this pack")
    if doc["kind"] == "upload_slot": raise HTTPException(409, "this is an upload slot: the document is supplied by the named professional, not generated here")
    site, opt = inp["site"], inp["option"]; head = f"**{STAMP}**\n\n"
    if doc_key == "application_data":
        L = [head, f"# Application data sheet: {site['address']}", f"Pack version {p['version']}; checklist `{p['checklist_version']}` (Council-verified: {checklist()['council_verified']}).", "",
             "**This lists every field in the order the Council portal is expected to ask for it, to type in. The portal order is NOT verified against the live portal (the Council site could not be opened from here): follow the portal's own order and use this as the source of the values.**", ""]
        L += ["## Property", "| Field | Value | Source |", "|--|--|--|", f"| Street address | {site['address']}, {site['suburb']} | Council/LINZ data |", f"| Parcel ID (LINZ) | {site['parcel_id']} | LINZ |",
              f"| Record of title no. | {site.get('title_no') or tc('title number')} | LINZ |", f"| Title type | {site.get('title_type') or tc('title type')} | LINZ |", f"| Site area (m2) | {site.get('area_m2')} | LINZ |", f"| Zone | {site.get('zone_name') or tc('zone')} | Auckland Unitary Plan |", ""]
        for sec, fs in FIELD_SECTIONS:
            L += [f"## {sec}", "| Field | Value |", "|--|--|"] + [f"| {lbl} | {_field(inp, k, lbl)} |" for k, lbl in fs] + [""]
        L += ["## Proposed work", "| Field | Value |", "|--|--|", f"| Type of consent | Building consent: change of use to a rest home / residential care, with alterations |",
              f"| Proposed use | Rest home (residential care) |", f"| Number of beds proposed | {opt['beds']} |", f"| Resident rooms | {opt['resident_rooms']} |", f"| Storeys | {_v(inp, 'storeys_per_building')} |", f"| Gross floor area (m2) | {_v(inp, 'gfa_m2')} |", ""]
        return "\n".join(L)
    if doc_key == "owner_agent_details":
        L = [head, "# Owner and agent details", ""] + [f"- **{lbl}**: {_field(inp, k, lbl)}" for sec, fs in FIELD_SECTIONS[:2] for k, lbl in fs]
        return "\n".join(L)
    if doc_key == "project_description":
        rows = [(r["label"] or r["type"], r["action"], r.get("becomes") or "", "; ".join(r["items"])) for lv in opt["levels"] for r in lv["rooms"] if r["action"] == "convert" or r["items"]]
        L = [head, f"# Project description: {site['address']}", "", f"Conversion of the existing building to a rest home. Layout option **{opt['scenario']}**: {opt['description']}", "",
             f"- Beds: {opt['beds']} across {opt['resident_rooms']} resident rooms. Binding constraint: {opt['binding_constraint']}.", f"- Existing use: {_field(inp, 'existing_use', 'existing use of the building')}",
             f"- Year built: {_v(inp, 'year_built')}. Construction: {_v(inp, 'construction_type')}.", "", "## Work by room (from the layout option; room level only, wall and structural changes are the designer's)", "| Room | Action | Becomes | New-work items |", "|--|--|--|--|"]
        L += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows] or ["| (none) | | | |"]
        if opt["warnings"]: L += ["", "Caveats on the option:"] + [f"- {w}" for w in opt["warnings"]]
        return "\n".join(L)
    if doc_key == "change_of_use":
        L = [head, "# Change of use: existing versus proposed", "", "Section 115 of the Building Act requires the building to comply as nearly as reasonably practicable with the Code provisions that matter for the new use; the Council's guidance (AC2205) asks for an existing-versus-new comparison. This sheet sets out what is recorded; **the compliance position is the fire engineer's and designer's to state.**", "",
             "| Item | Existing | Proposed |", "|--|--|--|", f"| Use | {_field(inp, 'existing_use', 'existing use')} | Rest home (residential care) |", f"| Sleeping capacity | {_v(inp, 'bedrooms_total')} bedrooms recorded | {opt['beds']} beds |",
             f"| Sprinklers | {_v(inp, 'sprinklers')} | {_pf(inp, 'cou_sprinklers_proposed')} |", f"| Fire alarm | {_v(inp, 'fire_alarm')} | {_pf(inp, 'cou_alarm_proposed')} |", f"| Fire risk group | {_pf(inp, 'cou_fire_group_existing')} | {_pf(inp, 'cou_fire_group_proposed')} |", f"| Exits | {_v(inp, 'level_access_entrances')} level-access entrances recorded | {_pf(inp, 'cou_exits_proposed')} |", ""]
        return "\n".join(L)
    if doc_key == "specification":
        L = [head, "# Specification and schedules (draft)", "", "Room schedule from the layout option. Doors, windows, finishes and fixtures are not known from the plan reading and are the designer's to specify.", "", "| Level | Room | Type | Area m2 | Action | Becomes |", "|--|--|--|--|--|--|"]
        for lv in opt["levels"]:
            for r in lv["rooms"]: L.append(f"| {lv['level_name']} | {r['label'] or ''} | {r['type']} | {r.get('area_m2') or ''} | {r['action']} | {r.get('becomes') or ''} |")
        L += ["", f"- Door schedule: {_pf(inp, 'spec_doors')}", f"- Window schedule: {_pf(inp, 'spec_windows')}", f"- Finishes schedule: {_pf(inp, 'spec_finishes')}", f"- Fixtures and fittings: {_pf(inp, 'spec_fixtures')}"]
        return "\n".join(L)
    if doc_key == "compliance_matrix":
        by = {c["id"]: c for c in inp["compliance"]}
        L = [head, "# Building Code compliance schedule (draft, clause by clause)", "", "The status column is the app's screening result, not a compliance opinion. The compliance method (acceptable solution, verification method or alternative solution) and the evidence are for the signing professional. Clause text and thresholds are not reproduced: they come from MBIE documents (docs/sources_manual/README.md).", "",
             "| Clause | Title | Signs off | Screening result | Compliance method | Evidence |", "|--|--|--|--|--|--|"]
        for cl in clauses():
            res = "; ".join(f"{by[i]['status']} ({i})" for i in cl["checks"] if i in by) or "no screening check"
            L.append(f"| {cl['clause']} | {cl['title']} | {cl['signs_off']} | {res} | {inp['fields'].get('clause_method.' + cl['clause']) or tc('designer: method for ' + cl['clause'])} | {inp['fields'].get('clause_evidence.' + cl['clause']) or tc('producer statement / report reference for ' + cl['clause'])} |")
        return "\n".join(L)
    if doc_key == "drawings":
        _, missing = drawing_files(p)
        L = [head, "# Drawing set", "", "Existing, change-of-use/strip-out and new-work drawings per level, from the human-confirmed plan reading (PDF in `Plans/`, DXF in `Plans/DXF/` for the designer). Room level only: walls, structure, fire and services are the designer's and engineers'.", ""]
        L += [f"- {lv['level_name']}: " + ("no scale set: **no drawing can be produced**" if lv['level_name'] in missing else "drawing included") for lv in opt["levels"]]
        return "\n".join(L)
    if doc_key == "lodgement_checklist":
        return "\n".join([head, f"# Lodgement checklist: {site['address']}", ""] + _checklist_md(pack_id))
    if doc_key == "cover_index":
        L = [head, f"# Building consent pack (DRAFT): {site['address']}", f"Pack version {p['version']} | checklist `{p['checklist_version']}` | Council-verified checklist: **{checklist()['council_verified']}** | status: {p['status']}", "",
             "This pack is prepared for review by the designer and engineers. It is not a consent application until the professionals have issued their documents and the owner lodges it through the Council portal.", "", "| Folder | File | Document | Kind | Required |", "|--|--|--|--|--|"]
        L += [f"| {d['folder']} | {d['file_name']} | {d['title']} | {d['kind']} | {'yes' if d['required'] else 'no'} |" for d in docs]
        return "\n".join(L)
    if doc_key == "pim_request": return "\n".join([head, "# PIM request details", "", f"Property: {site['address']}", f"Owner: {_field(inp, 'owner_name', 'owner name')}", "Request: Project Information Memorandum for a change of use to a rest home.", "(Request through the Council portal; this sheet holds the details to enter.)"])
    if doc_key == "fee_estimate": return "\n".join([head, "# Council fee estimate", "", tc("fee schedule not found: enter the Council's calculated fee when the portal gives it")])
    raise HTTPException(409, f"no generator for {doc_key}")

def _checklist_md(pack_id: int) -> list[str]:
    g = completeness(pack_id)
    L = [f"Ready to lodge: **{'YES' if g['ready'] else 'NO'}**. Blocking items: {len(g['blockers'])}.", "", "| Folder | File | Document | Required | Status |", "|--|--|--|--|--|"]
    L += [f"| {d['folder']} | {d['file_name']} | {d['title']} | {'yes' if d['required'] else 'no (' + (d['reason'] or '') + ')'} | {d['status']} |" for d in g["documents"]]
    L += ["", "## Blocking items"] + [f"- {b['code']}: {b['detail']}" for b in g["blockers"]]
    return L

# ------------------------------------------------------------------ drawings
def drawing_files(p: dict) -> tuple[list[tuple[str, bytes, bytes]], list[str]]:
    """-> ([(level_name, pdf, dxf)], names of levels that cannot be drawn)"""
    opt = get_option(p["option_id"]); out, missing = [], []
    for i, lv in enumerate(opt["levels"]):
        try: out.append((lv["level_name"], drawings.pdf(opt["id"], i), drawings.dxf(opt["id"], i)))
        except HTTPException: missing.append(lv["level_name"])
    return out, missing

# ------------------------------------------------------------------ statements and the register check
def statements(pack_id: int) -> list[dict]:
    with conn() as c: return c.execute("SELECT s.* FROM core.rh_statement s JOIN core.rh_pack_doc d ON d.id = s.doc_id WHERE d.pack_id = %s ORDER BY s.id", (pack_id,)).fetchall()

def statement_valid(s: dict, doc: dict) -> tuple[bool, list[str]]:
    """A statement counts only when: PDF on file, right type for the slot, author, company and date recorded (date not in the future), and the author found on the Council register (checked within MAX_AGE_DAYS)."""
    why = []
    if doc.get("statement_type") and s["statement_type"] != doc["statement_type"]: why.append(f"type {s['statement_type']} but the slot needs {doc['statement_type']}")
    if doc.get("statement_type"):
        if not s["author_name"]: why.append("author name not recorded")
        if not s["author_company"]: why.append("author company not recorded")
        if not s["date_issued"]: why.append("date issued not recorded")
        elif s["date_issued"] > date.today(): why.append("date issued is in the future")
        if s["register_status"] != "valid": why.append(f"author register check: {s['register_status'].replace('_', ' ')}")
        elif not s["register_checked_on"] or (date.today() - s["register_checked_on"]).days > ps_register.MAX_AGE_DAYS: why.append(f"register check older than {ps_register.MAX_AGE_DAYS} days: repeat it")
    return (not why), why

def add_statement(pack_id: int, doc_key: str, filename: str, data: bytes, meta: dict) -> dict:
    p = _pack(pack_id)
    if p["status"] == "superseded": raise HTTPException(409, "superseded pack: upload to the current version")
    doc = next((d for d in _docs(pack_id) if d["doc_key"] == doc_key), None)
    if not doc: raise HTTPException(404, "no such document in this pack")
    if doc["kind"] != "upload_slot": raise HTTPException(409, "this document is generated by the app, not an upload slot")
    if not data: raise HTTPException(422, "empty file")
    if len(data) > MAX_UPLOAD_BYTES: raise HTTPException(413, "file too large")
    if detect_type(data, filename) != "pdf": raise HTTPException(415, "the Council takes PDF: upload a PDF")
    sha = hashlib.sha256(data).hexdigest(); d = upload_dir() / "packs" / str(pack_id); d.mkdir(parents=True, exist_ok=True)
    stored = f"{sha[:16]}_{safe_name(filename)}"; (d / stored).write_bytes(data)
    typ = doc.get("statement_type") or "DOCUMENT"
    if doc.get("statement_type"):
        r = ps_register.check(meta.get("author_name"), meta.get("author_company"), doc.get("discipline"))
        reg = (r["status"], date.today() if r["status"] != "not_checked" else None, "register file" if r["status"] != "not_checked" else None, r["note"])
    else: reg = ("not_applicable", None, None, "not a producer statement")
    with conn() as c:
        c.execute("UPDATE core.rh_statement SET superseded = true WHERE doc_id = %s", (doc["id"],))
        r = c.execute("""INSERT INTO core.rh_statement (doc_id, original_name, stored_name, sha256, size_bytes, statement_type, author_name, author_company, psa_number, discipline, date_issued, scope_note, register_status, register_checked_on, register_checked_by, register_note)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                      (doc["id"], safe_name(filename), stored, sha, len(data), typ, meta.get("author_name"), meta.get("author_company"), meta.get("psa_number"), doc.get("discipline"), meta.get("date_issued"), meta.get("scope_note"), *reg)).fetchone()
        c.execute("UPDATE core.rh_pack SET status='draft', ready_marked_at=NULL WHERE id=%s AND status='ready_to_lodge'", (pack_id,)); c.commit()
    return statement_view(r["id"])

def statement_view(sid: int) -> dict:
    with conn() as c:
        s = c.execute("SELECT s.*, d.doc_key, d.statement_type AS slot_type, d.discipline AS slot_disc FROM core.rh_statement s JOIN core.rh_pack_doc d ON d.id=s.doc_id WHERE s.id=%s", (sid,)).fetchone()
        if not s: raise HTTPException(404, "no such statement")
        doc = c.execute("SELECT * FROM core.rh_pack_doc WHERE id=%s", (s["doc_id"],)).fetchone()
    ok, why = statement_valid(s, doc)
    return {**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in s.items() if k not in ("stored_name",)}, "valid": ok, "problems": why}

def record_register_check(sid: int, status: str, checked_by: str, note: str | None, on: date | None = None) -> dict:
    """The owner checked the Council's online 'Find a producer statement author' search and records the outcome. Re-running the loaded-file check is done with recheck()."""
    if status not in ("valid", "not_on_register", "expired"): raise HTTPException(422, "status must be valid, not_on_register or expired")
    if not (checked_by or "").strip(): raise HTTPException(422, "say who made the check")
    on = on or date.today()
    if on > date.today(): raise HTTPException(422, "check date is in the future")
    with conn() as c:
        r = c.execute("UPDATE core.rh_statement SET register_status=%s, register_checked_on=%s, register_checked_by=%s, register_note=%s WHERE id=%s AND NOT superseded RETURNING doc_id", (status, on, checked_by.strip(), note, sid)).fetchone()
        if not r: raise HTTPException(404, "no such current statement")
        c.execute("UPDATE core.rh_pack SET status='draft', ready_marked_at=NULL WHERE id=(SELECT pack_id FROM core.rh_pack_doc WHERE id=%s) AND status='ready_to_lodge'", (r["doc_id"],)); c.commit()
    return statement_view(sid)

def recheck(sid: int) -> dict:
    with conn() as c:
        s = c.execute("SELECT s.*, d.discipline AS dd FROM core.rh_statement s JOIN core.rh_pack_doc d ON d.id = s.doc_id WHERE s.id=%s AND NOT s.superseded", (sid,)).fetchone()
    if not s: raise HTTPException(404, "no such current statement")
    r = ps_register.check(s["author_name"], s["author_company"], s["dd"])
    if r["status"] == "not_checked": raise HTTPException(409, r["note"])
    return record_register_check(sid, r["status"], "register file", r["note"])

def statement_file(sid: int) -> tuple[str, bytes]:
    with conn() as c: s = c.execute("SELECT s.stored_name, s.original_name, d.pack_id FROM core.rh_statement s JOIN core.rh_pack_doc d ON d.id=s.doc_id WHERE s.id=%s", (sid,)).fetchone()
    if not s: raise HTTPException(404, "no such statement")
    return s["original_name"], (upload_dir() / "packs" / str(s["pack_id"]) / s["stored_name"]).read_bytes()

# ------------------------------------------------------------------ completeness and the gate
def completeness(pack_id: int) -> dict:
    p = _pack(pack_id); inp = p["inputs"]; docs = _docs(pack_id); sts = statements(pack_id); blockers = []; rows = []
    def block(code, detail): blockers.append({"code": code, "detail": detail})
    if not checklist()["council_verified"]:
        block("checklist_not_council_verified", "the pack is built to a checklist assembled from the spec and Council guidance summaries; Auckland Council's own checklist (AC1021 / portal) has not been opened and reconciled (docs/sources_manual/README.md)")
    for d in docs:
        status = "n/a"
        if d["kind"] == "upload_slot":
            live = [s for s in sts if s["doc_id"] == d["id"] and not s["superseded"]]
            if not live: status = "NOT UPLOADED"
            else:
                ok, why = statement_valid(live[0], d); status = "uploaded, valid" if ok else "uploaded, NOT valid: " + "; ".join(why)
                if not ok and d["required"]: block("statement_invalid", f"{d['title']}: " + "; ".join(why))
            if status == "NOT UPLOADED" and d["required"]: block("document_missing", f"{d['title']} has not been uploaded")
        else:
            txt = "" if d["doc_key"] in DYNAMIC else render(pack_id, d["doc_key"])
            n = len(TC.findall(txt)); status = "complete" if n == 0 else f"{n} item(s) still to complete"
            if n and d["required"]: block("placeholders_remaining", f"{d['title']}: {n} [TO COMPLETE] item(s): " + "; ".join(sorted(set(m[13:-1] for m in TC.findall(txt)))[:6]) + (" ..." if n > 6 else ""))
        rows.append({"doc_key": d["doc_key"], "title": d["title"], "kind": d["kind"], "folder": d["folder"], "file_name": d["file_name"], "required": d["required"], "reason": d["not_required_reason"], "status": status})
    if p["option_id"]:
        _, missing = drawing_files(p)
        if missing: block("drawings_unavailable", "no scale set on level(s): " + ", ".join(missing))
    for c_ in inp["compliance"]:
        if c_["status"] == "FAIL" and c_["id"] not in inp["resolutions"]:
            block("compliance_fail", f"{c_['id']}: {c_['detail']} (record how the design resolves it, or fix the design)")
    return {"pack_id": pack_id, "ready": not blockers, "blockers": blockers, "documents": rows, "status": p["status"]}

def mark_ready(pack_id: int) -> dict:
    p = _pack(pack_id)
    if p["status"] == "superseded": raise HTTPException(409, "superseded pack")
    g = completeness(pack_id)
    if not g["ready"]: raise HTTPException(409, {"message": "not ready to lodge", "blockers": g["blockers"]})
    with conn() as c: c.execute("UPDATE core.rh_pack SET status='ready_to_lodge', ready_marked_at=now() WHERE id=%s", (pack_id,)); c.commit()
    return get(pack_id)

# ------------------------------------------------------------------ views and export
def get(pack_id: int) -> dict:
    p = _pack(pack_id); g = completeness(pack_id)
    return {"id": p["id"], "parcel_id": p["parcel_id"], "option_id": p["option_id"], "version": p["version"], "status": p["status"], "checklist_version": p["checklist_version"], "council_verified": checklist()["council_verified"],
            "fields": p["inputs"]["fields"], "resolutions": p["inputs"]["resolutions"], "completeness": g, "created_at": p["created_at"].isoformat(),
            "register": {"file_loaded": ps_register.loaded(), "note": "No register file loaded: record each author check by hand from the Council's online search." if not ps_register.loaded() else "register file(s) loaded"},
            "label": "DRAFT pack. Producer statements, fire reports and signatures are upload slots: the app never writes them."}

def list_for_parcel(parcel_id: int) -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.rh_pack WHERE parcel_id=%s ORDER BY id DESC", (parcel_id,)).fetchall()]
    return [{"id": i, "version": _pack(i)["version"], "status": _pack(i)["status"]} for i in ids]

def upload_sheet(pack_id: int) -> str:
    p = _pack(pack_id); g = completeness(pack_id)
    L = [f"**{STAMP}**", "", f"# Upload sheet: {p['inputs']['site']['address']}", "", "Council portal rules (from the file-naming page summary; verify on the portal): PDF only, 300 MB maximum per file, landscape drawings, not locked or password protected. Folders: Applications, Plans, Supporting Documents.", "",
         "| Folder | File name (in the zip) | Format | Required | Status |", "|--|--|--|--|--|"]
    L += [f"| {d['folder']} | {d['file_name']}.pdf | PDF | {'yes' if d['required'] else 'no'} | {d['status']} |" for d in g["documents"]]
    return "\n".join(L)

def export_zip(pack_id: int) -> bytes:
    p = _pack(pack_id); docs = _docs(pack_id); buf = io.BytesIO(); readme = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in docs:
            if d["kind"] == "generated" and d["doc_key"] != "drawings":
                z.writestr(f"{d['folder']}/{d['file_name']}.pdf", md_to_pdf(render(pack_id, d["doc_key"]), d["title"]))
            elif d["kind"] == "form_data" and d["doc_key"] != "fee_estimate":
                z.writestr(f"{d['folder']}/{d['file_name']}.pdf", md_to_pdf(render(pack_id, d["doc_key"]), d["title"]))
        files, missing = drawing_files(p)
        for name, pdf_b, dxf_b in files:
            nm = safe_name(name); z.writestr(f"Plans/Architectural Plan {nm}.pdf", pdf_b); z.writestr(f"Plans/DXF/Architectural Plan {nm}.dxf", dxf_b)
        for d in docs:
            if d["kind"] != "upload_slot": continue
            live = [s for s in statements(pack_id) if s["doc_id"] == d["id"] and not s["superseded"]]
            if live:
                _, data = statement_file(live[0]["id"]); z.writestr(f"{d['folder']}/{d['file_name']}.pdf", data)
            else: readme.append(f"MISSING: {d['folder']}/{d['file_name']}.pdf ({d['title']}, from {d['owner']})")
        z.writestr("Upload Sheet.pdf", md_to_pdf(upload_sheet(pack_id), "Upload sheet"))
        z.writestr("README.txt", f"{STAMP}\n\nConsent pack version {p['version']} (status {p['status']}). Documents the app generated are stamped DRAFT on every page. Documents uploaded by professionals are included as received, unstamped.\n"
                   f"The checklist used is {p['checklist_version']}; Council-verified: {checklist()['council_verified']}.\n\nStill missing:\n" + ("\n".join(readme) or "(nothing)") + "\n")
    return buf.getvalue()
