"""Resource consent pack (MASTER_SPEC Part 2 section 8.1 to 8.7), draft. Built from a development scenario run. The Council's resource consent checklist, forms and fee schedule have NOT been seen (the Council site is not reachable from the sandbox):
the document list is the spec's (8.3) and council_verified stays false, so 'ready to lodge' is refused. Every generated document is stamped DRAFT and uses highlighted [TO COMPLETE: ...] placeholders, counted as gaps.
Professional documents (scheme plan, civil, geotechnical, traffic, arborist reports, written approvals) are upload slots only. The pack never predicts the Council's decision."""
import hashlib, io, json, re, zipfile
from datetime import date
from fastapi import HTTPException
from . import services
from .config import upload_dir
from .db import conn
from .devscenarios import FOOTER, get_run
from .pack_pdf import md_to_pdf
from .stamp import STAMP
from .uploads import detect_type, safe_name, MAX_UPLOAD_BYTES

CHECKLIST_VERSION = "spec-8.3-draft-1"; COUNCIL_VERIFIED = False
TC = re.compile(r"\[TO COMPLETE: [^\]]+\]")
def tc(x): return f"[TO COMPLETE: {x}]"
DOCS = [  # key, title, kind, required, owner
    ("cover_index", "Cover page and index", "generated", True, "me"), ("application_form", "Application form data sheet (pre-filled fields, portal order unverified)", "generated", True, "you"),
    ("cover_letter", "Cover letter", "generated", True, "you"), ("aee", "Assessment of Environmental Effects (draft, rule-by-rule)", "generated", True, "planner"), ("site_description", "Site description", "generated", True, "me"),
    ("title_easements", "Record of title and list of easements, covenants and consent notices", "upload_slot", True, "you"), ("plans", "Plans (site plan, scheme plan or building plans)", "upload_slot", True, "surveyor / designer"),
    ("affected_parties", "Affected parties list and written approval templates", "generated", True, "planner"), ("servicing_statement", "Infrastructure and servicing statement (draft)", "generated", True, "civil engineer"),
    ("stormwater_earthworks", "Stormwater and earthworks statements (where triggered)", "upload_slot", False, "civil engineer"), ("consultation_record", "Consultation record template (iwi, neighbours, utilities)", "generated", True, "you"),
    ("fees_estimate", "Council fees estimate", "upload_slot", True, "you"), ("scheme_plan", "Scheme plan by a licensed surveyor (subdivision)", "upload_slot", False, "licensed surveyor"),
    ("civil_report", "Civil engineering report", "upload_slot", False, "civil engineer"), ("geotech_report", "Geotechnical report (where hazards flagged)", "upload_slot", False, "geotechnical engineer"),
    ("traffic_report", "Traffic report (where triggered)", "upload_slot", False, "traffic engineer"), ("arborist_report", "Arborist report (where trees are protected)", "upload_slot", False, "arborist"),
    ("written_approvals", "Signed written approvals from affected parties", "upload_slot", False, "affected parties")]

def _pack(pid):
    with conn() as c: p = c.execute("SELECT * FROM core.user_rc_pack WHERE id=%s", (pid,)).fetchone()
    if not p: raise HTTPException(404, "no such pack")
    return p

def build(parcel_id: int, run_id: int | None = None) -> dict:
    from .devscenarios import latest
    run = get_run(run_id) if run_id else latest(parcel_id)
    if not run or run.get("status") != "ok": raise HTTPException(409, "run the feasibility summary (button 1) successfully first: the pack is built from that run")
    if run["parcel_id"] != parcel_id: raise HTTPException(404, "run belongs to another parcel")
    with conn() as c:
        v = c.execute("SELECT COALESCE(MAX(p.version),0)+1 AS v FROM core.user_rc_pack p JOIN core.user_dev_run r ON r.id=p.run_id WHERE r.parcel_id=%s", (parcel_id,)).fetchone()["v"]
        p = c.execute("INSERT INTO core.user_rc_pack (run_id, version, checklist_version) VALUES (%s,%s,%s) RETURNING id", (run["run_id"], v, CHECKLIST_VERSION)).fetchone()
        c.execute("UPDATE core.user_rc_pack SET status='superseded' WHERE id<>%s AND status<>'superseded' AND run_id IN (SELECT id FROM core.user_dev_run WHERE parcel_id=%s)", (p["id"], parcel_id)); c.commit()
    return get(p["id"])

def set_fields(pid: int, fields: dict) -> dict:
    p = _pack(pid)
    if p["status"] == "superseded": raise HTTPException(409, "superseded pack")
    allowed = {"applicant_name", "applicant_address", "applicant_email", "agent_name", "consent_types", "proposal_summary", "consultation_notes", "fee_estimate"}
    if set(fields) - allowed: raise HTTPException(422, f"unknown field(s): {sorted(set(fields) - allowed)}")
    cur = dict(p["fields"]); [cur.pop(k, None) if not v else cur.__setitem__(k, str(v)[:1500]) for k, v in fields.items()]
    with conn() as c: c.execute("UPDATE core.user_rc_pack SET fields=%s::jsonb, status=CASE WHEN status='ready_to_lodge' THEN 'draft' ELSE status END WHERE id=%s", (json.dumps(cur), pid)); c.commit()
    return get(pid)

def add_upload(pid: int, key: str, filename: str, data: bytes) -> dict:
    p = _pack(pid)
    if p["status"] == "superseded": raise HTTPException(409, "superseded pack")
    d = next((x for x in DOCS if x[0] == key), None)
    if not d or d[2] != "upload_slot": raise HTTPException(404, "no such upload slot")
    if not data: raise HTTPException(422, "empty file")
    if len(data) > MAX_UPLOAD_BYTES: raise HTTPException(413, "file too large")
    if detect_type(data, filename) != "pdf": raise HTTPException(415, "upload a PDF")
    sha = hashlib.sha256(data).hexdigest(); dd = upload_dir() / "rcpacks" / str(pid); dd.mkdir(parents=True, exist_ok=True); stored = f"{sha[:16]}_{safe_name(filename)}"; (dd / stored).write_bytes(data)
    up = dict(p["uploads"]); up[key] = {"filename": safe_name(filename), "stored": stored, "sha256": sha, "on": date.today().isoformat()}
    with conn() as c: c.execute("UPDATE core.user_rc_pack SET uploads=%s::jsonb, status=CASE WHEN status='ready_to_lodge' THEN 'draft' ELSE status END WHERE id=%s", (json.dumps(up), pid)); c.commit()
    return get(pid)

def render(pid: int, key: str) -> str:
    p = _pack(pid); run = get_run(p["run_id"]); f = p["fields"]; head = f"**{STAMP}**\n\n"; sc = (run.get("scenarios") or [None])[0]; inp = run["inputs"]; fin = run.get("financials") or {}
    F = lambda k, label: f.get(k) or tc(label)
    if key == "cover_index":
        return head + f"# Resource consent pack (DRAFT): {run['address']}\nVersion {p['version']} | checklist `{p['checklist_version']}` (Council-verified: {COUNCIL_VERIFIED}) | status {p['status']}\n\n| # | Document | Kind | Required |\n|--|--|--|--|\n" + "\n".join(f"| {i} | {t} | {k} | {'yes' if r else 'no'} |" for i, (_, t, k, r, _o) in enumerate(DOCS, 1))
    if key == "application_form":
        return head + "\n".join([f"# Application data sheet: {run['address']}", "Fields to type into the Council's form. The Council's form and portal order have not been seen: follow the form's own order.", "", "| Field | Value |", "|--|--|",
                                 f"| Site address | {run['address']} |", f"| Parcel (LINZ) | {run['parcel_id']} |", f"| Zone | {run['zone']} |", f"| Site area | {run['site']['area_m2']} m2 |", f"| Applicant | {F('applicant_name', 'applicant name')} |",
                                 f"| Applicant address | {F('applicant_address', 'postal address')} |", f"| Applicant email | {F('applicant_email', 'email')} |", f"| Agent | {f.get('agent_name') or 'none'} |", f"| Consent types sought | {F('consent_types', 'consent types, from the planner')} |",
                                 f"| Proposal | {inp['typology']}; {sc['unit_count'] if sc else 'n/a'} units (concept) |"])
    if key == "cover_letter": return head + f"# Cover letter\n\n{date.today().isoformat()}\n\nTo: Auckland Council, Resource Consents\n\nRe: {run['address']}\n\n{F('proposal_summary', 'one-paragraph proposal summary, written by the planner or applicant')}\n\nThe attached documents are drafts prepared for review by the applicant's planner and other professionals.\n\n{F('applicant_name', 'applicant name')}"
    if key == "site_description":
        return head + f"# Site description\n\n- Address: {run['address']}\n- Zone: {run['zone']}; area {run['site']['area_m2']} m2; title type {run['site']['title_type'] or 'unknown'}.\n- Overlays: {run['site']['overlays'] or 'none recorded'}.\n- Hazards recorded: {run['site']['hazards']['hazard_flags']}.\n- Existing buildings recorded: {run['site']['existing_buildings']}.\n- Easements, covenants and consent notices: {tc('from the record of title')}."
    if key == "aee":
        L = [head, "# Assessment of Environmental Effects (draft)", "", "Rule-by-rule assessment from the rules evaluator (operative plan). Rule values are not yet confirmed by the applicant. Effects assessments are for the planner.", "", "| Topic | Rule | Required | Proposed | Status |", "|--|--|--|--|--|"]
        for c in (sc["checks"] if sc else []): L.append(f"| {c['topic']} | {c.get('rule') or 'not loaded'} | {c['required'] if c['required'] is not None else ''} | {c['measured'] if c['measured'] is not None else ''} | {c['status']} |")
        L += ["", "## Activity status", "| Activity | Status | Rule |", "|--|--|--|"] + [f"| {a['activity']} | {a['status_class']} | {a['section_ref']} |" for a in run.get("activity_rows", [])]
        L += ["", "## Assessment of effects", tc("planner: effects on neighbours, character, amenity, infrastructure"), "", "## Objectives and policies", tc("planner: relevant objectives and policies"), "", "## Conclusion", tc("planner")]
        return "\n".join(L)
    if key == "affected_parties": return head + "# Affected parties\n\n" + tc("list of neighbours and others potentially affected, from the planner") + "\n\n## Written approval template\n\nI, " + tc("name") + ", of " + tc("address") + ", owner/occupier of " + tc("property") + ", have seen the plans for the proposal at " + run["address"] + " and give my written approval. Signature: " + tc("signed by the affected party") + "  Date: " + tc("date")
    if key == "servicing_statement":
        s = services.get(run["parcel_id"]); return head + f"# Infrastructure and servicing statement (draft)\n\nCapacity status: **{s['capacity_status']}** ({s['capacity_note']}).\n\n- Water: {tc('connection point and diameter, from Watercare')}\n- Wastewater: {tc('connection point, from Watercare')}\n- Stormwater: {tc('management approach, from the civil engineer')}\n- Power / telecoms: {tc('from the lines company')}\n\nManual entries recorded: {s['completeness']}."
    if key == "consultation_record": return head + "# Consultation record\n\n| Party | Date | Method | Outcome |\n|--|--|--|--|\n| Iwi / mana whenua | " + tc("date") + " | " + tc("method") + " | " + tc("outcome") + " |\n| Neighbours | " + tc("date") + " | " + tc("method") + " | " + tc("outcome") + " |\n| Utilities | " + tc("date") + " | " + tc("method") + " | " + tc("outcome") + " |\n\n" + (f.get("consultation_notes") or tc("notes"))
    raise HTTPException(409, "no generator for that document (an upload slot, or unknown)")

def completeness(pid: int) -> dict:
    p = _pack(pid); blockers = []; rows = []
    if not COUNCIL_VERIFIED: blockers.append({"code": "checklist_not_council_verified", "detail": "the Council's resource consent checklist and forms have not been seen: the pack follows the spec's list"})
    for key, title, kind, req, owner in DOCS:
        if kind == "upload_slot":
            st = "uploaded" if key in p["uploads"] else "needs_upload"
            if st == "needs_upload" and req: blockers.append({"code": "document_missing", "detail": f"{title} has not been uploaded"})
        else:
            n = len(TC.findall(render(pid, key))) if key != "cover_index" else 0; st = "generated" if n == 0 else f"generated, {n} item(s) to complete"
            if n and req: blockers.append({"code": "placeholders_remaining", "detail": f"{title}: {n} [TO COMPLETE] item(s)"})
        rows.append({"key": key, "title": title, "kind": kind, "required": req, "owner": owner, "status": st})
    run = get_run(p["run_id"]); fails = [c["id"] for sc in (run.get("scenarios") or [])[:1] for c in sc["checks"] if c["status"] == "FAIL"]
    if fails or run.get("scenarios", [{}])[0].get("kind") == "nearest_miss": blockers.append({"code": "compliance_fail", "detail": "the selected scenario has failing rules: " + ", ".join(fails)})
    return {"pack_id": pid, "ready": not blockers, "blockers": blockers, "documents": rows}

def mark_ready(pid: int) -> dict:
    p = _pack(pid)
    if p["status"] == "superseded": raise HTTPException(409, "superseded pack")
    g = completeness(pid)
    if not g["ready"]: raise HTTPException(409, {"message": "not ready to lodge", "blockers": g["blockers"]})
    with conn() as c: c.execute("UPDATE core.user_rc_pack SET status='ready_to_lodge' WHERE id=%s", (pid,)); c.commit()
    return get(pid)

def get(pid: int) -> dict:
    p = _pack(pid)
    return {"id": pid, "run_id": p["run_id"], "version": p["version"], "status": p["status"], "checklist_version": p["checklist_version"], "council_verified": COUNCIL_VERIFIED, "fields": p["fields"], "uploads": p["uploads"], "completeness": completeness(pid),
            "label": "DRAFT pack. Nothing here predicts the Council's decision. Professional documents are upload slots."}

def export_zip(pid: int) -> bytes:
    p = _pack(pid); buf = io.BytesIO(); miss = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, (key, title, kind, req, owner) in enumerate(DOCS, 1):
            nm = f"{i:02d} {title.split('(')[0].strip()}.pdf"
            if kind == "generated": z.writestr(nm, md_to_pdf(render(pid, key), title))
            elif key in p["uploads"]: z.writestr(nm, (upload_dir() / "rcpacks" / str(pid) / p["uploads"][key]["stored"]).read_bytes())
            elif req: miss.append(f"MISSING: {nm} ({owner})")
        g = completeness(pid); z.writestr("Upload sheet.pdf", md_to_pdf("# Upload sheet (portal order unverified)\n\n| File | Required | Status |\n|--|--|--|\n" + "\n".join(f"| {r['title']} | {'yes' if r['required'] else 'no'} | {r['status']} |" for r in g["documents"]), "Upload sheet"))
        z.writestr("README.txt", f"{STAMP}\n\nResource consent pack v{p['version']} ({p['status']}). Checklist {p['checklist_version']}; Council-verified: {COUNCIL_VERIFIED}.\n\nStill missing:\n" + ("\n".join(miss) or "(nothing)") + "\n\n" + FOOTER + "\n")
    return buf.getvalue()
