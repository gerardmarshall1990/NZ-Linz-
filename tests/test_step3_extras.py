"""Deal sheet, ranking and what-if sliders, retrofit calibration loop, plan request pack (Part 7 step 3 leftovers)."""
import os
from datetime import date, timedelta
import pymupdf, pytest
from fastapi.testclient import TestClient
from tests.test_step2 import PARCEL, plan_dxf
from tests.test_scenarios_api import FULL

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads_s3x"))
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            for t in ("rh_plan_request", "rh_scenario", "rh_brief", "rh_check_run", "rh_layout_option", "rh_evidence_gap_status"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.rh_approval"); c.execute("DELETE FROM core.rh_quote"); c.execute("DELETE FROM core.rh_rate_calibration")
            c.execute("DELETE FROM core.rh_plan_edit WHERE extraction_id IN (SELECT x.id FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_extraction WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_calibration WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            for t in ("rh_upload", "rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history")      # session fixture puts the owner's back
            c.commit()
    clean(); cl = TestClient(app)
    assert cl.post(f"/api/property/{PARCEL}").status_code == 200
    u = cl.post(f"/api/property/{PARCEL}/uploads", files={"file": ("plan.dxf", plan_dxf())}).json()
    e = cl.post(f"/api/uploads/{u['id']}/extract", json={"mode": "auto"}).json()
    assert cl.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE"}).status_code == 200
    cl.opts = {o["scenario"]: o for o in cl.post(f"/api/property/{PARCEL}/layouts").json()}; cl.oid = cl.opts["base"]["id"]
    yield cl; clean()

def pdf_text(b): return " ".join(p.get_text() for p in pymupdf.open(stream=b, filetype="pdf")).replace("\n", " ").replace("\ufb01", "fi")
def quote(client, qty=10, amt=5000, src="Supplier A", **kw): return client.post("/api/retrofit/quotes", json={"line": "nurse_call", "source": src, "quote_date": str(date.today()), "quantity": qty, "amount_ex_gst": amt, **kw})

# ---------------------------------------------------------------- calibration loop
def test_calibration_loop(client):
    assert quote(client, src="").status_code == 422 and quote(client, qty=0).status_code == 422
    assert client.post("/api/retrofit/quotes", json={"line": "nope", "source": "x", "quote_date": str(date.today()), "quantity": 1, "amount_ex_gst": 1}).status_code == 422
    assert client.post("/api/retrofit/quotes", json={"line": "nurse_call", "source": "x", "quote_date": str(date.today() + timedelta(days=3)), "quantity": 1, "amount_ex_gst": 1}).status_code == 422
    client.put("/api/settings/rates", json={"lines": {"nurse_call": {"low": 400, "base": 500, "high": 650, "source": "my guess"}}})
    s = quote(client, 10, 6000).json()                                                  # 600 per point vs model 500
    assert s["quotes"][0]["unit_rate"] == 600 and s["quotes"][0]["variance_vs_model_pct"] == 20.0 and s["n_quotes"] == 1
    assert client.post("/api/retrofit/calibration/nurse_call/apply", json={}).status_code == 409        # one quote: no range, needs an explicit accept
    quote(client, 10, 5000, src="Supplier B"); q3 = quote(client, 10, 7000, src="Supplier C").json()
    assert q3["proposed"] == {"low": 500.0, "base": 600.0, "high": 700.0, "n_quotes": 3, "single_quote": False}
    assert client.get("/api/retrofit/calibration").json()["lines"]["nurse_call"]["n_quotes"] == 3
    assert client.get("/api/retrofit/calibration").json()["lines"]["door_widening"]["n_quotes"] == 0
    a = client.post("/api/retrofit/calibration/nurse_call/apply", json={"note": "first round"}).json()
    assert a["applied"]["base"] == 600.0 and "calibrated from 3 quote(s)" in a["applied"]["source"]
    assert client.get("/api/settings").json()["rates"]["lines"]["nurse_call"]["base"] == 600.0         # the model now uses it
    h = client.get("/api/retrofit/calibration/history").json(); assert h[0]["old_rate"]["base"] == 500 and h[0]["new_rate"]["base"] == 600 and h[0]["n_quotes"] == 3
    qid = q3["quotes"][-1]["id"]; assert client.delete(f"/api/retrofit/quotes/{qid}").json()["n_quotes"] == 2        # a voided quote stops counting

# ---------------------------------------------------------------- what-if
def test_whatif_sliders(client):
    client.put("/api/settings/assumptions", json={"values": {k: v for k, v in FULL.items() if k != "fill_ramp_by_month"}})
    z = client.post(f"/api/property/{PARCEL}/whatif", json={"option_id": client.oid}).json()
    assert z["change"]["annual_profit_before_rent"] == 0 and z["base"]["annual_profit_before_rent"] is not None
    up = client.post(f"/api/property/{PARCEL}/whatif", json={"option_id": client.oid, "occupancy_pts": 10}).json()
    assert up["change"]["annual_profit_before_rent"] > 0
    fee = client.post(f"/api/property/{PARCEL}/whatif", json={"option_id": client.oid, "fee_pct": -10}).json(); wg = client.post(f"/api/property/{PARCEL}/whatif", json={"option_id": client.oid, "wage_pct": 10}).json()
    assert fee["change"]["annual_profit_before_rent"] < 0 and wg["change"]["annual_profit_before_rent"] < 0
    assert client.post(f"/api/property/{PARCEL}/whatif", json={"option_id": client.oid, "occupancy_pts": 99}).status_code == 422
    with __import__("backend.app.db", fromlist=["conn"]).conn() as c: assert c.execute("SELECT count(*) AS n FROM core.rh_scenario WHERE parcel_id=%s", (PARCEL,)).fetchone()["n"] == 0      # sliders save nothing

# ---------------------------------------------------------------- ranking
def test_ranking_tiers_weights_and_unranked(client):
    r = client.get("/api/ranking").json(); mine = [x for t in r["tiers"].values() for x in t["by_profit_per_effort_point"] if x["parcel_id"] == PARCEL]
    assert len(mine) == 1; row = mine[0]
    assert row["profit_per_effort_point"] == round(row["annual_profit_before_rent"] / row["effort_points"]) and row["effort_points"] > 1
    assert row in r["tiers"][row["tier"]]["by_profit_per_effort_point"] and all(row not in r["tiers"][t]["by_profit_per_effort_point"] for t in r["tiers"] if t != row["tier"])
    assert row["retrofit_needs_rate"] is True and row["profit_per_cash"] is None            # retrofit rates incomplete: cash at risk is not guessed
    w = client.put("/api/ranking/weights", json={"weights": {"beds_to_fill": 5.0}}).json(); assert w["weights"]["beds_to_fill"] == 5.0
    r2 = client.get("/api/ranking").json(); row2 = [x for x in r2["tiers"][row["tier"]]["by_profit_per_effort_point"] if x["parcel_id"] == PARCEL][0]
    assert row2["effort_points"] > row["effort_points"]
    assert client.put("/api/ranking/weights", json={"weights": {"nonsense": 1}}).status_code == 422 and client.put("/api/ranking/weights", json={"weights": {"parties": -1}}).status_code == 422
    client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": None}})        # inputs missing: listed, not scored
    r3 = client.get("/api/ranking").json(); un = [x for x in r3["tiers"][row["tier"]]["not_ranked"] if x["parcel_id"] == PARCEL]
    assert un and "utilities_per_week" in un[0]["missing"] and "profit_per_effort_point" not in un[0]
    client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": 500}})

# ---------------------------------------------------------------- deal sheet
def test_deal_sheet(client):
    assert client.get("/api/property/1/dealsheet.pdf").status_code == 404            # no Property Record
    txt = pdf_text(client.get(f"/api/property/{PARCEL}/dealsheet.pdf?option_id={client.oid}").content)
    assert "Rest Home Deal Sheet" in txt and "Bed scenarios" in txt and "Compliance (screening)" in txt
    tier = client.get(f"/api/property/{PARCEL}").json()["lowest_confidence"]
    assert ("Screening only: bedrooms/plans not confirmed" in txt) == (tier in (None, "ESTIMATED"))
    assert "Total withheld" in txt or "Base $" in txt
    assert "Walk-away rent per week" in txt and "Not advice" in txt
    client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": None}})
    assert "Needs input: utilities_per_week" in pdf_text(client.get(f"/api/property/{PARCEL}/dealsheet.pdf").content)          # a missing input is shown as missing, not filled
    client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": 500}})
    md = client.get(f"/api/property/{PARCEL}/dealsheet").text
    for w in ("guarantee", "approved"): assert w not in md.lower()

# ---------------------------------------------------------------- plan request pack
def test_plan_request_pack(client):
    e = client.get(f"/api/property/{PARCEL}/plan-request/email", params={"sender": "Me"}).json()
    assert "Information request" in e["text"] and "Floor plans of all levels" in e["text"] and "nothing is sent" in e["label"].lower() and e["text"].rstrip().endswith("Me")
    c = client.get(f"/api/property/{PARCEL}/plan-request/council").json()
    assert c["council"]["last_verified"] == "2026-10-18" and c["council"]["property_file"]["fee_nzd"] is None and "NOT found" in c["council"]["property_file"]["note"] and c["prefill"]["address"]
    f = client.get(f"/api/property/{PARCEL}/site-visit").json(); assert any(x["field"] == "corridor_width_min_m" for x in f["fields"])
    assert client.post(f"/api/property/{PARCEL}/site-visit", json={"values": {"gfa_m2": 5}}).status_code == 422
    r = client.post(f"/api/property/{PARCEL}/site-visit", json={"values": {"corridor_width_min_m": 1.2, "kitchens": "", "bedrooms_total": 8}, "visitor": "me"}).json()
    assert sorted(r["written"]) == ["bedrooms_total", "corridor_width_min_m"]
    facts = client.get(f"/api/property/{PARCEL}").json()["facts"]
    assert facts["corridor_width_min_m"]["confidence"] == "CONFIRMED" and facts["corridor_width_min_m"]["value"] == 1.2 and "site visit" not in facts["kitchens"]["source"]
    body = {"kind": "owner_agent", "recipient": "agent", "sent_on": str(date.today() - timedelta(days=9)), "follow_up_on": str(date.today() - timedelta(days=2))}
    r0 = client.post(f"/api/property/{PARCEL}/plan-requests", json=body); assert r0.status_code == 409 and r0.json()["detail"]["approval_required"]          # recording it as sent needs an approval record
    client.post(f"/api/approvals/{r0.json()['detail']['approval_id']}/decide", json={"approve": True})
    log = client.post(f"/api/property/{PARCEL}/plan-requests", json=body).json()
    assert log[0]["status"] == "sent" and log[0]["follow_up_due"] is True
    assert client.put(f"/api/plan-requests/{log[0]['id']}", json={"status": "received"}).json()[0]["follow_up_due"] is False
    assert client.post(f"/api/property/{PARCEL}/plan-requests", json={"kind": "bad"}).status_code == 422
