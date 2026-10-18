"""Map layers, Māori land module, Best Use tab, archetype playbooks."""
import os
import pytest
from fastapi.testclient import TestClient
from tests.test_step2 import PARCEL as CONV, plan_dxf
from tests.test_scenarios_api import FULL
from tests.test_dev_flow import INP
DEV = 4756180; MAORI = 6706176

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads_more"))
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            c.execute("DELETE FROM core.user_dev_run WHERE parcel_id IN (%s,%s)", (DEV, MAORI)); c.execute("DELETE FROM core.user_maori_note"); c.execute("DELETE FROM core.user_setting WHERE key LIKE 'hazard_reviewed:%'")
            for t in ("rh_scenario", "rh_brief", "rh_check_run", "rh_layout_option", "rh_evidence_gap_status"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (CONV,))
            c.execute("DELETE FROM core.rh_plan_edit WHERE extraction_id IN (SELECT x.id FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id=%s)", (CONV,))
            c.execute("DELETE FROM core.rh_plan_extraction WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (CONV,)); c.execute("DELETE FROM core.rh_plan_calibration WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (CONV,))
            for t in ("rh_upload", "rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (CONV,))
            c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history"); c.commit()
    clean(); yield TestClient(app); clean()

def test_layers_bbox_required_capped_and_hazard_labelled(client):
    k = client.get("/api/layers").json(); assert "zones" in k and "flood_plains" in k["hazards"] and "information only" in k["note"]
    assert client.get("/api/layers/zones", params={"bbox": "bad"}).status_code == 422 and client.get("/api/layers/zones", params={"bbox": "100,0,101,1"}).status_code == 422
    assert client.get("/api/layers/zones", params={"bbox": "174,-37,175,-36"}).status_code == 422          # too wide
    z = client.get("/api/layers/zones", params={"bbox": "174.62,-36.91,174.66,-36.88"}).json(); assert z["type"] == "FeatureCollection" and z["features"] and "zone" in z["features"][0]["properties"]
    assert client.get("/api/layers/hazard", params={"bbox": "174.62,-36.91,174.66,-36.88", "name": "nope"}).status_code == 422
    h = client.get("/api/layers/hazard", params={"bbox": "174.62,-36.91,174.66,-36.88", "name": "flood_plains"}).json(); assert "information only" in h["note"]
    m = client.get("/api/layers/maori_land", params={"bbox": "174.62,-36.91,174.66,-36.88"}).json(); assert m["features"] and all("ori" in (f["properties"]["zone"] or "") or f["properties"]["maori_land_linz"] for f in m["features"])

def test_maori_module_partnership_first_no_for_sale(client):
    d = client.post(f"/api/maori/{MAORI}", json={}).json()
    assert d["is_relevant"] and d["route"] == "lease or joint venture" and d["entity_to_approach"]["status"] == "unknown" and d["tpk_gap"]["linz_flagged_parcels"] > 0 and "No Te Puni" in d["tpk_gap"]["note"]
    assert len(d["approval_pathway"]) == 5 and "lawyer" in " ".join(d["approval_pathway"]) and d["transportable_homes"]["relocation_rules"].startswith("UNKNOWN")
    assert client.put(f"/api/maori/{MAORI}/entity", json={"name": "X Trust", "source": ""}).status_code == 422
    e = client.put(f"/api/maori/{MAORI}/entity", json={"name": "X Trust", "role": "trustees", "source": "Māori Land Court public record"}).json(); assert e["entity_to_approach"]["name"] == "X Trust"
    s = client.post(f"/api/maori/{MAORI}", json={"unit": {"width_m": 7, "depth_m": 10, "height_m": 5, "gfa_m2": 60, "bedrooms": 2}}).json(); assert s["indicative_scheme"]["status"] in ("ok", "needs_input")
    md = client.get(f"/api/maori/{MAORI}/outline").text
    assert "[TO COMPLETE" in md and "X Trust" in md and "DRAFT: NOT FOR CONSENT" in md
    assert "for sale" not in md.replace(d["never_for_sale"], "").lower() and "for sale" not in str({k: v for k, v in d.items() if k != "never_for_sale"}).lower()

def test_best_use_honesty_and_hazard_rule(client, monkeypatch):
    from backend.app import bestuse
    b = client.post(f"/api/bestuse/{DEV}", json={}).json(); assert b["best"] is None and all(c["status"] == "needs_input" for c in b["columns"]) and [c["option"] for c in b["columns"]] == ["a_conversion", "b_development", "c_new_build_rest_home"]
    assert client.post("/api/bestuse/1", json={}).status_code == 404
    # development column with finance
    client.post(f"/api/dev/{DEV}/scenarios", json=INP)
    monkeypatch.setattr(bestuse, "_hazard", lambda p: {"flagged": False, "flags": []}); clean_b = bestuse.development(DEV)
    monkeypatch.setattr(bestuse, "_hazard", lambda p: {"flagged": True, "flags": ["Floodplain"]}); flag_b = bestuse.development(DEV)
    assert clean_b["status"] == flag_b["status"] == "ok" and clean_b["eligible_for_best"] is True and flag_b["eligible_for_best"] is False and any("hazard" in r for r in flag_b["risks"]) and not any("hazard" in r for r in clean_b["risks"])
    assert client.put(f"/api/bestuse/{DEV}/hazard-reviewed", json={"reviewed": True}).json()["hazard_reviewed"] is True and bestuse.development(DEV)["eligible_for_best"] is True
    # option (a) is unaffected by hazard flags (information only)
    assert client.post(f"/api/property/{CONV}").status_code == 200
    u = client.post(f"/api/property/{CONV}/uploads", files={"file": ("plan.dxf", plan_dxf())}).json(); e = client.post(f"/api/uploads/{u['id']}/extract", json={"mode": "auto"}).json()
    assert client.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE"}).status_code == 200; client.post(f"/api/property/{CONV}/layouts")
    client.put("/api/settings/assumptions", json={"values": FULL})
    from backend.app import retrofit
    lines = {k: ({"low": 45000, "base": 50000, "high": 65000, "source": "test"} if v["basis"] == "allowance" else {"low": 90, "base": 100, "high": 130, "source": "test"}) for k, v in retrofit.rates()["lines"].items()}
    client.put("/api/settings/rates", json={"lines": lines, "pct": {"preliminaries_and_margins": {"low": 10, "base": 10, "high": 10}, "professional_fees": {"low": 8, "base": 8, "high": 8}, "contingency": {"low": 15, "base": 15, "high": 15}}})
    monkeypatch.setattr(bestuse, "_hazard", lambda p: {"flagged": False, "flags": []}); a1 = bestuse.conversion(CONV)
    monkeypatch.setattr(bestuse, "_hazard", lambda p: {"flagged": True, "flags": ["Floodplain"]}); a2 = bestuse.conversion(CONV)
    assert a1["status"] == "ok" and a1 == a2 and "information only" in a1["hazard_effect"]
    # best only when all three compare and a horizon is given
    nb = {"gfa_per_bed_m2": 45, "storey_height_m": 3, "build_cost_per_m2": 3000}
    full = client.post(f"/api/bestuse/{CONV}", json={"newbuild": nb}).json(); assert full["best"] is None and any("horizon" in r for r in full["best_blocked_because"]) and full["lowest_confidence"] == "ESTIMATED"

def test_apartment_playbook_checks_and_bed_recount(client):
    a = client.post(f"/api/property/{CONV}/playbooks/apartment", json={}).json(); by = {c["id"]: c for c in a["checks"]}
    assert by["beds_after_communal"]["status"] == "UNKNOWN" and by["corridor_width"]["status"] == "UNKNOWN" and "ALLOWANCE" in by["building_wide_allowances"]["detail"] and a["reviewed_by_engineer"] is None
    roles = {"lounge": 2, "dining": 1, "kitchen": 1, "nurse_station": 1, "office": 1, "laundry": 1, "storage": 1}
    a = client.post(f"/api/property/{CONV}/playbooks/apartment", json={"units_total": 60, "units_per_role": roles}).json(); assert {c["id"]: c for c in a["checks"]}["beds_after_communal"]["beds"] == 60 - 8
    client.put(f"/api/property/{CONV}/facts", json={"field": "title_type", "value": "unit title", "source": "test", "confidence": "CONFIRMED"})
    a = client.post(f"/api/property/{CONV}/playbooks/apartment", json={"owners": 12, "single_party_controls": False}).json(); assert a["deal_breakers"] == ["title_owners"]
    a = client.post(f"/api/property/{CONV}/playbooks/apartment", json={"owners": 1}).json(); assert a["deal_breakers"] == [] and {c["id"]: c for c in a["checks"]}["title_owners"]["status"] == "NEEDS_PROFESSIONAL"

def test_playbooks_are_skeletons_and_delta_is_honest(client):
    pbs = {p["name"]: p for p in client.get("/api/playbooks").json()}
    assert {"apartment_building", "single_level_house", "two_storey_house", "motel_single_level", "motel_two_storey", "lodge_guesthouse", "home_and_income"} <= set(pbs) and all(p["reviewed_by_engineer"] is None and p["complete"] is False for p in pbs.values() if p["name"] != "apartment_building")
    d = client.get(f"/api/property/{CONV}/playbooks/single_level_house/delta").json(); assert d["delta_available"] is False and "not been written and reviewed" in d["reason"] and d["items"]
    assert "apartment_building" in client.get(f"/api/property/{CONV}/playbooks/match").json()
    assert client.get(f"/api/property/{CONV}/playbooks/nope/delta").status_code == 404
