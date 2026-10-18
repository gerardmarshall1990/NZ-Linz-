"""Part 8 scale design: approval queue extras, tasks, next best action, dashboard, capture portal, engineer workflow, capacity planner."""
import io, os
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from backend.app.db import conn
from tests.test_screen import FULL
P = 4756180

def png(kind="sharp"):
    from PIL import Image
    import numpy as np
    rng = np.random.default_rng(1)
    a = {"sharp": rng.integers(0, 256, (800, 800), dtype="uint8"), "dark": np.zeros((800, 800), dtype="uint8"), "flat": np.full((800, 800), 128, dtype="uint8")}[kind]
    b = io.BytesIO(); Image.fromarray(a).convert("RGB").save(b, "PNG"); return b.getvalue()

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads_scale"))
    from backend.app.main import app
    def clean():
        with conn() as c:
            for t in ("user_task", "user_comment_template", "user_capture_link", "rh_approval", "rh_effort_log", "rh_milestone"): c.execute(f"DELETE FROM core.{t}")
            for t in ("rh_check_run", "rh_brief", "rh_layout_option", "rh_scenario"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (P,))
            c.execute("DELETE FROM core.rh_review_package"); c.execute("DELETE FROM core.user_engineer"); c.execute("DELETE FROM core.rh_pack WHERE parcel_id=%s", (P,))
            c.execute("DELETE FROM analytics.rh_screen WHERE parcel_id=999999990"); c.execute("DELETE FROM core.user_listing WHERE source_id LIKE 'TSCALE-%'")
            c.execute("DELETE FROM core.user_flag WHERE key='capture_portal_links'"); c.execute("DELETE FROM core.rh_upload WHERE parcel_id=%s", (P,))
            for t in ("rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (P,))
            c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history"); c.commit()
    clean(); yield TestClient(app); clean()

def test_approval_edit_and_tasks(client):
    from backend.app import approvals
    a = approvals.request("owner_message", "offer_doc", 1, "Send letter", "original")
    assert client.put(f"/api/approvals/{a['id']}/draft", json={"draft_text": "edited text"}).json()["draft_text"] == "edited text" and client.put(f"/api/approvals/{a['id']}/draft", json={"draft_text": " "}).status_code == 422
    client.post(f"/api/approvals/{a['id']}/decide", json={"approve": False}); assert client.put(f"/api/approvals/{a['id']}/draft", json={"draft_text": "late"}).status_code == 409
    t = client.post("/api/tasks", json={"title": "Lodge pack", "assignee": "assistant", "due_on": str(date.today() - timedelta(days=1))}).json(); assert t["overdue"] is True and client.post("/api/tasks", json={"title": ""}).status_code == 422
    assert [x["id"] for x in client.get("/api/tasks", params={"assignee": "assistant"}).json()] == [t["id"]] and client.put(f"/api/tasks/{t['id']}", json={"status": "done"}).json()["done_at"]
    assert client.get("/api/tasks").json() == [] and client.put(f"/api/tasks/{t['id']}", json={"status": "weird"}).status_code == 422

def test_next_best_action_needs_your_probabilities_and_minutes(client):
    with conn() as c: c.execute("INSERT INTO analytics.rh_screen (parcel_id, address, suburb, zone, beds_base, beds_tier, beds_source, profit_before_rent_annual, inputs_hash) VALUES (999999990,'1 Test St','Testville','Residential - Mixed Housing Urban Zone',20,'DOCUMENTED','listing bedrooms',500000,'x')"); c.commit()
    q = client.get("/api/nba").json(); row = next(x for x in q["queue"] if x["parcel_id"] == 999999990)
    assert row["next_action"] == "approve_outreach" and row["expected_profit"] is None and q["ranked_by"] == "profit only" and any("stage probabilities" in n for n in q["needs"]) and all(x["beds_tier"] != "ESTIMATED" for x in q["queue"])
    assert client.put("/api/nba/probabilities/owner_agrees", json={"p": 1.5}).status_code == 422 and client.put("/api/nba/probabilities/nope", json={"p": .5}).status_code == 422
    for s, p in (("owner_agrees", .5), ("plans_received", .5), ("engineers_ok", .8), ("consent_ok", .5), ("certification_ok", .5)): client.put(f"/api/nba/probabilities/{s}", json={"p": p})
    client.post("/api/metrics/minutes", json={"step": "owner_contact", "minutes": 30, "role": "owner"})
    row = next(x for x in client.get("/api/nba").json()["queue"] if x["parcel_id"] == 999999990)
    assert row["stage_probability"] == pytest.approx(.5 * .5 * .8 * .5 * .5) and row["expected_profit"] == pytest.approx(500000 * .05) and row["minutes_estimate"] == 30 and row["expected_profit_per_human_minute"] == pytest.approx(25000 / 30)

def test_dashboard_matches_the_logs(client):
    client.post("/api/metrics/minutes", json={"parcel_id": P, "step": "plan_review", "minutes": 20, "role": "assistant"}); client.post("/api/metrics/minutes", json={"parcel_id": P, "step": "pack_review", "minutes": 40, "role": "owner"})
    assert client.post("/api/metrics/minutes", json={"step": "other", "minutes": 5, "role": "wizard"}).status_code == 422
    client.post(f"/api/property/{P}"); today = date.today()
    client.put(f"/api/property/{P}/milestones/lodged", json={"actual_on": str(today - timedelta(days=30))}); client.put(f"/api/property/{P}/milestones/consent_granted", json={"actual_on": str(today - timedelta(days=10))})
    d = client.get("/api/dashboard").json(); roles = {r["role"]: r["minutes"] for r in d["human_minutes_by_role"]}
    assert roles["assistant"] == 20 and roles["owner"] >= 40 and d["human_minutes_total"] == sum(roles.values()) and d["cycle_time_per_stage"]["lodged_to_consent_granted"] == {"n": 1, "avg_days": 20.0}
    assert d["slowest_step"] == "lodged_to_consent_granted" and d["pipeline"]["property_records"] >= 1 and d["pipeline"]["screened_candidates_by_tier"]
    w = client.post("/api/dashboard/weekly").json(); assert "dashboard" in w and "digest" in w and "nothing is emailed" in w["note"].lower()

def test_capture_portal_flag_permission_checks_retakes_and_retention(client):
    from backend.app import capture_portal as cp
    r = client.post("/api/capture-links", json={"parcel_id": P}); assert r.status_code == 409 and r.json()["detail"]["kind"] == "capture_link_issue"          # needs an approval record
    client.post(f"/api/approvals/{r.json()['detail']['approval_id']}/decide", json={"approve": True})
    off = client.post("/api/capture-links", json={"parcel_id": P}).json(); assert off["link"] is None                                                       # flag OFF: no working link
    from tests.conftest import RAW_TESTCLIENT
    from backend.app.main import app
    anon = RAW_TESTCLIENT(app); assert anon.get("/capture/abc").status_code == 404 and anon.get("/api/capture/abc").status_code == 404
    client.put("/api/flags/capture_portal_links", json={"enabled": True})
    r = client.post("/api/capture-links", json={"parcel_id": P}); client.post(f"/api/approvals/{r.json()['detail']['approval_id']}/decide", json={"approve": True}); lk = client.post("/api/capture-links", json={"parcel_id": P}).json()
    tok = lk["link"].rsplit("/", 1)[1]; assert anon.get("/capture/" + tok).status_code == 200 and "Permission first" in anon.get("/capture/" + tok).text and anon.get("/api/capture/wrong").status_code == 404
    with conn() as c: c.execute("INSERT INTO core.rh_property (parcel_id, created_by) VALUES (%s,'t') ON CONFLICT DO NOTHING", (P,)); c.commit()
    client.put(f"/api/property/{P}/facts", json={"field": "bedrooms_total", "value": 3, "source": "test", "confidence": "DOCUMENTED"})
    v = anon.get(f"/api/capture/{tok}").json(); assert not v["permission_recorded"] and any("permission" in m for m in v["check"]["missing"])
    assert anon.post(f"/api/capture/{tok}/details", json={"rooms": []}).status_code == 409 and anon.post(f"/api/capture/{tok}/upload", files={"file": ("a.png", png())}, data={"label": "x"}).status_code == 409
    assert anon.post(f"/api/capture/{tok}/permission", json={"by": "", "role": "owner"}).status_code == 422
    v = anon.post(f"/api/capture/{tok}/permission", json={"by": "A Owner", "role": "owner"}).json(); assert v["permission_recorded"] and "Capture guide" in v["guide"]
    assert anon.post(f"/api/capture/{tok}/details", json={"rooms": [{"type": "bedroom", "label": "Bed 1"}], "door_width_min_m": 9, "exits_count": 2}).status_code == 422
    v = anon.post(f"/api/capture/{tok}/details", json={"rooms": [{"type": "bedroom", "label": "Bed 1"}, {"type": "kitchen", "label": "Kitchen"}]}).json()
    miss = " | ".join(v["check"]["missing"]); assert "bedrooms: 1 listed, 3 expected from the Property Record" in miss and "door width" in miss and "exits" in miss and "photos: a clear photo of Bed 1" in miss
    v = anon.post(f"/api/capture/{tok}/upload", files={"file": ("d.png", png("dark"))}, data={"label": "Bed 1"}).json(); assert any("retake Bed 1" in m and "too dark" in m for m in v["check"]["missing"])
    v = anon.post(f"/api/capture/{tok}/upload", files={"file": ("f.png", png("flat"))}, data={"label": "Kitchen"}).json(); assert any("retake Kitchen" in m and "blurry" in m for m in v["check"]["missing"])
    assert anon.post(f"/api/capture/{tok}/upload", files={"file": ("n.pdf", b"%PDF-1.4 x")}, data={"label": "x", "kind": "photo"}).status_code in (415, 422)
    assert anon.post(f"/api/capture/{tok}/submit").json()["submitted"] is False
    anon.post(f"/api/capture/{tok}/details", json={"rooms": [{"type": "bedroom", "label": f"Bed {i}"} for i in (1, 2, 3)], "door_width_min_m": 0.82, "exits_count": 2})
    for lab in ("Bed 1", "Bed 2", "Bed 3"): anon.post(f"/api/capture/{tok}/upload", files={"file": ("s.png", png("sharp"))}, data={"label": lab})
    done = anon.post(f"/api/capture/{tok}/submit").json(); assert done["submitted"] is True and client.get("/api/capture-links").json()[0]["notification"].startswith("complete")
    rem = client.post(f"/api/capture-links/{client.get('/api/capture-links').json()[0]['id']}/reminder").json(); assert rem["kind"] == "owner_message" and "no rush" in rem["draft_text"] and "stop" in rem["draft_text"]
    with conn() as c: c.execute("UPDATE core.user_capture_link SET retention_until = current_date - 1"); c.commit()
    pg = client.post("/api/capture-links/purge").json(); assert pg["links_purged"] >= 1 and pg["files_deleted"] >= 3 and anon.get(f"/api/capture/{tok}").status_code == 404

def test_engineer_workflow_queue_escalation_scorecard(client):
    from backend.app import reviews
    with conn() as c:
        c.execute("INSERT INTO core.rh_property (parcel_id, created_by) VALUES (%s,'t') ON CONFLICT DO NOTHING", (P,))
        pack = c.execute("INSERT INTO core.rh_pack (parcel_id, version, checklist_version, inputs) VALUES (%s,1,'t','{\"site\":{\"address\":\"x\",\"suburb\":\"y\"},\"option\":{},\"facts\":{},\"fields\":{},\"compliance\":[]}'::jsonb) RETURNING id", (P,)).fetchone()["id"]; c.commit()
    assert client.post("/api/engineers", json={"name": "", "discipline": "fire"}).status_code == 422 and client.post("/api/engineers", json={"name": "X", "discipline": "wizard"}).status_code == 422
    fe = client.post("/api/engineers", json={"name": "Fiona Fire", "company": "FireCo", "discipline": "fire", "fee_per_review": 600, "target_turnaround_days": 5, "review_window": "Tuesdays"}).json()
    se = client.post("/api/engineers", json={"name": "Sam Struct", "discipline": "structural", "target_turnaround_days": 3}).json()
    k1 = reviews.create(pack, "fire", None, None)["id"]; k2 = reviews.create(pack, "structural", None, None)["id"]
    assert client.post("/api/engineers/assign", json={"package_ids": [k1], "engineer_id": se["id"]}).status_code == 409                    # wrong discipline
    q = client.post("/api/engineers/assign", json={"package_ids": [k1], "engineer_id": fe["id"]}).json(); assert q[0]["fee"] == 600 and q[0]["days_to_due"] == 5
    client.post("/api/engineers/assign", json={"package_ids": [k2], "engineer_id": se["id"]}); qq = client.get("/api/engineers/queue").json(); assert [x["id"] for x in qq] == [k2, k1]          # soonest due first
    with conn() as c: c.execute("UPDATE core.rh_review_package SET due_on = current_date - 2 WHERE id=%s", (k2,)); c.commit()
    assert client.get("/api/engineers/queue").json()[0]["overdue"] is True and client.post("/api/engineers/escalate").json()["escalated"] == [k2] and client.post("/api/engineers/escalate").json()["escalated"] == []
    assert "escalated" in [e["kind"] for e in reviews.view(k2)["events"]]
    reviews._event(k1, "comment", "Fiona", "exit width?"); reviews.mark_returned(k1)
    sc = {x["engineer"]: x for x in client.get("/api/engineers/scorecard").json()}; assert sc["Fiona Fire"]["returned"] == 1 and sc["Fiona Fire"]["issues_raised"] == 1 and sc["Fiona Fire"]["target_days"] == 5 and sc["Fiona Fire"]["on_time_rate"] == 1.0 and sc["Sam Struct"]["returned"] == 0
    t = client.post("/api/comment-templates", json={"title": "Exit widths", "body": "Please confirm clear exit widths.", "discipline": "fire"}).json(); assert client.get("/api/comment-templates", params={"discipline": "structural"}).json() == [] and len(client.get("/api/comment-templates", params={"discipline": "fire"}).json()) == 1
    from backend.app import engineers
    assert "Playbook" in engineers.playbook_delta_text(pack) or "No archetype" in engineers.playbook_delta_text(pack)

def test_capacity_planner_binding_constraint_and_cash_curve(client):
    from backend.app import capacity
    homes = [{"parcel_id": i, "address": f"h{i}", "beds": 16, "tier": "ESTIMATED", "retrofit": 160000} for i in range(1, 7)]
    big = {"engineer_reviews_per_week": 100, "lodgement_admin_hours_per_week": 1000, "lodgement_hours_per_pack": 1, "builder_starts_per_month": 100, "auditor_audits_per_month": 100, "manager_hires_per_month": 100, "care_staff_hires_per_month": 100, "cash_limit_dollars": 5_000_000}
    assert capacity.plan(homes, {}, FULL)["status"] == "needs_input" and capacity.plan(homes, big, {**FULL, "stabilised_occupancy": None})["status"] == "needs_input"
    free = capacity.plan(homes, big, FULL); assert free["binding_constraint"] is None and free["opened_within_horizon"] == 6 and len({h["works_start_week"] for h in free["schedule"]}) == 1
    slow = capacity.plan(homes, {**big, "builder_starts_per_month": 1}, FULL); starts = sorted(h["works_start_week"] for h in slow["schedule"])
    assert slow["binding_constraint"]["key"] == "builder_starts_per_month" and all(b - a in (4, 5) for a, b in zip(starts, starts[1:])) and slow["binding_constraint"]["blocked_home_weeks"] > 0
    poor = capacity.plan(homes, {**big, "cash_limit_dollars": 200_000}, FULL); assert poor["binding_constraint"]["key"] == "cash" and poor["opened_within_horizon"] < 6
    assert poor["cash_curve_by_4_weeks"][0] == 200_000 - 160_000 - 20_000 or poor["cash_curve_by_4_weeks"][0] <= 200_000
    blank = capacity.plan(homes, {"cash_limit_dollars": 5_000_000}, FULL); assert len(blank["not_modelled"]) == 6 and blank["binding_constraint"] is None and "staffing, cash and certification" in blank["note"]
    r = capacity.plan(homes, big, FULL, opening_target="2027-06-01"); assert all(t["note"] == "set lead time" for t in r["readiness"][0]["tracks"])
    api = client.post("/api/capacity", json={"homes": homes, "capacities": {**big, "builder_starts_per_month": 1}, "overrides": FULL}).json(); assert api["binding_constraint"]["key"] == "builder_starts_per_month"
