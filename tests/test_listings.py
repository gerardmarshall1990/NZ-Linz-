"""Listings import, address matching, history, Property Record upgrade, verdict logic (hand-calculated cases), minimum beds, coverage, and a repo scan for scraping code. Needs `make app-db`."""
import os, re
from datetime import date, timedelta
from pathlib import Path
import psycopg
import pytest
from fastapi.testclient import TestClient
from backend.app import economics as E, verdict as V
from tests.test_economics import P as BASEP

ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)

def admin():
    return psycopg.connect(f"host=localhost dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}", autocommit=True)

@pytest.fixture(scope="module")
def addrs():
    """Real addresses from the database: a single-address parcel, and a multi-unit parcel with a unit address."""
    with admin() as c:
        single = c.execute("""SELECT a.full_address, a.address_number, a.full_road_name, a.suburb_locality, s.parcel_id FROM core.sites s JOIN raw.linz_addresses a ON ST_Intersects(s.geom, a.geom)
                              WHERE s.address_count = 1 AND a.unit IS NULL AND a.address_lifecycle = 'Current' AND a.suburb_locality IS NOT NULL AND s.parcel_id NOT IN (4898114, 4899224)
                                AND (SELECT count(*) FROM raw.linz_addresses b WHERE b.address_number = a.address_number AND lower(b.full_road_name_ascii) = lower(a.full_road_name_ascii)) = 1 LIMIT 1""").fetchone()
        multi = c.execute("""SELECT a.full_address, a.unit, a.address_number, a.full_road_name, a.suburb_locality, s.parcel_id FROM core.sites s JOIN raw.linz_addresses a ON ST_Intersects(s.geom, a.geom)
                             WHERE s.address_count BETWEEN 2 AND 4 AND a.unit IS NOT NULL AND a.address_lifecycle = 'Current' AND a.suburb_locality IS NOT NULL AND s.parcel_id NOT IN (4898114, 4899224)
                               AND (SELECT count(DISTINCT s2.parcel_id) FROM raw.linz_addresses b JOIN core.sites s2 ON ST_Intersects(s2.geom, b.geom) WHERE b.address_number = a.address_number AND lower(b.full_road_name_ascii) = lower(a.full_road_name_ascii)) = 1 LIMIT 1""").fetchone()
    return {"single": single, "multi": multi}

@pytest.fixture(scope="module")
def client(addrs):
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            num, road = addrs["single"][1], addrs["single"][2]
            c.execute("DELETE FROM core.user_listing WHERE source_id LIKE 'T-%%' OR raw_address LIKE '%%Unmatched Nowhere%%' OR raw_address = %s", (f"{num} {road}",))
            for pid in (addrs["single"][4], addrs["multi"][5]):
                c.execute("DELETE FROM core.rh_scenario WHERE parcel_id=%s", (pid,))
                c.execute("DELETE FROM core.rh_property_fact_history WHERE parcel_id=%s", (pid,)); c.execute("DELETE FROM core.rh_property_fact WHERE parcel_id=%s", (pid,)); c.execute("DELETE FROM core.rh_property WHERE parcel_id=%s", (pid,))
            c.commit()
    clean(); yield TestClient(app); clean()

CSV_HEAD = "source_id,address,suburb,rent_per_week,bedrooms,bathrooms,listing_type,url\n"

# ---------------------------------------------------------------- address matching
def test_address_normalisation():
    from backend.app.listings import parse_address
    assert parse_address("12B/45 Queen St, Grey Lynn, Auckland") == {"unit": "12B", "number": 45, "suffix": "", "street": "queen street", "suburb": "grey lynn"}
    assert parse_address("Unit 3/7A Smith Rd") == {"unit": "3", "number": 7, "suffix": "A", "street": "smith road", "suburb": None}
    assert parse_address("no number here") == {}

def test_match_exact_and_abbreviation_and_wrong_suburb(client, addrs):
    from backend.app.listings import match_address
    from backend.app.db import conn
    full, num, road, sub, pid = addrs["single"]
    with conn() as c:
        m = match_address(c, f"{num} {road}", sub); assert m["confidence"] == "high" and m["parcel_id"] == pid
        abbr = re.sub(r"\bStreet\b", "St", road); abbr = re.sub(r"\bRoad\b", "Rd", abbr); abbr = re.sub(r"\bAvenue\b", "Ave", abbr)
        assert match_address(c, f"{num} {abbr}, {sub}, Auckland", None)["parcel_id"] == pid
        assert match_address(c, f"{num} {road}")["confidence"] == "medium"                       # no suburb supplied: lower confidence, said so
        assert match_address(c, "99999 Nonexistent Street")["confidence"] == "none"
        assert match_address(c, "just words")["confidence"] == "none"
        mu = match_address(c, f"{addrs['multi'][1]}/{addrs['multi'][2]} {addrs['multi'][3]}", addrs["multi"][4]); assert mu["parcel_id"] == addrs["multi"][5] and mu["confidence"] in ("high", "medium")

# ---------------------------------------------------------------- import, history, dedupe
def post(client, text, **form):
    return client.post("/api/listings/import", files={"file": ("l.csv", text.encode())}, data={"source": "csv_manual", **{k: str(v).lower() if isinstance(v, bool) else v for k, v in form.items()}})

def test_import_dry_run_new_changed_unchanged_history_relist_snapshot(client, addrs):
    full, num, road, sub, pid = addrs["single"]
    base = CSV_HEAD + f"T-1,{num} {road},{sub},900,6,3,rent,https://example.test/1\n"
    r = post(client, base, dry_run=True).json(); assert r["new"] == 1 and r["dry_run"] is True
    assert client.post("/api/listings/search", json={"filters": {"source": "csv_manual"}}).json()["count"] == 0     # dry run wrote nothing
    r = post(client, base, dry_run=False).json(); assert r["new"] == 1 and r["matched"]["high"] == 1
    assert post(client, base, dry_run=False).json()["unchanged"] == 1                                                  # dedupe by source id
    # same listing without an id dedupes by normalised address
    r2 = post(client, "address,suburb,rent_per_week,bedrooms,listing_type\n" + f"{num} {road},{sub},900,6,rent\n", dry_run=False).json(); assert r2["new"] == 1
    # rent change creates a history row
    r = post(client, CSV_HEAD + f"T-1,{num} {road},{sub},950,6,3,rent,https://example.test/1\n", dry_run=False).json(); assert r["changed"] == 1
    with admin() as c:
        h = c.execute("SELECT field, old_value, new_value FROM core.user_listing_history h JOIN core.user_listing l ON l.id = h.listing_id WHERE l.source_id = 'T-1'").fetchall()
    rh = [x for x in h if x[0] == "rent_per_week"]; assert len(rh) == 1 and float(rh[0][1]) == 900 and float(rh[0][2]) == 950
    # snapshot import without it removes the listing; re-appearing relists it with history
    r = post(client, CSV_HEAD + "T-2,1 Unmatched Nowhere Road,,500,3,1,rent,\n", dry_run=False, snapshot=True).json(); assert r["removed"] >= 1
    with admin() as c: assert c.execute("SELECT status FROM core.user_listing WHERE source_id = 'T-1'").fetchone()[0] == "removed"
    r = post(client, base, dry_run=False).json(); assert r["changed"] == 1
    with admin() as c: assert c.execute("SELECT status FROM core.user_listing WHERE source_id = 'T-1'").fetchone()[0] == "active"
    # the unmatched one is in the review queue and can be fixed by the owner
    q = [x for x in client.get("/api/listings/review-queue").json() if x["raw_address"].startswith("1 Unmatched")]; assert q and q[0]["match_confidence"] == "none"
    assert client.put(f"/api/listings/{q[0]['id']}/match", json={"parcel_id": pid}).json()["match_confidence"] == "high"
    assert not [x for x in client.get("/api/listings/review-queue").json() if x["raw_address"].startswith("1 Unmatched")]

def test_bad_csv_and_unknown_source_rejected(client):
    assert client.post("/api/listings/import", files={"file": ("l.csv", b"foo,bar\n1,2\n")}, data={"source": "csv_manual"}).status_code == 422
    assert client.post("/api/listings/import", files={"file": ("l.csv", (CSV_HEAD + "T-9,1 A St,,1,1,1,flat,\n").encode())}, data={"source": "csv_manual", "dry_run": "false"}).status_code == 422
    assert client.post("/api/listings/import", files={"file": ("l.csv", CSV_HEAD.encode())}, data={"source": "nope"}).status_code == 422

# ---------------------------------------------------------------- Property Record upgrade
def test_listing_upgrades_record_to_documented_but_never_over_confirmed(client, addrs):
    full, num, road, sub, pid = addrs["single"]
    post(client, CSV_HEAD + f"T-3,{num} {road},{sub},800,7,4,rent,\n", dry_run=False)
    with admin() as c: lid = c.execute("SELECT id FROM core.user_listing WHERE source_id = 'T-3'").fetchone()[0]
    r = client.post(f"/api/listings/{lid}/upgrade-record").json(); assert set(r["upgraded"]) == {"bedrooms_total", "bathrooms_total"}
    rec = client.get(f"/api/property/{pid}").json()["facts"]; assert rec["bedrooms_total"]["confidence"] == "DOCUMENTED" and rec["bedrooms_total"]["value"] == 7 and "listing" in rec["bedrooms_total"]["source"]
    client.put(f"/api/property/{pid}/facts", json={"field": "bedrooms_total", "value": 5, "source": "confirmed plan", "confidence": "CONFIRMED"})
    r = client.post(f"/api/listings/{lid}/upgrade-record").json(); assert r["skipped"] and "CONFIRMED" in r["skipped"][0]["reason"]
    assert client.get(f"/api/property/{pid}").json()["facts"]["bedrooms_total"]["value"] == 5
    with admin() as c: lid2 = c.execute("SELECT id FROM core.user_listing WHERE source_id = 'T-2'").fetchone()
    assert client.post("/api/listings/999999/upgrade-record").status_code == 404

# ---------------------------------------------------------------- verdict logic, hand-calculated
PV = {**BASEP, "retrofit_cost_per_bed_screening": 10000}
SITE = {"parcel_id": 1, "zone_name": "Residential - Single House Zone", "title_type": "Freehold", "hazard_flags": ["flood plain"], "pc120_depends": False}
ROWS = [{"activity": "Supported residential care", "status_class": "discretionary", "section_ref": "H3.4.1 (A1)"}]

def test_minimum_beds_closed_form_matches_brute_force():
    mb = V.minimum_beds(PV)
    def profit(beds): return E.operating(beds, 0.9, PV)["net"] - E.retrofit_charge_weekly(beds * 10000, PV)["weekly"] - 130000 / 52
    brute = next(b for b in range(1, 500) if profit(b) >= 0)
    assert mb["minimum_beds"] == brute and profit(brute - 1) < 0
    tgt = next(b for b in range(1, 500) if profit(b) - (260000 - 130000) / 52 >= 0); assert mb["target_beds"] == tgt
    assert V.minimum_beds(dict(PV, retrofit_cost_per_bed_screening=None))["minimum_beds"] is None
    assert V.minimum_beds(dict(PV, retrofit_cost_per_bed_screening=1e9))["minimum_beds"] is None        # every extra bed loses money: reported as None

def L(beds, rent, **kw): return {"bedrooms": beds, "rent_per_week": rent, "parcel_id": 1, "match_confidence": "high", **kw}

def test_verdict_green_amber_red_grey_cases():
    mb = V.minimum_beds(PV)["minimum_beds"]; wa = V.at_beds(mb + 3, PV)["walk_away_rent"]
    g = V.verdict(L(mb + 3, wa * 0.8), SITE, ROWS, PV, "DOCUMENTED"); assert g["verdict"] == "GREEN" and g["economics"]["rent_multiple_possible"] == pytest.approx(wa / (wa * 0.8))
    assert V.verdict(L(mb + 3, wa * 0.8), SITE, ROWS, PV, "ESTIMATED")["verdict"] == "AMBER"                     # data only estimated
    assert V.verdict(L(mb + 3, wa * 0.8), {**SITE, "title_type": None}, ROWS, PV, "DOCUMENTED")["verdict"] == "AMBER"   # title unknown
    assert V.verdict(L(mb + 3, wa * 0.8), SITE, [], PV, "DOCUMENTED")["verdict"] == "AMBER"                       # no activity rows: unknown
    r = V.verdict(L(mb + 3, wa * 1.2), SITE, ROWS, PV, "DOCUMENTED"); assert r["verdict"] == "RED" and any("not viable at the asking rent" in x for x in r["reasons"])
    r = V.verdict(L(mb - 1, 100), SITE, ROWS, PV, "DOCUMENTED"); assert r["verdict"] == "RED" and any("too small" in x for x in r["reasons"])
    assert V.verdict(L(mb + 3, 100), {**SITE, "title_type": "Unit title"}, ROWS, PV, "DOCUMENTED")["verdict"] == "RED"
    assert V.verdict(L(mb + 3, 100), {**SITE, "title_type": "Cross lease"}, ROWS, PV, "DOCUMENTED")["verdict"] == "RED"
    assert V.verdict(L(mb + 3, 100), SITE, [{"activity": "x", "status_class": "prohibited", "section_ref": "r"}], PV, "DOCUMENTED")["verdict"] == "RED"
    assert V.verdict(L(None, 100), SITE, ROWS, PV)["verdict"] == "GREY" and V.verdict(L(8, 100, match_confidence="low"), SITE, ROWS, PV)["verdict"] == "GREY"
    assert V.verdict({**L(8, 100), "parcel_id": None}, None, [], PV)["verdict"] == "GREY"

def test_verdict_grey_with_unset_inputs_and_never_says_approved():
    r = V.verdict(L(8, 900), SITE, ROWS, {**PV, "clinical_lead_cost_per_week": None}, "DOCUMENTED")
    assert r["verdict"] == "GREY" and "clinical_lead_cost_per_week" in r["needs_input"]
    r2 = V.verdict(L(8, 900), {**SITE, "title_type": "Unit title"}, ROWS, {**PV, "clinical_lead_cost_per_week": None})
    assert r2["verdict"] == "RED"                                                           # a deal-breaker still shows even with inputs unset
    text = str(V.verdict(L(12, 500), SITE, ROWS, PV)).lower()
    assert "approved" not in text and "will work" not in text.replace("promise that it will work", "")

def test_hazards_are_information_only():
    mb = V.minimum_beds(PV)["minimum_beds"]; wa = V.at_beds(mb + 3, PV)["walk_away_rent"]
    base = V.verdict(L(mb + 3, wa * 0.8), SITE, ROWS, PV, "DOCUMENTED")
    for hz in (None, [], ["flood plain", "coastal inundation", "tsunami zone", "landslide high"]):
        v = V.verdict(L(mb + 3, wa * 0.8), {**SITE, "hazard_flags": hz}, ROWS, PV, "DOCUMENTED")
        assert v["verdict"] == base["verdict"] and v["reasons"] == base["reasons"] and v["economics"] == base["economics"]
    assert "information only" in base["hazard_note"] and base["hazard_info"] == ["flood plain"]

def test_offer_levels_and_ceiling():
    mb = V.minimum_beds(PV)["minimum_beds"]; beds = mb + 5; wa = V.at_beds(beds, PV)["walk_away_rent"]
    v = V.verdict(L(beds, wa / 2.5), SITE, ROWS, PV, "DOCUMENTED"); lv = {x["multiple"]: x for x in v["offer_levels"]}
    assert lv[2.0]["above_ceiling"] is False and lv[2.0]["weekly_profit_after_rent"] > 130000 / 52 - 1e-6
    v2 = V.verdict(L(beds, wa / 1.4), SITE, ROWS, PV, "DOCUMENTED"); lv2 = {x["multiple"]: x for x in v2["offer_levels"]}
    assert lv2[1.5]["above_ceiling"] is True and lv2[1.25]["above_ceiling"] is False                  # suggests nothing above the ceiling; flags it
    assert v["economics"]["offer_ceiling"] == pytest.approx(wa)

# ---------------------------------------------------------------- API end to end, coverage, no scraping
def test_default_config_gives_grey_and_search_counts_and_coverage(client, addrs):
    full, num, road, sub, pid = addrs["single"]
    post(client, CSV_HEAD + f"T-4,{num} {road},{sub},800,9,4,rent,\nT-5,1 Unmatched Nowhere Road,,500,3,1,rent,\n", dry_run=False)
    r = client.post("/api/listings/search", json={"filters": {"source": "csv_manual"}}).json()
    assert r["verdict_counts"]["GREY"] == r["count"] > 0                                    # no deal inputs: nothing is guessed
    assert "Trade Me" in r["source_coverage"] and "realestate.co.nz" in r["source_coverage"] and "incomplete" in r["source_coverage"]
    src = client.get("/api/listings/sources").json()["sources"]; assert src["realestate_co_nz"]["status"] == "blocked" and src["trademe"]["status"] == "pending" and src["csv_manual"]["status"] == "live"
    ov = {k: v for k, v in PV.items() if k in __import__("backend.app.economics", fromlist=["x"]).default_assumptions()}
    r = client.post("/api/listings/search", json={"filters": {"source": "csv_manual", "min_beds": 8}, "assumptions": ov}).json()
    assert r["count"] >= 1 and all(o["listing"]["bedrooms"] >= 8 for o in r["listings"]) and r["verdict_counts"]["GREY"] == 0

def test_no_scraping_code_in_repo():
    banned = re.compile(r"^\s*(import|from)\s+(bs4|scrapy|selenium|playwright|mechanize|requests_html|lxml\.html|pyppeteer)\b", re.M)
    for d in ("backend", "scripts"):
        for f in (ROOT / d).rglob("*.py"): assert not banned.search(f.read_text()), f
    for f in list((ROOT / "backend").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):          # no HTTP calls to listing sites anywhere
        assert not re.search(r"(urlopen|requests\.|httpx\.|curl)[^\n]*(trademe|realestate)", f.read_text(), re.I), f

# ---------------------------------------------------------------- Offer Builder from a listing (no plans yet)
def test_offer_from_listing_screening(client, addrs):
    from tests.test_settings_map import INPUTS
    full, num, road, sub, pid = addrs["single"]
    post(client, CSV_HEAD + f"T-off,{num} {road},{sub},900,14,4,rent,\n", dry_run=False)
    with admin() as c: lid = c.execute("SELECT id FROM core.user_listing WHERE source_id = 'T-off'").fetchone()[0]
    terms = {"multiple": 1.5, "s": 0.4, "floor": 500, "s_h": 0.3, "threshold": 800, "conversion_payment_per_week": 300}
    r = client.post(f"/api/listings/{lid}/offer", json={"terms": terms}).json()                          # no inputs saved: needs input, no numbers
    assert r["modes"] == {} and r["needs_input"]
    ov = {k: v for k, v in INPUTS.items()} | {"fill_ramp_by_month": [0.3, 0.6, 0.8], "pre_opening_costs": 20000, "working_capital": 15000}
    r = client.post(f"/api/listings/{lid}/offer", json={"terms": terms, "assumptions": ov}).json()
    assert set(r["modes"]) == {"fixed", "jv", "hybrid"} and r["beds"] == 14 and r["basis"].startswith("screening")
    assert any("allowances" in f["text"] and f["level"] == "red" for f in r["flags"])                    # all of the screening retrofit is an allowance: red banner
    fx = r["modes"]["fixed"]
    assert (fx.get("blocked") and r["walk_away_rent_per_week"] <= 0) or fx["owner"]["weekly_at_stabilisation"] <= r["walk_away_rent_per_week"] + 1e-9
    assert r["range"]["retrofit"]["base"] == 14 * INPUTS["retrofit_cost_per_bed_screening"] and r["range"]["retrofit"]["low"] == pytest.approx(0.8 * r["range"]["retrofit"]["base"])
    assert "Lawyer review required" in r["banner"]
    pdf = client.get(f"/api/scenarios/{r['scenario_id']}/proposal.pdf", params={"mode": "jv"}); assert pdf.content.startswith(b"%PDF")
    assert client.post("/api/listings/999999/offer", json={"terms": terms}).status_code == 404
    with admin() as c: c.execute("DELETE FROM core.rh_scenario WHERE parcel_id = %s", (pid,))

def test_offer_from_listing_works_for_a_parcel_with_no_property_record_yet(client, addrs):
    from tests.test_settings_map import INPUTS
    full, num, road, sub, pid = addrs["multi"][0], addrs["multi"][2], addrs["multi"][3], addrs["multi"][4], addrs["multi"][5]
    post(client, CSV_HEAD + f"T-new,{num} {road},{sub},700,20,6,rent,\n", dry_run=False)
    with admin() as c:
        lid = c.execute("SELECT id FROM core.user_listing WHERE source_id = 'T-new'").fetchone()[0]
        assert c.execute("SELECT count(*) FROM core.rh_property WHERE parcel_id = %s", (pid,)).fetchone()[0] == 0
    ov = INPUTS | {"fill_ramp_by_month": [0.5], "pre_opening_costs": 1000, "working_capital": 1000}
    r = client.post(f"/api/listings/{lid}/offer", json={"terms": {"s": 0.4}, "assumptions": ov}); assert r.status_code == 200 and r.json()["modes"]
    with admin() as c:
        c.execute("DELETE FROM core.rh_scenario WHERE parcel_id = %s", (pid,)); c.execute("DELETE FROM core.rh_property WHERE parcel_id = %s", (pid,))

def test_settings_flags_and_notes(client):
    from backend.app import settings
    r = client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": 650}, "flags": {"utilities_per_week": "quote"}, "notes": {"utilities_per_week": "Mercury quote 12 Oct"}}).json()
    a = r["assumptions"]["utilities_per_week"]; assert a["value"] == 650 and a["flag"] == "quote" and a["note"] == "Mercury quote 12 Oct" and a["from"] == "you" and a["on"]
    r = client.put("/api/settings/assumptions", json={"values": {"insurance_per_year": 20000}}).json(); assert r["assumptions"]["insurance_per_year"]["flag"] == "owner_entered"
    assert client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": 1}, "flags": {"utilities_per_week": "guess"}}).status_code == 422
    r = client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": None, "insurance_per_year": None}}).json()
    assert r["assumptions"]["utilities_per_week"]["value"] is None and r["assumptions"]["utilities_per_week"]["flag"] is None and "utilities_per_week" in r["blank_assumptions"]     # cleared goes back to blank
    with admin() as c: c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history")

def test_negative_walk_away_rent_is_stated_plainly():
    v = V.verdict(L(7, 1950), SITE, ROWS, PV, "DOCUMENTED"); e = v["economics"]
    assert e["offer_ceiling"] < 0 and e["rent_multiple_possible"] is None and "no rent makes this work" in e["ceiling_note"] and v["verdict"] == "RED"

def test_quick_offer_from_current_rent(client, addrs):
    from tests.test_settings_map import INPUTS
    full, num, road, sub, pid = addrs["single"]
    post(client, CSV_HEAD + f"T-quick,{num} {road},{sub},1000,7,4,rent,\n", dry_run=False)
    with admin() as c: lid = c.execute("SELECT id FROM core.user_listing WHERE source_id = 'T-quick'").fetchone()[0]
    r = client.post(f"/api/listings/{lid}/quick-offer", json={"assumptions": INPUTS}).json()
    assert r["current_rent"] == 1000 and r["beds"] == 7 and r["scaled_by_beds_over_30"] == pytest.approx(7 / 30)
    assert r["net_before_rent"] == pytest.approx(r["revenue"] - r["running_costs"])
    assert r["most_you_could_pay"] == pytest.approx(r["net_before_rent"] - r["retrofit_charge"] - r["my_minimum_profit_per_week"])
    assert [o["multiple"] for o in r["offers"]] == [1.0, 1.1, 1.25, 1.5] and all(o["affordable"] == (o["rent"] <= r["most_you_could_pay"]) for o in r["offers"])
    assert client.post(f"/api/listings/{lid}/quick-offer", json={"current_rent": 2000, "assumptions": INPUTS}).json()["current_rent"] == 2000
    assert client.post(f"/api/listings/{lid}/quick-offer", json={}).json()["needs_input"]                 # nothing saved: needs input, no numbers
    assert client.post("/api/listings/999999/quick-offer", json={}).status_code == 404
