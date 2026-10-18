"""Capture guide, RFI tracker, timeline and tracks, milestones, effort metrics, certification checklist, approvals."""
from datetime import date, timedelta
import pymupdf, pytest
from fastapi.testclient import TestClient
from tests.test_step2 import PARCEL

@pytest.fixture(scope="module")
def client():
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            for t in ("rh_rfi", "rh_milestone", "rh_cert_item"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.rh_approval"); c.execute("DELETE FROM core.rh_effort_log"); c.execute("DELETE FROM core.user_setting WHERE key LIKE 'track:%' OR key LIKE 'structure_light:%'")
            for t in ("rh_plan_request", "rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.commit()
    clean(); cl = TestClient(app); assert cl.post(f"/api/property/{PARCEL}").status_code == 200; yield cl; clean()

def fact(client, f, v): assert client.put(f"/api/property/{PARCEL}/facts", json={"field": f, "value": v, "source": "test", "confidence": "CONFIRMED"}).status_code == 200

def test_capture_guide_lists_only_what_is_unknown(client):
    md = client.get(f"/api/property/{PARCEL}/capture-guide").text
    assert "Capture guide" in md and "Narrowest corridor clear width (m)  (now: unknown)" in md and "permission" in md
    client.post(f"/api/property/{PARCEL}/site-visit", json={"values": {"corridor_width_min_m": 1.4}})
    md2 = client.get(f"/api/property/{PARCEL}/capture-guide").text
    assert "Narrowest corridor clear width (m)  (now: unknown)" not in md2 and "Narrowest corridor clear width (m): 1.4 (CONFIRMED)" in md2
    assert "Capture guide" in pymupdf.open(stream=client.get(f"/api/property/{PARCEL}/capture-guide.pdf").content, filetype="pdf")[0].get_text()

def test_rfi_tracker(client):
    today = date.today(); base = {"received_on": str(today - timedelta(days=10)), "summary": "Fire report queries", "items": [{"text": "Provide travel distances", "owner_role": "fire engineer"}, {"text": "Confirm ensuite ventilation"}]}
    assert client.post(f"/api/property/{PARCEL}/rfis", json={**base, "received_on": str(today + timedelta(days=1))}).status_code == 422
    assert client.post(f"/api/property/{PARCEL}/rfis", json={**base, "items": []}).status_code == 422
    assert client.post(f"/api/property/{PARCEL}/rfis", json={**base, "due_on": str(today - timedelta(days=20))}).status_code == 422
    r = client.post(f"/api/property/{PARCEL}/rfis", json={**base, "due_on": str(today - timedelta(days=1)), "council_ref": "BC-1"}).json()
    assert r["overdue"] is True and r["open_items"] == 2 and any(x["id"] == r["id"] for x in client.get("/api/rfis/overdue").json())
    assert client.post(f"/api/rfis/{r['id']}/responded", json={}).status_code == 409                 # items still open
    i1, i2 = [i["id"] for i in r["items"]]
    assert client.put(f"/api/rfi-items/{i1}", json={"status": "answered"}).status_code == 422          # an answer needs its text
    client.put(f"/api/rfi-items/{i1}", json={"status": "answered", "response": "Travel distance 18 m per fire report v2"}); client.put(f"/api/rfi-items/{i2}", json={"status": "not_applicable"})
    a = client.post(f"/api/rfis/{r['id']}/responded", json={}); assert a.status_code == 409 and a.json()["detail"]["approval_required"]       # needs an approval record
    client.post(f"/api/approvals/{a.json()['detail']['approval_id']}/decide", json={"approve": True})
    done = client.post(f"/api/rfis/{r['id']}/responded", json={}).json(); assert done["status"] == "responded" and done["overdue"] is False
    assert client.post(f"/api/rfis/{r['id']}/close").json()["status"] == "closed"

def test_timeline_scenarios_tracks_and_can_hit_target(client):
    t = client.get(f"/api/property/{PARCEL}/timeline").json()
    assert [(s["key"], s["weeks"]) for s in t["stages"]] == [("consent_weeks", 4), ("works_weeks", 8), ("audit_weeks", 4), ("fill_weeks", 4)] and t["total_weeks"] == 20
    d = client.get(f"/api/property/{PARCEL}/timeline", params={"scenario": "delay"}).json(); assert d["stages"][0]["weeks"] == 17 and d["total_weeks"] == 33
    c = client.get(f"/api/property/{PARCEL}/timeline", params={"scenario": "contract"}).json(); assert c["stages"] is None and c["total_months"] == 9 and "phase split" in c["note"]
    o = client.get(f"/api/property/{PARCEL}/timeline", params={"opening": "2027-06-01"}).json(); assert o["start_date"] == "2027-01-12" and o["stages"][-1]["end_date"] == "2027-06-01"
    assert all(tr["lead_weeks"] is None and tr["note"] == "set lead time" for tr in o["parallel_tracks"])               # no lead time is guessed
    assert client.put("/api/timeline/tracks/policies", json={"lead_weeks": 6}).status_code == 422                       # needs a source
    client.put("/api/timeline/tracks/policies", json={"lead_weeks": 6, "source": "operator said"})
    p = next(x for x in client.get(f"/api/property/{PARCEL}/timeline", params={"opening": "2027-06-01"}).json()["parallel_tracks"] if x["key"] == "policies"); assert p["start_date"] == "2027-04-20"
    assert client.put("/api/timeline/tracks/nope", json={}).status_code == 404
    assert t["can_hit_target"]["verdict"] == "unknown" and any("structural" in u for u in t["can_hit_target"]["unknown"])
    fact(client, "storeys_per_building", 1); fact(client, "sprinklers", "full"); fact(client, "fire_alarm", "full")
    assert client.put(f"/api/property/{PARCEL}/structure-light", json={"light": True}).json()["verdict"] == "can_hit_target"
    assert client.put(f"/api/property/{PARCEL}/structure-light", json={"light": False}).json()["verdict"] == "contract_only"
    client.put(f"/api/property/{PARCEL}/structure-light", json={"light": True}); fact(client, "sprinklers", "none")
    v = client.get(f"/api/property/{PARCEL}/timeline").json()["can_hit_target"]; assert v["verdict"] == "contract_only" and "no sprinklers in place" in v["blockers"]

def test_timeline_scenario_feeds_offer_weeks_but_not_contract():
    from backend.app import timeline
    from fastapi import HTTPException
    assert timeline.weeks_for("delay")["consent_weeks"] == 17
    with pytest.raises(HTTPException): timeline.weeks_for("contract")

def test_milestones_and_metrics(client):
    today = date.today()
    ms = client.put(f"/api/property/{PARCEL}/milestones/lodged", json={"planned_on": str(today - timedelta(days=5)), "actual_on": str(today - timedelta(days=2))}).json()
    assert next(m for m in ms if m["key"] == "lodged")["days_late"] == 3 and len(ms) == 8
    assert client.put(f"/api/property/{PARCEL}/milestones/bogus", json={}).status_code == 422 and client.put(f"/api/property/{PARCEL}/milestones/certified", json={"actual_on": str(today + timedelta(days=1))}).status_code == 422
    assert client.get("/api/metrics").json()["by_step"] == [] and client.get("/api/metrics").json()["avg_minutes_per_property"] is None
    client.post("/api/metrics/minutes", json={"parcel_id": PARCEL, "step": "plan_review", "minutes": 30}); m = client.post("/api/metrics/minutes", json={"parcel_id": PARCEL, "step": "plan_review", "minutes": 10}).json()
    assert m["by_step"][0]["total"] == 40 and m["by_step"][0]["avg"] == 20 and m["avg_minutes_per_property"] == 40
    assert client.post("/api/metrics/minutes", json={"step": "nap", "minutes": 1}).status_code == 422 and client.post("/api/metrics/minutes", json={"step": "other", "minutes": -1}).status_code == 422

def test_certification_checklist_and_templates(client):
    v = client.get(f"/api/property/{PARCEL}/certification").json()
    assert v["certification_done"] == "0/8" and "not yet loaded" in v["warning"] and all(i["status"] == "not_started" for i in v["certification"])
    v = client.put(f"/api/property/{PARCEL}/certification/legal_entity", json={"status": "done", "note": "NZBN"}).json(); assert v["certification_done"] == "1/8"
    assert client.put(f"/api/property/{PARCEL}/certification/nope", json={"status": "done"}).status_code == 404 and client.put(f"/api/property/{PARCEL}/certification/legal_entity", json={"status": "great"}).status_code == 422
    t = client.get("/api/certification/templates/policies").text; assert "NOT A POLICY" in t and t.count("[TO COMPLETE") >= 6 and "DRAFT: NOT FOR CONSENT" in t
    assert "lease_conditions" in v and len(v["lease_conditions"]) == 9
