"""Economics, retrofit and Offer Builder through the API, on a real property record with the layout engine. Needs `make app-db`."""
import os
import pytest
from fastapi.testclient import TestClient
from tests.test_step2 import PARCEL, plan_dxf  # same ground-truth plan

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads3"))
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            for t in ("rh_scenario", "rh_brief", "rh_check_run", "rh_layout_option", "rh_evidence_gap_status"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_edit WHERE extraction_id IN (SELECT x.id FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_extraction WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_calibration WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            for t in ("rh_upload", "rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.commit()
    clean(); cl = TestClient(app)
    assert cl.post(f"/api/property/{PARCEL}").status_code == 200
    u = cl.post(f"/api/property/{PARCEL}/uploads", files={"file": ("plan.dxf", plan_dxf())}).json()
    e = cl.post(f"/api/uploads/{u['id']}/extract", json={"mode": "auto"}).json()
    assert cl.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE"}).status_code == 200
    cl.opts = {o["scenario"]: o for o in cl.post(f"/api/property/{PARCEL}/layouts").json()}
    yield cl; clean()

FULL = {"clinical_lead_cost_per_week": 2000, "manager_cost_per_week": 2500, "cook_cleaner_laundry_per_week": 1500, "utilities_per_week": 500, "insurance_per_year": 26000,
        "supplies_per_occupied_bed_per_week": 40, "repairs_maintenance_per_year": 26000, "compliance_and_certification_per_year": 13000, "other_opex_per_week": 300, "roster_coverage_multiplier": 1.5,
        "stabilised_occupancy": 0.9, "fill_ramp_by_month": [0.3, 0.6, 0.8], "pre_opening_costs": 20000, "working_capital": 15000, "lease_term_years": 10, "cost_of_capital_pct": 8,
        "target_profit_per_year": 20000, "minimum_acceptable_profit_per_year": 10000}

def test_default_config_blocks_everything(client):
    oid = client.opts["base"]["id"]
    r = client.post(f"/api/property/{PARCEL}/economics", json={"option_id": oid}).json()
    assert r["walk_away_rent_per_week"] is None and "clinical_lead_cost_per_week" in r["needs_input"] or "stabilised_occupancy" in r["needs_input"]
    assert r["banner"] == "Screening only: bedrooms/plans not confirmed" or r["confidence"] == "CONFIRMED"
    off = client.post(f"/api/property/{PARCEL}/offers", json={"option_id": oid, "asking_rent": 1000, "terms": {"s": 0.5}}).json()
    assert off["modes"] == {} and off["needs_input"]                       # rates blank: needs input, never a made-up number

def test_retrofit_withheld_without_rates_and_computed_with_rates(client):
    oid = client.opts["base"]["id"]
    r = client.post(f"/api/property/{PARCEL}/retrofit", params={"option_id": oid}).json()
    assert r["total"] is None and r["needs_rate"] and "Total withheld" in r["note"]
    by = {l["line"]: l for l in r["lines"]}
    assert by["ensuite_build_or_upgrade"]["quantity"] == 2 and by["nurse_call"]["quantity"] == 4 + 4    # 4 resident rooms + 4 communal rooms (lounge, kitchen, office, laundry; stores are not communal)
    assert by["furniture_fitout_per_bed"]["quantity"] == 4
    from backend.app import scenarios
    cfg = {"lines": {k: ({**v, "low": 45000, "base": 50000, "high": 65000} if v["basis"] == "allowance" else {**v, "low": 90, "base": 100, "high": 130}) for k, v in __import__("backend.app.retrofit", fromlist=["x"]).rates()["lines"].items()},
           "pct_lines": {"preliminaries_and_margins": {"low": 10, "base": 10, "high": 10}, "professional_fees": {"low": 8, "base": 8, "high": 8}, "contingency": {"low": 15, "base": 15, "high": 15}}}
    r2 = scenarios.retrofit_cost(PARCEL, oid, cfg)
    n_lines = len(cfg["lines"]); assert r2["total"]["base"] == pytest.approx(r2["subtotal"]["base"] * 1.33)
    assert r2["allowance_share_pct"] > 30 and r2["banner"].startswith("Mostly allowances")      # allowance lines dominate the cost: banner shown
    assert r2["per_bed"]["base"] == pytest.approx(r2["total"]["base"] / 4)

def test_economics_and_offer_end_to_end_with_inputs(client):
    oid = client.opts["base"]["id"]
    e = client.post(f"/api/property/{PARCEL}/economics", json={"option_id": oid, "assumptions": FULL, "retrofit_total": 300000}).json()
    assert e["walk_away_rent_per_week"] is not None and e["beds"] == 4 and e["below_target"] is True
    assert e["sensitivity"]["N_range"]["low"] < e["sensitivity"]["N_range"]["base"] < e["sensitivity"]["N_range"]["high"]
    assert "min_resident_room_m2" in e["rules_not_applied"]
    off = client.post(f"/api/property/{PARCEL}/offers", json={"option_id": oid, "asking_rent": 1000, "assumptions": FULL, "retrofit": {"low": 240000, "base": 300000, "high": 360000},
                      "allowance_pct": 10, "terms": {"multiple": 2.0, "s": 0.4, "floor": 500, "s_h": 0.3, "threshold": 800}}).json()
    assert set(off["modes"]) == {"fixed", "jv", "hybrid"} and off["ranking"]
    wa = off["walk_away_rent_per_week"]
    if wa <= 0: assert off["modes"]["fixed"]["blocked"] and "no positive rent works" in off["modes"]["fixed"]["note"] and "fixed" not in off["ranking"]       # 4 beds lose money before rent: no fixed rent is offered
    else: assert off["modes"]["fixed"]["owner"]["weekly_at_stabilisation"] <= wa + 1e-9                                                                   # never above walk-away
    assert "Lawyer review required" in off["banner"] and off["modes"]["jv"]["owner"]["cases"]["occ_60"] is not None
    be = off["modes"]["jv"]["break_even_occupancy"]
    assert "needs_input" not in be and be["operator_zero_profit"] is None and "not reached" in be["note"]   # 4 beds cannot cover a fixed roster even full: reported, not hidden
    assert e["stabilised"]["net"] < 0
    assert len(client.get(f"/api/property/{PARCEL}/scenarios").json()) >= 3
    bad = client.post(f"/api/property/{PARCEL}/economics", json={"option_id": oid, "assumptions": {"nonsense": 1}}); assert bad.status_code == 422

def test_option_of_another_property_rejected(client):
    assert client.post(f"/api/property/{PARCEL}/economics", json={"option_id": 999999}).status_code == 404

FORBIDDEN_WORDS = ["guarantee", "guaranteed", "assured", "assurance", "risk-free", "risk free", "will be approved", "will be certified", "certain to", "no risk"]

def test_proposal_pack_language_downside_and_banner(client):
    oid = client.opts["base"]["id"]
    off = client.post(f"/api/property/{PARCEL}/offers", json={"option_id": oid, "asking_rent": 1000, "assumptions": FULL, "retrofit": 300000, "allowance_pct": 10,
                                                              "terms": {"multiple": 2.0, "s": 0.4, "floor": 500, "s_h": 0.3, "threshold": 800, "conversion_payment_per_week": 300}}).json()
    for mode in [k for k, m in off["modes"].items() if not m.get("blocked")]:
        r = client.get(f"/api/scenarios/{off['scenario_id']}/proposal", params={"mode": mode})
        assert r.status_code == 200, r.text; t = r.json()["markdown"]
        assert "LAWYER REVIEW REQUIRED" in t and "Downside" in t and "Assumptions appendix" in t and "never contact tenants" in t
        low = t.lower()
        for w in FORBIDDEN_WORDS: assert w not in low, (mode, w)
        assert "minimum payment" in low or mode != "hybrid"
    assert client.get(f"/api/scenarios/{off['scenario_id']}/proposal.pdf", params={"mode": "jv"}).content.startswith(b"%PDF")
    assert client.get("/api/scenarios/999999/proposal", params={"mode": "jv"}).status_code == 404

def test_forbidden_words_in_all_generating_code():
    from pathlib import Path
    for f in ("economics.py", "proposal.py", "briefs.py", "scenarios.py", "layout.py", "compliance.py", "retrofit.py", "gaps.py"):
        t = (Path(__file__).resolve().parent.parent / "backend" / "app" / f).read_text().lower()
        for w in ("guarantee", "assured", "risk-free", "will be approved", "will be certified"): assert w not in t, (f, w)
