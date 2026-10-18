"""Feeds admin, importers (attributes, sales, rest homes, census): dry run, rejects, match rate, apply, and the effect on screening and suburb analytics."""
import pytest
from fastapi.testclient import TestClient
from backend.app import importers, screen
from backend.app.db import conn

@pytest.fixture(scope="module")
def client():
    from backend.app.main import app
    def clean():
        with conn() as c:
            for t in ("user_property_attribute", "user_sale", "user_demographic", "user_rest_home", "user_import_log"): c.execute(f"DELETE FROM core.{t}")
            c.commit()
    clean(); yield TestClient(app); clean()

def target():
    from backend.app import listings
    with conn() as c:
        rows = c.execute("SELECT s.parcel_id, s.address, s.suburb, ST_XMin(g.geom) a, ST_YMin(g.geom) b, ST_XMax(g.geom) c, ST_YMax(g.geom) d FROM analytics.rh_screen s JOIN core.sites g ON g.parcel_id=s.parcel_id WHERE s.beds_tier='ESTIMATED' AND s.address ~ '^[0-9]+ ' AND s.suburb ~ '^[A-Za-z ]+$' ORDER BY s.parcel_id LIMIT 60").fetchall()
        for r in rows:
            m = listings.match_address(c, r["address"].split(",")[0], r["suburb"]); m2 = listings.match_address(c, r["address"], None)
            if m["confidence"] == "high" and m2["confidence"] == "high" and m["parcel_id"] == r["parcel_id"] == m2["parcel_id"]: return r
    raise AssertionError("no unambiguous test address found")

def up(client, kind, text, **data): return client.post(f"/api/importers/{kind}", files={"file": ("f.csv", text.encode())}, data=data)

def test_feeds_admin_lists_the_register(client):
    f = client.get("/api/feeds").json(); by = {x["feed"]: x for x in f}
    assert len(f) == 22 and by["Auckland Council forms, fee schedules, lodgement checklists"]["status"] == "manual" and "AC1009" in by["Auckland Council forms, fee schedules, lodgement checklists"]["blocked_reason"] and by["Auckland Council open data (zones, overlays, hazards, property keys)"]["rows"] > 0

def test_attributes_dry_run_rejects_apply_and_screening(client):
    t = target(); addr = t["address"].split(",")[0]
    csv = f"Property Address,Suburb,Beds,Baths,Floor Area,Year Built\n{addr},{t['suburb']},9,3,420,1985\n999 Nowhere Boulevard,Nowhere,4,2,150,1990\n{addr},{t['suburb']},abc,2,100,1990\n"
    d = up(client, "property_attributes", csv, dry_run="true").json()
    assert d["rows"] == 3 and d["dry_run"] is True and d["rejected"] == 1
    assert d["columns_mapped"]["bedrooms"] == "Beds" and d["columns_mapped"]["build_year"] == "Year Built" and d["match"]["high"] + d["match"]["medium"] >= 1 and 0 < d["match_rate"] <= 1 and d["null_rates"]["storeys"] == 1.0
    with conn() as c: assert c.execute("SELECT count(*) AS n FROM core.user_property_attribute").fetchone()["n"] == 0            # a dry run writes nothing
    assert up(client, "property_attributes", csv, dry_run="false").status_code == 422                                         # source and licence needed to apply
    a = up(client, "property_attributes", csv, dry_run="false", source="Supplier X, licence allows private AI-queried use").json(); assert a["applied"] == 1 and a["rejected"] == 2
    with conn() as c: row = c.execute("SELECT * FROM core.user_property_attribute").fetchone(); assert row["bedrooms"] == 9 and float(row["floor_area_m2"]) == 420 and row["source"].startswith("Supplier X")
    screen.run((t["a"] - 5, t["b"] - 5, t["c"] + 5, t["d"] + 5), progress=None)
    with conn() as c: s = c.execute("SELECT beds_base, beds_tier, beds_source FROM analytics.rh_screen WHERE parcel_id=%s", (t["parcel_id"],)).fetchone()
    assert (s["beds_base"], s["beds_tier"]) == (9, "DOCUMENTED") and "licensed" in s["beds_source"]
    assert [x["dry_run"] for x in client.get("/api/importers/log").json()][:2] == [False, True]

def test_mapping_override_missing_required_and_bad_column(client):
    odd = "Where,Num,When\n1 Queen Street,12,2024-05-01\n"
    r = up(client, "sales", odd, dry_run="true").json(); assert r["required_missing"] and "required column" in r["note"]
    ok = up(client, "sales", odd, dry_run="true", mapping='{"address":"Where","price":"Num","sale_date":"When"}').json(); assert ok["required_missing"] == [] and ok["rows"] == 1 and ok["sample"][0]["price"] == 12.0
    assert up(client, "sales", odd, dry_run="true", mapping='{"address":"Nope"}').status_code == 422 and up(client, "wizards", odd).status_code == 422
    bad = up(client, "sales", "address,sale date,price\n1 Queen Street,31/02/2024,100\n", dry_run="true").json(); assert bad["rejected"] == 1 and "date" in bad["rejects"][0]["reason"]

def test_rest_homes_and_census_fill_the_suburb_analytics(client):
    from backend.app import screenapi
    t = target(); addr = t["address"].split(",")[0]
    assert any(x["certified_beds_existing"] is None for x in screenapi.suburbs()["suburbs"]) and any("HealthCERT" in n for n in screenapi.suburbs()["notes"])
    h = up(client, "rest_homes", f"Provider Name,Physical Address,Certified Beds\nTest Care Home,\"{t['address']}\",40\n", dry_run="false", source="HealthCERT export test").json(); assert h["applied"] == 1
    d = up(client, "demographics", f"Area,Census Year,Population aged 75+\n{t['suburb']},2023,2000\n", dry_run="false", source="Stats NZ test").json(); assert d["applied"] == 1
    row = next(x for x in screenapi.suburbs()["suburbs"] if x["suburb"] == t["suburb"]); assert row["certified_beds_existing"] == 40 and row["beds_per_1000_aged_75_plus"] == 20.0
    sub = screenapi.suburbs(); assert not any("no census data" in n for n in sub["notes"]) and not any("no rest home list" in n for n in sub["notes"])
    with conn() as c: pt = c.execute("SELECT lon, lat FROM core.user_rest_home").fetchone()
    g = client.get("/api/layers/rest_homes", params={"bbox": f"{pt['lon'] - .01},{pt['lat'] - .01},{pt['lon'] + .01},{pt['lat'] + .01}"}).json(); assert g["features"][0]["properties"]["name"] == "Test Care Home"
