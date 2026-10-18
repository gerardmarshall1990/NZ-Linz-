"""Field capture, CRM extras, call sheets / routes, offer generator: all behind feature flags (off by default); guardrails with the flags on."""
import os
import pytest
from fastapi.testclient import TestClient
from tests.test_step2 import PARCEL as CONV, plan_dxf
from tests.test_scenarios_api import FULL
from backend.app.db import conn
CAP = 4756180

def tiny_pdf():
    import pymupdf
    d = pymupdf.open(); d.new_page(); return d.tobytes()

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads_out"))
    from backend.app.main import app
    def clean():
        with conn() as c:
            c.execute("DELETE FROM core.user_field_capture"); c.execute("DELETE FROM core.user_audit_log"); c.execute("DELETE FROM core.user_offer_doc"); c.execute("DELETE FROM core.user_route_plan")
            c.execute("DELETE FROM core.user_crm_activity"); c.execute("DELETE FROM core.user_crm_lead"); c.execute("DELETE FROM core.user_crm_do_not_contact"); c.execute("DELETE FROM core.rh_approval")
            for t in ("rh_scenario", "rh_brief", "rh_check_run", "rh_layout_option", "rh_evidence_gap_status"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id IN (%s,%s)", (CONV, CAP))
            c.execute("DELETE FROM core.rh_plan_edit WHERE extraction_id IN (SELECT x.id FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id IN (%s,%s))", (CONV, CAP))
            c.execute("DELETE FROM core.rh_plan_extraction WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id IN (%s,%s))", (CONV, CAP)); c.execute("DELETE FROM core.rh_plan_calibration WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id IN (%s,%s))", (CONV, CAP))
            for t in ("rh_upload", "rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id IN (%s,%s)", (CONV, CAP))
            c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history"); c.commit()
    clean(); yield TestClient(app); clean()

@pytest.fixture()
def on(monkeypatch):
    from backend.app import flags
    monkeypatch.setattr(flags, "gated_flags", lambda: {"outreach_enabled": True, "field_capture_enabled": True, "offer_letters_enabled": True})

def test_everything_is_403_while_flags_are_off(client):
    for m, p in (("get", "/field"), ("get", "/field/sw.js"), ("post", "/api/field/capture"), ("post", "/api/call-sheets"), ("post", "/api/offer-letters"), ("get", "/api/crm/audit"), ("get", "/api/crm/funnel/rep"), ("get", "/crm")): assert getattr(client, m)(p).status_code == 403, p

def test_field_capture_permission_first_then_documented_then_confirmed(client, on):
    base = {"parcel_id": CAP, "rep_name": "Rep One", "values": {"corridor_width_min_m": 1.1, "sprinklers": "none"}, "rooms": [{"type": "bedroom"}, {"type": "bedroom"}, {"type": "kitchen"}, {"type": "ensuite"}]}
    r = client.post("/api/field/capture", json=base); assert r.status_code == 422 and "permission first" in r.json()["detail"]
    assert any(a["action"] == "capture_refused" for a in client.get("/api/crm/audit").json())
    assert client.post("/api/field/capture", json={**base, "permission_given_by": "A Owner (owner)", "values": {"gfa_m2": 5}}).status_code == 422           # not on the capture form
    assert client.post("/api/field/capture", json={**base, "permission_given_by": "A Owner (owner)", "rooms": [{"type": "dungeon"}]}).status_code == 422
    cap = client.post("/api/field/capture", json={**base, "permission_given_by": "A Owner (owner)", "gps": {"lat": -36.9, "lon": 174.7}}).json(); assert cap["status"] == "pending_review"
    f = client.get(f"/api/property/{CAP}").json()["facts"]
    assert f["bedrooms_total"]["value"] == 2 and f["kitchens"]["value"] == 1 and f["rooms_with_ensuite"]["value"] == 1 and f["corridor_width_min_m"]["confidence"] == "DOCUMENTED" and "permission: A Owner" in f["corridor_width_min_m"]["source"]
    assert client.post(f"/api/field/captures/{cap['id']}/review", json={"accept": True}).json()["status"] == "confirmed"
    assert client.get(f"/api/property/{CAP}").json()["facts"]["bedrooms_total"]["confidence"] == "CONFIRMED" and client.post(f"/api/field/captures/{cap['id']}/review", json={"accept": True}).status_code == 409
    c2 = client.post("/api/field/capture", json={**base, "permission_given_by": "Agent", "values": {"stairs_count": 3}}).json(); assert client.post(f"/api/field/captures/{c2['id']}/review", json={"accept": False}).json()["status"] == "rejected"
    html = client.get("/field").text; assert "Permission first" in html and "manifest.json" in html and "localStorage" in html and client.get("/field/manifest.json").json()["display"] == "standalone"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 60; assert client.post("/api/field/photo", data={"parcel_id": CAP}, files={"file": ("p.png", png)}).json()["upload_id"]
    assert client.post("/api/field/photo", data={"parcel_id": CAP}, files={"file": ("p.pdf", tiny_pdf())}).status_code == 415

def test_field_capture_refused_on_do_not_contact_parcel(client, on):
    client.post("/api/crm/do-not-contact", json={"reason": "owner asked", "parcel_id": 4888673})
    assert client.post("/api/field/capture", json={"parcel_id": 4888673, "rep_name": "R", "permission_given_by": "x", "values": {}}).status_code == 409

def test_crm_page_and_funnel_dimensions_audit_and_lists(client, on):
    assert "do-not-contact" in client.get("/crm").text
    L = client.post("/api/crm/leads", json={"parcel_id": CAP}).json()
    client.put(f"/api/crm/leads/{L['id']}", json={"assigned_rep": "Rep One", "counterparty_type": "owner", "source": "title copy", "lawful_basis": "legitimate interest"}); client.put(f"/api/crm/leads/{L['id']}/contactable", json={"contactable": True})
    assert any(x["id"] == L["id"] for x in client.get("/api/crm/leads", params={"rep": "Rep One"}).json())
    f = client.get("/api/crm/funnel/rep").json(); assert f["funnel"]["Rep One"]["new"] == 1 and set(client.get("/api/crm/funnel/suburb").json()["funnel"])
    assert client.get("/api/crm/funnel/colour").status_code == 422
    client.get(f"/api/crm/leads/{L['id']}"); client.post(f"/api/crm/leads/{L['id']}/activities", json={"kind": "call"})
    acts = [a["action"] for a in client.get("/api/crm/audit").json()]; assert {"lead_view", "contact_attempt", "lead_list"} <= set(acts)

def test_route_ordering_hand_calculated_and_call_sheet(client, on):
    from backend.app import routeplan
    stops = [{"lat": 0.0, "lon": 0.0, "n": "A"}, {"lat": 0.0, "lon": 0.1, "n": "B"}, {"lat": 0.0, "lon": 0.05, "n": "C"}]
    o = routeplan.order(stops, (0.0, 0.0)); assert [s["n"] for s in o] == ["A", "C", "B"] and o[0]["leg_km"] == 0 and o[1]["leg_km"] == pytest.approx(5.56, abs=0.05)
    with conn() as c: ids = [r["parcel_id"] for r in c.execute("SELECT parcel_id FROM analytics.rh_screen WHERE suburb IS NOT NULL AND beds_base >= 8 ORDER BY parcel_id LIMIT 6").fetchall()]
    cs = client.post("/api/call-sheets", json={"parcel_ids": ids, "name": "test run"}).json()
    assert cs["distance_basis"] == "straight-line" and cs["plan"] and "Never the tenant" in cs["markdown"] and "[TO COMPLETE: your answers]" in cs["markdown"] and "straight-line" in cs["markdown"]
    assert sum(len(c["stops"]) for c in cs["plan"]) == len(ids) and client.post("/api/call-sheets", json={"parcel_ids": []}).status_code == 422
    assert client.post("/api/call-sheets/pdf", json={"parcel_ids": ids}).content[:4] == b"%PDF"

def test_offer_generator_guardrails(client, on):
    from backend.app import retrofit
    assert client.post(f"/api/property/{CONV}").status_code == 200
    u = client.post(f"/api/property/{CONV}/uploads", files={"file": ("plan.dxf", plan_dxf())}).json(); e = client.post(f"/api/uploads/{u['id']}/extract", json={"mode": "auto"}).json()
    assert client.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE"}).status_code == 200; oid = client.post(f"/api/property/{CONV}/layouts").json()[0]["id"]
    client.put("/api/settings/assumptions", json={"values": FULL})
    off = client.post(f"/api/property/{CONV}/offers", json={"option_id": oid, "asking_rent": 1000, "terms": {"multiple": 1.5, "s": 0.4}, "retrofit": 300000}).json(); sid = off["scenario_id"]; walk = off["walk_away_rent_per_week"]
    mk = lambda **k: client.post("/api/offer-letters", json={"kind": "terms_sheet", "scenario_id": sid, "mode": "jv", **k})
    assert mk(rent_offered=walk + 1).status_code == 422 and "walk-away" in mk(rent_offered=walk + 1).json()["detail"]            # never above the walk-away rent
    t = mk(rent_offered=walk - 1, terms={"term": "10 years"}).json(); assert "LAWYER REVIEW REQUIRED" in t["markdown"] and "(not a contract)" in t["markdown"] and "10 years" in t["markdown"] and "[TO COMPLETE]" in t["markdown"] and t["version"] == 1
    assert mk(rent_offered=walk - 1).json()["version"] == 2
    L = client.post("/api/crm/leads", json={"parcel_id": CONV}).json()
    assert mk(rent_offered=walk - 1, lead_id=L["id"]).status_code == 409                                                           # not contactable
    client.put(f"/api/crm/leads/{L['id']}", json={"counterparty_type": "landlord", "source": "listing agent as published", "lawful_basis": "legitimate interest"}); client.put(f"/api/crm/leads/{L['id']}/contactable", json={"contactable": True})
    em = client.post("/api/offer-letters", json={"kind": "email", "scenario_id": sid, "mode": "jv", "lead_id": L["id"], "sender": "Me Ltd, 1 Road, 021 000"}).json()
    assert "UNSUBSCRIBE" in em["markdown"] and "Me Ltd" in em["markdown"] and "may not be met" in em["markdown"]
    for kind in ("letter", "one_page"):
        d = client.post("/api/offer-letters", json={"kind": kind, "scenario_id": sid, "mode": "jv", "lead_id": L["id"]}).json(); low = d["markdown"].lower()
        assert "lawyer review required" in low and not any(w in low for w in ("guarantee", "will be granted", " approved "))
    s = client.post(f"/api/offer-letters/{em['id']}/sent"); assert s.status_code == 409 and s.json()["detail"]["approval_required"]
    client.post(f"/api/approvals/{s.json()['detail']['approval_id']}/decide", json={"approve": True}); assert client.post(f"/api/offer-letters/{em['id']}/sent").json()["status"] == "sent_recorded"
    client.post("/api/crm/do-not-contact", json={"reason": "asked", "parcel_id": CONV}); assert client.post("/api/offer-letters", json={"kind": "letter", "scenario_id": sid, "mode": "jv", "lead_id": L["id"]}).status_code == 409
    assert len(client.get("/api/offer-letters", params={"scenario_id": sid}).json()) >= 4
