"""Feature flags (all off, gated routes answer 403) and the validation gate settings."""
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
from tests.conftest import RAW_TESTCLIENT

ROOT = Path(__file__).resolve().parent.parent
GATED = ["/api/outreach/leads", "/api/crm/contacts", "/api/call-sheets", "/api/routes/plan", "/api/leads/export", "/api/field/capture", "/field", "/api/offer-letters/new"]

def app():
    from backend.app.main import app as a; return a

def test_flags_file_is_all_false_and_only_literal_true_turns_one_on():
    cfg = yaml.safe_load((ROOT / "config" / "feature_flags.yaml").read_text())
    assert cfg == {"outreach_enabled": False, "field_capture_enabled": False, "offer_letters_enabled": False}

def test_gated_routes_are_403_while_off_and_login_still_comes_first():
    c = TestClient(app()); anon = RAW_TESTCLIENT(app())
    for p in GATED:
        assert c.get(p).status_code == 403, p
        assert c.post(p, json={}).status_code == 403, p
        assert anon.get(p, follow_redirects=False).status_code in (401, 303), p            # not logged in: the login wall answers first
    assert "outreach_enabled" in c.get("/api/leads/export").json()["detail"]
    assert c.get("/api/health").status_code == 200

def test_flag_on_lets_the_request_through_to_the_router(monkeypatch):
    from backend.app import flags
    monkeypatch.setattr(flags, "gated_flags", lambda: {"outreach_enabled": True, "field_capture_enabled": False, "offer_letters_enabled": False})
    c = TestClient(app()); assert c.get("/api/crm/contacts").status_code == 404 and c.get("/api/field/capture").status_code == 403       # no such route is built yet: 404, not 403

def test_the_app_has_no_switch_for_the_gated_flags():
    c = TestClient(app()); fl = {f["key"]: f for f in c.get("/api/flags").json()}
    assert all(fl[k]["enabled"] is False and fl[k]["changeable_in_app"] is False for k in ("outreach_enabled", "field_capture_enabled", "offer_letters_enabled"))
    for k in ("outreach_enabled", "field_capture_enabled", "offer_letters_enabled"): assert c.put(f"/api/flags/{k}", json={"enabled": True}).status_code == 404

def test_validation_config_blank_then_set():
    from backend.app.db import conn
    with conn() as cn: cn.execute("DELETE FROM core.user_setting WHERE key LIKE 'validation:%'"); cn.commit()
    c = TestClient(app()); assert c.get("/api/validation/config").json() == {"tolerance_pct": None, "properties": []}
    assert c.put("/api/validation/config", json={"tolerance_pct": -1}).status_code == 422 and c.put("/api/validation/config", json={"properties": [1, 2, 3, 4, 5, 6]}).status_code == 422
    r = c.put("/api/validation/config", json={"tolerance_pct": 15, "properties": [4899224]}).json(); assert r == {"tolerance_pct": 15, "properties": [4899224]}
    with conn() as cn: cn.execute("DELETE FROM core.user_setting WHERE key LIKE 'validation:%'"); cn.commit()
