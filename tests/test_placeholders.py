"""Placeholder inputs: loaded only into blanks with a source, banner and list of what drove a result, verdicts capped at AMBER, per-deal overrides, the Placeholders page API."""
import pytest
from backend.app import settings, verdict as V
from tests.test_listings import addrs, admin, CSV_HEAD, post, client as _lc  # noqa: F401
from tests.test_settings_map import INPUTS
from tests.test_economics import P as BASEP

BANNER = "Uses placeholder inputs: not decision-grade"

@pytest.fixture()
def client(_lc):
    with admin() as c: c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history")
    yield _lc
    with admin() as c:
        c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history")
        c.execute("DELETE FROM core.rh_scenario WHERE parcel_id IN (SELECT parcel_id FROM core.user_listing WHERE source_id LIKE 'T-ph%')")

def save(client, values, flag):
    r = client.put("/api/settings/assumptions", json={"values": values, "flags": {k: flag for k in values}, "notes": {k: "test source" for k in values}}); assert r.status_code == 200, r.text

def listing_id(client, addrs, beds=30, rent=3000, sid="T-ph"):
    full, num, road, sub, pid = addrs["single"]
    post(client, CSV_HEAD + f"{sid},{num} {road},{sub},{rent},{beds},8,rent,\n", dry_run=False)
    with admin() as c: return c.execute("SELECT id FROM core.user_listing WHERE source_id = %s", (sid,)).fetchone()[0]

# ------------------------------------------------------------------ the loader
def test_loader_fills_only_blanks_with_flag_and_source_and_never_overwrites(client):
    save(client, {"utilities_per_week": 777}, "owner_entered")                           # the owner's own figure
    r = client.post("/api/placeholders/load").json()
    assert "utilities_per_week" in r["kept_your_values"] and "utilities_per_week" not in r["loaded"]
    a = client.get("/api/settings").json()["assumptions"]
    assert a["utilities_per_week"]["value"] == 777 and a["utilities_per_week"]["flag"] == "owner_entered"
    d = settings.placeholder_defs()
    for k, x in d["placeholders"].items():
        if k == "utilities_per_week": continue
        assert a[k]["value"] == x["value"] and a[k]["flag"] == "placeholder" and len(a[k]["note"]) > 40, k           # every placeholder carries its source
    assert a["roster_coverage_multiplier"]["value"] == 1.4 and a["roster_coverage_multiplier"]["flag"] == "confirmed" and "owner" in a["roster_coverage_multiplier"]["note"]
    assert a["cash_limit"]["value"] is None                                                                          # deal-dependent: not given a placeholder
    assert client.post("/api/placeholders/load").json()["loaded"] == []                                              # idempotent

def test_every_placeholder_has_a_source_and_basis_and_cautious_cost_inputs_are_not_zero():
    d = settings.placeholder_defs()["placeholders"]
    for k, x in d.items():
        assert x["source"].strip() and x["basis"] and x["label"] and x["value"] > 0, k
    assert d["lease_term_years"]["value"] <= 10 and d["cost_of_capital_pct"]["value"] >= 6 and d["minimum_acceptable_profit_per_year"]["value"] >= 100000     # cautious direction

# ------------------------------------------------------------------ verdict cap and banner
FULL = {k: v for k, v in INPUTS.items()} | {"fill_ramp_by_month": [0.5, 0.6, 0.8, 1.0], "pre_opening_costs": 20000, "working_capital": 15000}

def test_green_is_capped_at_amber_while_placeholders_are_used_and_returns_when_real(client, addrs):
    lid = listing_id(client, addrs)
    save(client, FULL, "placeholder")
    v = client.get(f"/api/listings/{lid}").json()
    assert v["verdict"] == "AMBER" and v["placeholder_banner"] == BANNER and v["placeholders_used"]
    assert any("capped at AMBER" in r for r in v["reasons"])
    used = {x["key"] for x in v["placeholders_used"]}; assert {"clinical_lead_cost_per_week", "lease_term_years", "minimum_acceptable_profit_per_year"} <= used
    save(client, FULL, "owner_entered")                                                                              # the same numbers, now the owner's own
    v2 = client.get(f"/api/listings/{lid}").json()
    assert v2["verdict"] == "GREEN" and v2["placeholder_banner"] is None and v2["placeholders_used"] == []
    save(client, {"retrofit_cost_per_bed_screening": 10000}, "estimate")                                             # an owner estimate is also not decision-grade
    v3 = client.get(f"/api/listings/{lid}").json(); assert v3["verdict"] == "AMBER" and [x["key"] for x in v3["placeholders_used"]] == ["retrofit_cost_per_bed_screening"]

def test_red_stays_red_and_grey_has_no_banner(client, addrs):
    lid = listing_id(client, addrs, beds=7, rent=1950, sid="T-ph2")
    save(client, FULL, "placeholder"); v = client.get(f"/api/listings/{lid}").json()
    assert v["verdict"] == "RED" and v["placeholder_banner"] == BANNER                                               # a red is not softened to amber
    with admin() as c: c.execute("DELETE FROM core.user_setting")
    g = client.get(f"/api/listings/{lid}").json(); assert g["verdict"] == "GREY" and g["placeholder_banner"] is None and g["placeholders_used"] == []   # no numbers, no banner

def test_pure_function_cap():
    mb = V.minimum_beds({**BASEP, "retrofit_cost_per_bed_screening": 10000})["minimum_beds"]
    PV = {**BASEP, "retrofit_cost_per_bed_screening": 10000}; wa = V.at_beds(mb + 3, PV)["walk_away_rent"]
    site = {"parcel_id": 1, "zone_name": "Z", "title_type": "Freehold", "hazard_flags": [], "pc120_depends": False}; rows = [{"activity": "x", "status_class": "discretionary", "section_ref": "r"}]
    lst = {"bedrooms": mb + 3, "rent_per_week": wa * 0.8, "parcel_id": 1, "match_confidence": "high"}
    assert V.verdict(lst, site, rows, PV, "DOCUMENTED")["verdict"] == "GREEN"
    assert V.verdict(lst, site, rows, PV, "DOCUMENTED", [{"key": "k", "label": "L", "value": 1, "flag": "placeholder", "source": "s"}])["verdict"] == "AMBER"

# ------------------------------------------------------------------ economics, offers, proposal, map, per-deal overrides
def test_offer_economics_proposal_and_map_carry_the_banner_and_list(client, addrs):
    lid = listing_id(client, addrs, sid="T-ph3"); save(client, FULL, "placeholder")
    terms = {"multiple": 1.0, "s": 0.4, "floor": 500, "s_h": 0.3, "threshold": 800, "conversion_payment_per_week": 300}
    o = client.post(f"/api/listings/{lid}/offer", json={"terms": terms}).json()
    assert o["placeholder_banner"] == BANNER and {"pre_opening_costs", "working_capital", "lease_term_years"} <= {x["key"] for x in o["placeholders_used"]}
    o2 = client.post(f"/api/listings/{lid}/offer", json={"terms": terms, "assumptions": {"lease_term_years": 12, "pre_opening_costs": 90000}}).json()     # per-deal figures are the owner's, not placeholders
    keys = {x["key"] for x in o2["placeholders_used"]}; assert "lease_term_years" not in keys and "pre_opening_costs" not in keys and "working_capital" in keys
    md = client.get(f"/api/scenarios/{o['scenario_id']}/proposal", params={"mode": "jv"}).json()["markdown"]
    assert BANNER in md and "Placeholder inputs this proposal rests on" in md and "Lease term" in md
    m = client.get("/api/map/listings").json(); assert BANNER in m["placeholder_banner"] and any(f["properties"]["placeholders"] for f in m["features"])
    save(client, FULL, "owner_entered"); o3 = client.post(f"/api/listings/{lid}/offer", json={"terms": terms}).json()
    assert o3["placeholder_banner"] is None and o3["placeholders_used"] == [] and BANNER not in client.get(f"/api/scenarios/{o3['scenario_id']}/proposal", params={"mode": "jv"}).json()["markdown"]
    assert client.get("/api/map/listings").json()["placeholder_banner"] is None

# ------------------------------------------------------------------ the Placeholders page
def test_placeholders_page_lists_value_source_and_edit_removes_it(client):
    client.post("/api/placeholders/load")
    d = client.get("/api/placeholders").json()
    assert d["banner"] == BANNER and len(d["placeholders"]) == len(settings.placeholder_defs()["placeholders"])
    row = next(x for x in d["placeholders"] if x["key"] == "insurance_per_year")
    assert row["value"] == 60000 and row["flag"] == "placeholder" and "Deliberately high" in row["source"] and row["label"]
    assert not any(x["key"] == "roster_coverage_multiplier" for x in d["placeholders"])                              # the confirmed 1.4 is not a placeholder
    client.put("/api/settings/assumptions", json={"values": {"insurance_per_year": 41000}, "flags": {"insurance_per_year": "quote"}, "notes": {"insurance_per_year": "broker quote"}})
    d2 = client.get("/api/placeholders").json(); assert not any(x["key"] == "insurance_per_year" for x in d2["placeholders"]) and len(d2["placeholders"]) == len(d["placeholders"]) - 1
    assert client.put("/api/settings/assumptions", json={"values": {"insurance_per_year": 1}, "flags": {"insurance_per_year": "hopeful"}}).status_code == 422

def test_bed_rules_typed_from_own_copy_need_a_clause(client):
    from backend.app import bedrules
    assert client.get("/api/bed-rules").json()["building_code_clauses_verified"] is False
    r = client.put("/api/bed-rules", json={"values": {"min_resident_room_m2": {"value": 12}}}); assert r.status_code == 422        # no clause: refused
    assert client.put("/api/bed-rules", json={"values": {"min_resident_room_m2": {"value": 0.5, "clause": "x"}}}).status_code == 422
    assert client.put("/api/bed-rules", json={"values": {"ensuite_required": {"value": "sometimes", "clause": "x"}}}).status_code == 422
    assert client.put("/api/bed-rules", json={"values": {"nonsense": {"value": 1, "clause": "x"}}}).status_code == 422
    try:
        r = client.put("/api/bed-rules", json={"values": {"min_resident_room_m2": {"value": 12, "clause": "owner's copy, clause 1.2"}}}).json()
        assert r["regulatory"]["min_resident_room_m2"]["value"] == 12 and r["regulatory"]["min_resident_room_m2"]["clause"] and "min_resident_room_m2" not in r["missing"] and bedrules.reg("min_resident_room_m2") == 12
    finally:
        client.put("/api/bed-rules", json={"values": {"min_resident_room_m2": {"value": None}}})
    assert bedrules.reg("min_resident_room_m2") is None and "min_resident_room_m2" in client.get("/api/bed-rules").json()["missing"]

def test_bed_rule_can_be_marked_not_stated_in_the_standard(client):
    from backend.app import bedrules
    try:
        r = client.put("/api/bed-rules", json={"values": {"communal_area_per_bed_m2": {"not_stated": True, "clause": "section 4.1 checked"}}}).json()
        assert r["states"]["communal_area_per_bed_m2"] == "not_stated" and r["regulatory"]["communal_area_per_bed_m2"]["value"] is None
        assert bedrules.reg("communal_area_per_bed_m2") is None and "communal_area_per_bed_m2" in r["missing"] and r["states"]["min_resident_room_m2"] in ("blank", "entered")
    finally:
        client.put("/api/bed-rules", json={"values": {"communal_area_per_bed_m2": {"value": None}}})
    assert client.get("/api/bed-rules").json()["states"]["communal_area_per_bed_m2"] == "blank"
