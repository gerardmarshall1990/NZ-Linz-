"""Site Panel flow for development sites: button 1 (scenarios), button 2 (report), button 3 (resource consent pack), services module."""
import io, os, zipfile
import pymupdf, pytest
from fastapi.testclient import TestClient
PARCEL = 4756180; STAMP = "DRAFT: NOT FOR CONSENT until reviewed and issued by a qualified professional"
INP = {"typology": "houses", "unit": {"width_m": 7, "depth_m": 10, "height_m": 7.5, "wall_height_m": 5.5, "gfa_m2": 120, "bedrooms": 3}, "access_width_m": 3.5,
       "finance": {"price_per_unit": 900000, "build_cost_per_m2": 3000, "site_works_allowance": 100000, "contingency_pct": 10, "land_cost": 1500000, "consent_professional_fees": 150000, "development_contributions": 100000, "holding_months": 18, "interest_rate_pct": 8, "selling_costs_pct": 3},
       "timeline_weeks": {"pre_application": 4, "lodgement": 1}}

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads_dev"))
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            c.execute("DELETE FROM core.user_rc_pack WHERE run_id IN (SELECT id FROM core.user_dev_run WHERE parcel_id=%s)", (PARCEL,)); c.execute("DELETE FROM core.user_dev_run WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.user_site_services WHERE parcel_id=%s", (PARCEL,)); c.execute("DELETE FROM core.rh_upload WHERE parcel_id=%s", (PARCEL,))
            for t in ("rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.commit()
    clean(); yield TestClient(app); clean()

def pdf_bytes(t="x"): d = pymupdf.open(); d.new_page().insert_text((72, 72), t); return d.tobytes()
def text(b): return " ".join(p.get_text() for p in pymupdf.open(stream=b, filetype="pdf")).replace("\n", " ").replace("ﬁ", "fi")

def test_report_needs_button_1_first(client):
    assert client.get(f"/api/dev/{PARCEL}/report").status_code == 409 and client.post(f"/api/dev/{PARCEL}/rc-pack", json={}).status_code == 409

def test_button_1_scenarios_and_validation(client):
    assert client.post(f"/api/dev/{PARCEL}/scenarios", json={"typology": "apartments"}).status_code == 422
    assert client.post(f"/api/dev/{PARCEL}/scenarios", json={"typology": "houses", "unit": {"width_m": -1}}).status_code == 422
    assert client.post(f"/api/dev/{PARCEL}/scenarios", json={"typology": "houses", "timeline_weeks": {"nap": 2}}).status_code == 422
    r = client.post(f"/api/dev/{PARCEL}/scenarios", json=INP).json()
    assert r["status"] == "ok" and r["scenarios"][0]["kind"] == "compliant" and r["financials"]["status"] == "ok" and r["financials"]["profit"] is not None and r["sensitivity"]["status"] == "ok" and r["break_even_build_cost_per_m2"]
    assert r["badge"] == "incomplete" and r["open_items"] and any("vehicle_access" in x for x in r["open_items"]) and r["candidates_evaluated"] >= 20 and r["site"]["hazards"]["note"]
    assert client.get(f"/api/dev/{PARCEL}/latest").json()["run_id"] == r["run_id"]
    lots = client.post(f"/api/dev/{PARCEL}/scenarios", json={**INP, "typology": "lots"}).json(); assert lots["subdivision"]["max_lots_by_area"] >= 2 and "frontage" in lots["subdivision"]["note"]
    client.post(f"/api/dev/{PARCEL}/scenarios", json=INP)

def test_button_2_detailed_report(client):
    md = client.get(f"/api/dev/{PARCEL}/report").text
    for n in range(1, 12): assert f"## {n}. " in md, n
    assert "set duration" in md and "| pre application | 4 |" in md and "needs rate" in md
    assert "Binding constraint" in md and "Formulas:" in md and "not yet" in md and "Screening and preparation tool" in md and "UNKNOWN" in md
    t = text(client.get(f"/api/dev/{PARCEL}/report.pdf").content); assert "Detailed development report" in t
    for w in ("guarantee", "will be granted", " approved "): assert w not in md.lower()
    client.post(f"/api/dev/{PARCEL}/scenarios", json={"typology": "houses", "unit": {"width_m": 7}})        # a needs-input run
    assert client.get(f"/api/dev/{PARCEL}/report").status_code == 409
    client.post(f"/api/dev/{PARCEL}/scenarios", json=INP)

def test_services_licence_aware_capacity_unknown_until_letter(client):
    s = client.get(f"/api/property/{PARCEL}/services").json()
    assert s["capacity_status"] == "UNKNOWN" and {x["key"]: x["status"] for x in s["sources"]}["watercare"] == "not_loaded" and all(l["status"] == "needs rate" for l in s["cost_lines"]) and "Watercare" in s["confirmations_needed"][0]
    assert client.put(f"/api/property/{PARCEL}/services", json={"water_main_dist_m": -3}).status_code == 422 and client.put(f"/api/property/{PARCEL}/services", json={"watercare_api": 1}).status_code == 422
    s = client.put(f"/api/property/{PARCEL}/services", json={"water_main_dist_m": 12.5, "power_flag": "overhead"}).json(); assert s["completeness"].startswith("2/") and s["manual"]["water_main_dist_m"] == 12.5
    assert client.put(f"/api/property/{PARCEL}/services", json={"capacity_status": "CONFIRMED"}).status_code == 422          # needs the letter
    assert client.put(f"/api/property/{PARCEL}/services", json={"capacity_status": "INDICATIVE_OK"}).json()["capacity_status"] == "INDICATIVE_OK"
    client.post(f"/api/property/{PARCEL}")
    up = client.post(f"/api/property/{PARCEL}/uploads", files={"file": ("letter.pdf", pdf_bytes())}, data={"kind": "document"}).json()
    assert client.put(f"/api/property/{PARCEL}/services", json={"confirmation_upload_id": up["id"] + 999}).status_code == 422
    ok = client.put(f"/api/property/{PARCEL}/services", json={"capacity_status": "CONFIRMED", "confirmation_upload_id": up["id"]}).json(); assert ok["capacity_status"] == "CONFIRMED"

def test_button_3_resource_consent_pack(client):
    p = client.post(f"/api/dev/{PARCEL}/rc-pack", json={}).json(); pid = p["id"]
    assert p["council_verified"] is False and p["status"] == "draft"
    codes = {b["code"] for b in p["completeness"]["blockers"]}; assert {"checklist_not_council_verified", "document_missing", "placeholders_remaining"} <= codes
    for k in ("cover_index", "application_form", "cover_letter", "aee", "site_description", "affected_parties", "servicing_statement", "consultation_record"):
        md = client.get(f"/api/rc-packs/{pid}/documents/{k}.md").text; assert STAMP in md, k
    aee = client.get(f"/api/rc-packs/{pid}/documents/aee.md").text; assert "| Yards |" in aee and "H" in aee and "[TO COMPLETE: planner" in aee
    assert client.get(f"/api/rc-packs/{pid}/documents/title_easements.md").status_code == 409                       # an upload slot: nothing generated
    assert client.post(f"/api/rc-packs/{pid}/documents/plans/upload", files={"file": ("p.png", b"\x89PNG\r\n\x1a\n" + b"0" * 40)}).status_code == 415
    assert client.post(f"/api/rc-packs/{pid}/documents/plans/upload", files={"file": ("p.pdf", pdf_bytes())}).json()["completeness"]["documents"][6]["status"] == "uploaded"
    assert client.put(f"/api/rc-packs/{pid}/fields", json={"fields": {"applicant_name": "A Applicant", "bogus": "x"}}).status_code == 422
    assert client.put(f"/api/rc-packs/{pid}/fields", json={"fields": {"applicant_name": "A Applicant"}}).json()["fields"]["applicant_name"] == "A Applicant"
    assert client.post(f"/api/rc-packs/{pid}/ready-to-lodge").status_code == 409
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/rc-packs/{pid}/export.zip").content)); names = z.namelist()
    assert "README.txt" in names and "Upload sheet.pdf" in names and any(n.startswith("01 ") for n in names) and any("MISSING" in z.read("README.txt").decode() for _ in [0])
    assert STAMP in text(z.read([n for n in names if n.startswith("04 ")][0]))
    p2 = client.post(f"/api/dev/{PARCEL}/rc-pack", json={}).json(); assert p2["version"] == p["version"] + 1 and client.get(f"/api/rc-packs/{pid}").json()["status"] == "superseded"

def test_parking_assumption_is_an_editable_flagged_input_with_0_1_2_sensitivity(client):
    r = client.post(f"/api/dev/{PARCEL}/scenarios", json={**INP, "parking_spaces_per_unit": 1}).json()
    a = r["assumptions"][0]; assert a["key"] == "parking_spaces_per_unit" and a["value"] == 1 and a["flag"] == "assumption" and a["source"] == "your input"
    assert [p["spaces_per_unit"] for p in r["parking_sensitivity"]] == [0, 1, 2] and r["parking_sensitivity"][0]["driveway"]["status"] == "NOT_APPLICABLE"
    assert all(p["unit_count"] >= 1 for p in r["parking_sensitivity"])
    assert client.post(f"/api/dev/{PARCEL}/scenarios", json={**INP, "parking_spaces_per_unit": 9}).status_code == 422
    d = client.post(f"/api/dev/{PARCEL}/scenarios", json=INP).json()["assumptions"][0]; assert d["value"] == 2 and d["source"].startswith("default")
    client.post(f"/api/dev/{PARCEL}/scenarios", json=INP)
