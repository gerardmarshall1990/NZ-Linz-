"""Part 7 step 4 tests: pack build and versioning, DRAFT stamp on every generated document, upload slots only for statements, register check, the ready-to-lodge gate, engineer review packages, feature flag."""
import copy, io, os, zipfile
from datetime import date, timedelta
import pymupdf, pytest
from fastapi.testclient import TestClient
from tests.test_step2 import PARCEL, plan_dxf, setup_property

STAMP = "DRAFT: NOT FOR CONSENT until reviewed and issued by a qualified professional"

def pdf_bytes(text="statement"):
    d = pymupdf.open(); d.new_page().insert_text((72, 72), text); return d.tobytes()

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads_pack"))
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            c.execute("DELETE FROM core.rh_pack WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.user_flag WHERE key='engineer_review_links'")
            for t in ("rh_brief", "rh_check_run", "rh_layout_option", "rh_evidence_gap_status"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_edit WHERE extraction_id IN (SELECT x.id FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_extraction WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_calibration WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            for t in ("rh_upload", "rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.commit()
    clean(); cl = TestClient(app); setup_property(cl)
    cl.opt = cl.post(f"/api/property/{PARCEL}/layouts").json()[0]["id"]; yield cl; clean()

def new_pack(client): r = client.post(f"/api/property/{PARCEL}/packs", json={"option_id": client.opt}); assert r.status_code == 200, r.text; return r.json()

def doc_row(pack_id, key):
    from backend.app.db import conn
    with conn() as c: return c.execute("SELECT * FROM core.rh_pack_doc WHERE pack_id=%s AND doc_key=%s", (pack_id, key)).fetchone()

def test_build_and_versions(client):
    a = new_pack(client); assert a["version"] >= 1 and a["status"] == "draft" and a["council_verified"] is False
    b = new_pack(client); assert b["version"] == a["version"] + 1
    assert client.get(f"/api/packs/{a['id']}").json()["status"] == "superseded"
    assert client.put(f"/api/packs/{a['id']}/fields", json={"fields": {"owner_name": "X"}}).status_code == 409
    keys = {d["doc_key"] for d in b["completeness"]["documents"]}
    for k in ("cover_index", "application_data", "drawings", "ps1_design", "ps1_structural", "ps1_fire", "fire_report", "cow", "compliance_matrix"): assert k in keys

def test_every_generated_document_is_stamped_draft(client):
    p = new_pack(client)
    for d in p["completeness"]["documents"]:
        if d["kind"] == "generated" and d["doc_key"] != "drawings":
            md = client.get(f"/api/packs/{p['id']}/documents/{d['doc_key']}.md").text; assert STAMP in md, d["doc_key"]
            pdf = pymupdf.open(stream=client.get(f"/api/packs/{p['id']}/documents/{d['doc_key']}.pdf").content, filetype="pdf")
            assert all(STAMP in pg.get_text().replace("\n", " ") for pg in pdf), d["doc_key"]
    # drawings carry the stamp (DXF text layer and PDF)
    dpdf = client.get(f"/api/layouts/{client.opt}/drawing.pdf").content
    assert STAMP in pymupdf.open(stream=dpdf, filetype="pdf")[0].get_text().replace("\n", " ")

def test_statements_and_reports_are_upload_slots_only(client):
    p = new_pack(client)
    for k in ("ps1_design", "ps1_structural", "ps1_fire", "ps1_services", "ps2_review", "fire_report", "cow", "structural_calcs", "record_of_title"):
        assert doc_row(p["id"], k)["kind"] == "upload_slot"
        assert client.get(f"/api/packs/{p['id']}/documents/{k}.md").status_code == 409      # nothing is generated for them
    ex = zipfile.ZipFile(io.BytesIO(client.get(f"/api/packs/{p['id']}/export.zip").content))
    assert "README.txt" in ex.namelist() and "Upload Sheet.pdf" in ex.namelist()
    assert not any(n.startswith("Supporting Documents/PS1") or n.endswith("Fire Report.pdf") for n in ex.namelist())      # nothing fabricated for the missing slots
    assert "MISSING: Supporting Documents/PS1 Design.pdf" in ex.read("README.txt").decode()

def test_non_pdf_statement_refused_and_unregistered_author_is_not_valid(client):
    p = new_pack(client); url = f"/api/packs/{p['id']}/documents/ps1_structural/upload"
    assert client.post(url, files={"file": ("ps1.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50)}).status_code == 415
    r = client.post(url, files={"file": ("ps1.pdf", pdf_bytes())}, data={"author_name": "A Engineer", "author_company": "Eng Ltd", "date_issued": str(date.today())})
    assert r.status_code == 200, r.text; s = r.json()
    assert s["valid"] is False and s["register_status"] == "not_checked" and any("register" in x for x in s["problems"])
    assert any(b["code"] == "statement_invalid" and "PS1: structural" in b["detail"] for b in client.get(f"/api/packs/{p['id']}/completeness").json()["blockers"])
    ok = client.post(f"/api/statements/{s['id']}/register-check", json={"status": "valid", "checked_by": "owner", "note": "Council search"}).json()
    assert ok["valid"] is True and ok["register_checked_by"] == "owner"
    assert client.post(f"/api/statements/{s['id']}/register-check", json={"status": "not_on_register", "checked_by": "owner"}).json()["valid"] is False
    assert client.post(f"/api/statements/{s['id']}/register-check", json={"status": "valid", "checked_by": ""}).status_code == 422
    assert client.post(f"/api/statements/{s['id']}/register-check", json={"status": "valid", "checked_by": "o", "checked_on": str(date.today() + timedelta(days=1))}).status_code == 422

def test_statement_validity_rules():
    from backend.app.consent_pack import statement_valid
    doc = {"statement_type": "PS1"}
    base = {"statement_type": "PS1", "author_name": "A", "author_company": "C", "date_issued": date.today(), "register_status": "valid", "register_checked_on": date.today()}
    assert statement_valid(base, doc) == (True, [])
    assert not statement_valid({**base, "statement_type": "PS2"}, doc)[0]
    assert not statement_valid({**base, "date_issued": date.today() + timedelta(days=2)}, doc)[0]
    assert not statement_valid({**base, "author_name": None}, doc)[0]
    assert not statement_valid({**base, "register_checked_on": date.today() - timedelta(days=45)}, doc)[0]
    for st in ("not_checked", "not_on_register", "expired"): assert not statement_valid({**base, "register_status": st}, doc)[0]

def test_register_file_check(tmp_path, monkeypatch):
    from backend.app import ps_register as pr
    monkeypatch.setattr(pr, "REG_DIR", tmp_path)
    assert pr.check("A Engineer", "Eng Ltd")["status"] == "not_checked"
    (tmp_path / "r.csv").write_text("name,company,registration_no,valid_until\nA Engineer,Eng Ltd,123,\nOld Eng,Old Ltd,9,2020-01-01\n")
    assert pr.check("a  engineer", "ENG LTD")["status"] == "valid"
    assert pr.check("Nobody", None)["status"] == "not_on_register"
    assert pr.check("Old Eng", "Old Ltd")["status"] == "expired"
    assert pr.check("A Engineer", "Other Co")["status"] == "not_on_register"

def test_ready_to_lodge_gate_and_full_path(client, monkeypatch):
    from backend.app import consent_pack as cp
    p = new_pack(client); pid = p["id"]
    r = client.post(f"/api/packs/{pid}/ready-to-lodge"); assert r.status_code == 409
    codes = {b["code"] for b in r.json()["detail"]["blockers"]}
    assert {"checklist_not_council_verified", "document_missing", "placeholders_remaining"} <= codes
    # even with every other gap closed, an unverified checklist keeps the gate shut
    verified = copy.deepcopy(cp.checklist()); verified["council_verified"] = True
    monkeypatch.setattr(cp, "checklist", lambda: verified)
    fields = {k: "x" for k in list(cp.FIELD_KEYS) if k != "fire_route"} | {"fire_route": "C/AS2"} | {f"clause_method.{c['clause']}": "m" for c in cp.clauses()} | {f"clause_evidence.{c['clause']}": "e" for c in cp.clauses()}
    assert client.put(f"/api/packs/{pid}/fields", json={"fields": fields}).status_code == 200
    for k, v in (("kitchens", 1), ("laundries", 1), ("lounge_dining_areas", 1), ("staff_office_rooms", 1), ("year_built", 1985), ("construction_type", "timber"), ("sprinklers", "none"), ("fire_alarm", "none"), ("level_access_entrances", 1),
                 ("bedrooms_total", 4), ("storeys_per_building", 1), ("gfa_m2", 300)):
        assert client.put(f"/api/property/{PARCEL}/facts", json={"field": k, "value": v, "source": "test", "confidence": "CONFIRMED"}).status_code == 200, k
    p = new_pack(client); pid = p["id"]; assert client.put(f"/api/packs/{pid}/fields", json={"fields": fields}).status_code == 200
    assert "lodgement_checklist_unanswered" in {b["code"] for b in client.get(f"/api/packs/{pid}/completeness").json()["blockers"]}
    assert client.put(f"/api/packs/{pid}/lodgement", json={"sections_na": [x["id"] for x in client.get(f"/api/packs/{pid}/lodgement").json()["sections"]]}).json()["unanswered"] == 0
    now = client.get(f"/api/packs/{pid}/completeness").json()
    # resolve screening FAILs with a stated resolution (the designer's), and upload every required slot with a valid author
    res = {b["detail"].split(":")[0]: "designer to resolve in PS1" for b in now["blockers"] if b["code"] == "compliance_fail"}
    assert client.put(f"/api/packs/{pid}/fields", json={"resolutions": res}).status_code == 200
    for d in client.get(f"/api/packs/{pid}").json()["completeness"]["documents"]:
        if d["kind"] == "upload_slot" and d["required"]:
            s = client.post(f"/api/packs/{pid}/documents/{d['doc_key']}/upload", files={"file": (d["doc_key"] + ".pdf", pdf_bytes(d["doc_key"]))}, data={"author_name": "A Engineer", "author_company": "Eng Ltd", "date_issued": str(date.today())}).json()
            if s["register_status"] != "not_applicable": client.post(f"/api/statements/{s['id']}/register-check", json={"status": "valid", "checked_by": "owner"})
    g = client.get(f"/api/packs/{pid}/completeness").json(); assert g["ready"], g["blockers"]
    assert client.post(f"/api/packs/{pid}/ready-to-lodge").json()["status"] == "ready_to_lodge"
    # any change withdraws the ready state
    client.put(f"/api/packs/{pid}/fields", json={"fields": {"owner_name": "Changed"}}); assert client.get(f"/api/packs/{pid}").json()["status"] == "draft"
    # one statement turning invalid blocks again
    sid = [s for s in client.get(f"/api/packs/{pid}/statements").json() if s["statement_type"] == "PS1"][0]["id"]
    client.post(f"/api/statements/{sid}/register-check", json={"status": "not_on_register", "checked_by": "owner"})
    assert client.post(f"/api/packs/{pid}/ready-to-lodge").status_code == 409
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/packs/{pid}/export.zip").content)); names = z.namelist()
    assert "Supporting Documents/PS1 Design.pdf" in names and any(n.startswith("Plans/Architectural Plan") and n.endswith(".pdf") for n in names)

def test_not_required_needs_a_reason(client):
    p = new_pack(client)
    assert client.put(f"/api/packs/{p['id']}/documents/tech_literature/required", json={"required": False}).status_code == 422
    r = client.put(f"/api/packs/{p['id']}/documents/ps1_services/required", json={"required": False, "reason": "no new services work"}); assert r.status_code == 200

def test_review_packages_flag_and_metrics(client):
    p = new_pack(client); pid = p["id"]
    rv = client.post(f"/api/packs/{pid}/reviews", json={"role": "fire", "engineer_name": "F Eng", "engineer_company": "Fire Ltd"}).json(); assert rv["status"] == "draft"
    s = client.post(f"/api/reviews/{rv['id']}/send").json(); assert s["link"] is None and s["status"] == "sent"      # flag OFF: no working link issued
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/reviews/{rv['id']}/package.zip").content)); assert "Brief.pdf" in z.namelist() and "Documents wanted from you.txt" in z.namelist()
    assert STAMP in pymupdf.open(stream=z.read("Brief.pdf"), filetype="pdf")[0].get_text().replace("\n", " ")
    from tests.conftest import RAW_TESTCLIENT
    from backend.app.main import app
    anon = RAW_TESTCLIENT(app)
    assert anon.get("/review/abc").status_code == 404 and anon.get("/api/review/abc").status_code == 404
    assert anon.get("/api/packs/1").status_code == 401                         # everything else still needs the login
    assert client.put("/api/flags/engineer_review_links", json={"enabled": True}).json()["enabled"] is True
    s = client.post(f"/api/reviews/{rv['id']}/send").json(); tok = s["link"].rsplit("/", 1)[1]
    assert anon.get("/review/" + tok).status_code == 200
    page = anon.get("/api/review/" + tok).json(); assert page["role"] == "fire" and STAMP in page["label"]
    assert anon.get("/api/review/wrong-token").status_code == 404
    assert anon.post(f"/api/review/{tok}/comment", json={"author": "F Eng", "body": "Need exit widths"}).status_code == 200
    assert client.get(f"/api/packs/{pid}/reviews").json()[0]["status"] == "commented"
    assert anon.post(f"/api/review/{tok}/return", json={"author": "F Eng", "body": ""}).status_code == 200
    assert anon.get("/api/review/" + tok).status_code == 404                        # link dies on return
    v = client.get(f"/api/packs/{pid}/reviews").json()[0]; assert v["status"] == "returned" and [e["kind"] for e in v["events"]][-1] == "returned"
    m = client.get("/api/reviews/metrics").json()["by_role"]["fire"]; assert m["returned"] >= 1 and m["median_turnaround_hours"] is not None
    # a cancelled package's link stops working; turning the flag off stops every link
    rv2 = client.post(f"/api/packs/{pid}/reviews", json={"role": "structural"}).json(); t2 = client.post(f"/api/reviews/{rv2['id']}/send").json()["link"].rsplit("/", 1)[1]
    assert anon.get("/api/review/" + t2).status_code == 200
    client.put("/api/flags/engineer_review_links", json={"enabled": False}); assert anon.get("/api/review/" + t2).status_code == 404

def test_flags_default_off(client):
    from backend.app import flags
    client.put("/api/flags/engineer_review_links", json={"enabled": False})
    assert all(f["enabled"] is False for f in flags.all_flags())
    assert flags.enabled("never_defined") is False
    assert client.put("/api/flags/not_a_flag", json={"enabled": True}).status_code == 404


# ---------------------------------------------------------------- AC1009 (Council lodgement checklist, v.21 June 2026)
def test_ac1009_is_loaded_in_full():
    from backend.app import consent_pack as cp
    d = cp.ac1009(); items = [it for s in d["sections"] for it in s["items"]]
    assert d["form"]["code"] == "AC1009" and d["form"]["version"] == "v.21" and len(d["sections"]) == 45 and len(items) == 151
    assert len({it["id"] for it in items}) == 151 and sum(1 for it in items if it["ps"]) >= 8
    assert {"G3", "G5", "F6", "C", "D1", "B1"} <= {s["title"].split()[0] for s in d["sections"]} | {"B1", "C"}
    assert any("90 days" in r for r in d["rules"]) and set(d["fire_routes"]) == {"C/AS2", "C/VM2", "alternative_solution"}

def test_lodgement_answers_validate_and_block_until_answered(client):
    p = new_pack(client); pid = p["id"]; lv = client.get(f"/api/packs/{pid}/lodgement").json(); assert lv["unanswered"] == 151
    assert client.put(f"/api/packs/{pid}/lodgement", json={"answers": {"nope.1": "yes"}}).status_code == 422
    assert client.put(f"/api/packs/{pid}/lodgement", json={"answers": {"general.1": "maybe"}}).status_code == 422
    r = client.put(f"/api/packs/{pid}/lodgement", json={"answers": {"general.1": "yes"}, "sections_na": ["f9"]}).json()
    assert r["unanswered"] == 151 - 1 - 9 and next(s for s in r["sections"] if s["id"] == "f9")["section_na"] is True
    assert client.put(f"/api/packs/{pid}/lodgement", json={"answers": {"general.1": None}}).json()["unanswered"] == 151 - 9
    md = client.get(f"/api/packs/{pid}/documents/lodgement_checklist.md").text
    assert "AC1009" in md and "TO COMPLETE" in md and STAMP in md

def test_ninety_day_rule_and_fire_route(client):
    from datetime import date, timedelta
    p = new_pack(client); pid = p["id"]
    url = f"/api/packs/{pid}/documents/record_of_title/upload"
    old = client.post(url, files={"file": ("rot.pdf", pdf_bytes())}, data={"date_issued": str(date.today() - timedelta(days=120))}).json()
    assert old["valid"] is False and any("90 days" in x for x in old["problems"])
    assert client.post(url, files={"file": ("rot.pdf", pdf_bytes("new"))}, data={"date_issued": str(date.today() - timedelta(days=10))}).json()["valid"] is True
    ps = client.post(f"/api/packs/{pid}/documents/ps1_structural/upload", files={"file": ("p.pdf", pdf_bytes())}, data={"author_name": "A", "author_company": "C", "date_issued": str(date.today() - timedelta(days=100))}).json()
    client.post(f"/api/statements/{ps['id']}/register-check", json={"status": "valid", "checked_by": "o"})
    st = [s for s in client.get(f"/api/packs/{pid}/statements").json() if s["id"] == ps["id"]][0]; assert st["valid"] is False and any("90 days" in x for x in st["problems"])
    codes = lambda: {b["code"] for b in client.get(f"/api/packs/{pid}/completeness").json()["blockers"]}
    assert "fire_route_not_chosen" in codes()
    assert client.put(f"/api/packs/{pid}/fields", json={"fields": {"fire_route": "magic"}}).status_code == 422
    docs = lambda: {d["doc_key"]: d["required"] for d in client.get(f"/api/packs/{pid}/completeness").json()["documents"]}
    client.put(f"/api/packs/{pid}/fields", json={"fields": {"fire_route": "C/VM2"}}); d = docs()
    assert d["fire_engineering_brief"] and d["ps2_review"] and not d["ps1_fire"]           # AC1009 p4: VM2 needs the brief and PS2 review evidence
    client.put(f"/api/packs/{pid}/fields", json={"fields": {"fire_route": "C/AS2"}}); d = docs()
    assert d["ps1_fire"] and not d["fire_engineering_brief"] and not d["ps2_review"]
    client.put(f"/api/packs/{pid}/fields", json={"fields": {"fire_route": "alternative_solution"}}); d = docs()
    assert d["ps1_fire"] and d["fire_engineering_brief"] and not d["ps2_review"]
    assert not docs()["owner_authorisation"]; client.put(f"/api/packs/{pid}/fields", json={"fields": {"agent_name": "An Agent"}}); assert docs()["owner_authorisation"]

def test_drawings_carry_the_ac1009_title_block(client):
    p = new_pack(client); pid = p["id"]; client.put(f"/api/packs/{pid}/fields", json={"fields": {"designer_name": "D Signer Ltd", "owner_name": "Owner Co"}})
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/packs/{pid}/export.zip").content))
    pdfn = [n for n in z.namelist() if n.startswith("Plans/Architectural Plan") and n.endswith(".pdf")][0]
    txt = pymupdf.open(stream=z.read(pdfn), filetype="pdf")[0].get_text().replace("\n", " ")
    for want in ("Address:", "Legal description:", "Drawing A-01", "D Signer Ltd", "Owner Co", "Dated:", "DRAFT: NOT FOR CONSENT"): assert want in txt, want
