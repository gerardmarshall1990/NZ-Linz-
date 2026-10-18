"""Digest and saved searches, CRM guardrails (behind the outreach flag), Trade Me connector (off until terms are read and keys are set)."""
import json
from datetime import date
import psycopg, pytest
from fastapi.testclient import TestClient
from backend.app.db import conn
from tests.test_listings import addrs, CSV_HEAD  # noqa: F401

@pytest.fixture(scope="module")
def client():
    from backend.app.main import app
    def clean():
        with conn() as c:
            c.execute("DELETE FROM core.user_crm_activity"); c.execute("DELETE FROM core.user_crm_lead"); c.execute("DELETE FROM core.user_crm_do_not_contact")
            c.execute("DELETE FROM core.user_saved_search"); c.execute("DELETE FROM core.user_digest")
            c.execute("DELETE FROM core.user_listing_history WHERE listing_id IN (SELECT id FROM core.user_listing WHERE source_id LIKE 'TDC-%')"); c.execute("DELETE FROM core.user_listing WHERE source_id LIKE 'TDC-%' OR source = 'trademe'"); c.commit()
    clean(); yield TestClient(app); clean()

def imp(client, num, road, sub, rent, beds, sid="TDC-1"):
    return client.post("/api/listings/import", files={"file": ("l.csv", (CSV_HEAD + f"{sid},{num} {road},{sub},{rent},{beds},3,rent,\n").encode())}, data={"source": "csv_manual", "dry_run": "false"}).json()

def test_digest_new_changed_and_saved_search(client, addrs):
    num, road, sub = addrs["single"][1], addrs["single"][2], addrs["single"][3]
    assert client.post("/api/saved-searches", json={"name": "bad", "filters": {"colour": "red"}}).status_code == 422
    ss = client.post("/api/saved-searches", json={"name": "5+ beds", "filters": {"min_beds": 5}}).json()
    assert imp(client, num, road, sub, 900, 6)["new"] == 1
    d = client.get("/api/digest", params={"since": str(date.today())}).json()
    mine = [x for x in d["new_listings"] if x["address"].startswith(f"{num} {road}")]; assert mine and mine[0]["verdict"] in ("GREEN", "AMBER", "RED", "GREY") and mine[0]["demo"] is False
    assert any(m["search"] == "5+ beds" and mine[0]["listing_id"] in m["listing_ids"] for m in d["saved_search_matches"]) and "Nothing is emailed" in d["label"]
    assert set(d["due"]) == {"plan_request_follow_ups", "overdue_rfis", "approvals_waiting"} and d["source_coverage"]
    imp(client, num, road, sub, 950, 6)                                                  # a rent change
    d2 = client.get("/api/digest", params={"since": str(date.today())}).json()
    assert any(h["field"] == "rent_per_week" and float(h["new"]) == 950 for h in d2["price_changes"])
    run = client.post("/api/digest/run", params={"since": str(date.today())}).json(); assert run["id"] and client.get("/api/digest/history").json()[0]["id"] == run["id"]
    assert client.delete(f"/api/saved-searches/{ss['id']}").json()["ok"]

def test_crm_is_off_by_default_and_guardrails_hold_when_on(client, monkeypatch, addrs):
    assert client.post("/api/crm/leads", json={"parcel_id": 1}).status_code == 403
    from backend.app import flags
    monkeypatch.setattr(flags, "gated_flags", lambda: {"outreach_enabled": True, "field_capture_enabled": False, "offer_letters_enabled": False})
    num, road, sub = addrs["single"][1], addrs["single"][2], addrs["single"][3]; imp(client, num, road, sub, 900, 6, "TDC-2")
    with conn() as c: lid = c.execute("SELECT id, parcel_id FROM core.user_listing WHERE source_id='TDC-2'").fetchone()
    L = client.post("/api/crm/leads", json={"listing_id": lid["id"]}).json(); assert L["contactable"] is False and L["parcel_id"] == lid["parcel_id"] and L["stage"] == "new"
    assert client.put(f"/api/crm/leads/{L['id']}/contactable", json={"contactable": True}).status_code == 422          # no source or lawful basis
    assert client.put(f"/api/crm/leads/{L['id']}", json={"counterparty_type": "tenant"}).status_code == 422             # tenants are never approached
    assert client.post(f"/api/crm/leads/{L['id']}/activities", json={"kind": "call"}).status_code == 409                # not contactable
    assert client.post(f"/api/crm/leads/{L['id']}/activities", json={"kind": "note", "notes": "researching"}).status_code == 200
    client.put(f"/api/crm/leads/{L['id']}", json={"counterparty_type": "owner", "source": "public Companies Office register", "lawful_basis": "legitimate interest: business property approach", "contact_name": "A Owner"})
    assert client.put(f"/api/crm/leads/{L['id']}/contactable", json={"contactable": True}).json()["contactable"] is True
    assert client.post(f"/api/crm/leads/{L['id']}/activities", json={"kind": "call", "outcome": "no answer"}).status_code == 200
    assert client.put(f"/api/crm/leads/{L['id']}/stage", json={"stage": "lost"}).status_code == 422
    client.post("/api/crm/do-not-contact", json={"reason": "asked not to be contacted", "contact_name": "a owner"})        # case-insensitive match; also withdraws contactable
    now = client.get(f"/api/crm/leads/{L['id']}").json(); assert now["do_not_contact"] is True and now["contactable"] is False
    assert client.post(f"/api/crm/leads/{L['id']}/activities", json={"kind": "email"}).status_code == 409
    assert client.put(f"/api/crm/leads/{L['id']}/contactable", json={"contactable": True}).status_code == 409
    assert client.get("/api/crm/funnel").json()["new"] >= 1
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn() as c: c.execute("INSERT INTO core.user_crm_lead (contactable) VALUES (true)")           # the database refuses it too

def test_trademe_connector_is_off_until_terms_and_keys(client, monkeypatch):
    from backend.app import listings, trademe
    for k in trademe.KEYS: monkeypatch.delenv(k, raising=False)
    st = client.get("/api/trademe/status").json(); assert st["ready"] is False and st["source_status"] == "pending" and any("developer terms" in b for b in st["blockers"]) and "CSV" in st["fallback"]
    r = client.post("/api/trademe/sync", json={"params": {}}); assert r.status_code == 503 and "blockers" in r.json()["detail"]
    for k in trademe.KEYS: monkeypatch.setenv(k, "x-" + k[-3:])
    assert client.get("/api/trademe/status").json()["ready"] is False                               # keys alone are not enough: the owner must set the source live
    real = listings.sources
    monkeypatch.setattr(listings, "sources", lambda: {**real(), "sources": {**real()["sources"], "trademe": {**real()["sources"]["trademe"], "status": "live"}}})
    assert client.get("/api/trademe/status").json()["ready"] is True
    monkeypatch.setattr(trademe, "MIN_INTERVAL_S", 0)
    class R:
        status_code = 200
        def json(self): return {"List": [{"ListingId": 5551, "Address": "12 Test Road", "Suburb": "Epsom", "RentPerWeek": 1200, "Bedrooms": 5, "Bathrooms": 2, "Body": "SHOULD NOT BE STORED"}, {"ListingId": 5552, "Suburb": "No address"}]}
    seen = {}
    class H:
        def get(self, url, params=None, headers=None, timeout=None): seen.update(url=url, headers=headers); return R()
    out = trademe.sync({"bedrooms_min": 5}, http=H())
    assert out["new"] == 1 and seen["headers"]["User-Agent"].startswith("nz-rest-home") and 'oauth_signature_method="PLAINTEXT"' in seen["headers"]["Authorization"]
    with conn() as c:
        row = c.execute("SELECT * FROM core.user_listing WHERE source='trademe' AND source_id='5551'").fetchone()
        assert row and float(row["rent_per_week"]) == 1200 and row["bedrooms"] == 5 and "SHOULD NOT" not in json.dumps(row, default=str)
