"""My inputs (settings) and map endpoints: validation, layering over the blank config, history, verdicts picking up the owner's inputs, GeoJSON for the map."""
import os
import psycopg
import pytest
from fastapi.testclient import TestClient
from tests.test_listings import addrs, admin, CSV_HEAD, post  # noqa: F401  (fixtures)

@pytest.fixture(scope="module")
def client(addrs):
    from backend.app.main import app
    def clean():
        with admin() as c:
            c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history")
            num, road = addrs["single"][1], addrs["single"][2]
            c.execute("DELETE FROM core.user_listing WHERE source_id LIKE 'T-%%' OR raw_address = %s", (f"{num} {road}",))
    clean(); yield TestClient(app); clean()

INPUTS = {"clinical_lead_cost_per_week": 2000, "manager_cost_per_week": 2500, "cook_cleaner_laundry_per_week": 1500, "utilities_per_week": 500, "insurance_per_year": 26000,
          "supplies_per_occupied_bed_per_week": 40, "repairs_maintenance_per_year": 26000, "compliance_and_certification_per_year": 13000, "other_opex_per_week": 300, "roster_coverage_multiplier": 1.5,
          "stabilised_occupancy": 0.9, "lease_term_years": 10, "cost_of_capital_pct": 8, "target_profit_per_year": 260000, "minimum_acceptable_profit_per_year": 130000, "retrofit_cost_per_bed_screening": 10000}

def test_blank_by_default_then_saved_and_validated(client):
    s = client.get("/api/settings").json()
    assert "clinical_lead_cost_per_week" in s["blank_assumptions"] and s["assumptions"]["fee_per_bed_per_week"]["from"] == "config"
    assert client.put("/api/settings/assumptions", json={"values": {"stabilised_occupancy": 90}}).status_code == 422          # fraction expected
    assert client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": -5}}).status_code == 422
    assert client.put("/api/settings/assumptions", json={"values": {"nonsense": 1}}).status_code == 422
    assert client.put("/api/settings/assumptions", json={"values": {"retrofit_funding_mode": "gift"}}).status_code == 422
    assert client.put("/api/settings/assumptions", json={"values": {"fill_ramp_by_month": [0.2, 1.5]}}).status_code == 422
    r = client.put("/api/settings/assumptions", json={"values": INPUTS}).json()
    assert r["assumptions"]["utilities_per_week"] == {"value": 500, "from": "you"} and "utilities_per_week" not in r["blank_assumptions"]
    client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": None}})
    assert "utilities_per_week" in client.get("/api/settings").json()["blank_assumptions"]            # cleared goes back to blank, never a default
    client.put("/api/settings/assumptions", json={"values": {"utilities_per_week": 500}})
    with admin() as c: assert c.execute("SELECT count(*) FROM core.user_setting_history WHERE key = 'assumption:utilities_per_week'").fetchone()[0] == 3

def test_rates_validation(client):
    assert client.put("/api/settings/rates", json={"lines": {"nurse_call": {"low": 5, "base": 4, "high": 6, "source": "QS"}}}).status_code == 422       # low <= base <= high
    assert client.put("/api/settings/rates", json={"lines": {"nurse_call": {"low": 4, "base": 5, "high": 6}}}).status_code == 422                      # needs a source
    assert client.put("/api/settings/rates", json={"lines": {"nurse_call": {"low": 4, "base": 5}, }}).status_code == 422                                # all three or none
    assert client.put("/api/settings/rates", json={"lines": {"nope": {}}}).status_code == 422
    r = client.put("/api/settings/rates", json={"lines": {"nurse_call": {"low": 400, "base": 500, "high": 650, "source": "QS quote 12 Oct"}}, "pct": {"contingency": {"low": 10, "base": 15, "high": 20}}}).json()
    assert r["rates"]["lines"]["nurse_call"]["base"] == 500 and r["rates"]["pct_lines"]["contingency"]["high"] == 20
    from backend.app import retrofit
    assert retrofit.rates()["lines"]["nurse_call"]["base"] is None                                 # the config file is untouched; the database layers over it
    client.put("/api/settings/rates", json={"lines": {"nurse_call": {"low": None, "base": None, "high": None, "source": None}}, "pct": {"contingency": {"low": None, "base": None, "high": None}}})

def test_inputs_flow_into_listing_verdicts_and_map(client, addrs):
    full, num, road, sub, pid = addrs["single"]
    post(client, CSV_HEAD + f"T-1,{num} {road},{sub},500,12,3,rent,\n", dry_run=False)
    g = client.get("/api/map/listings").json()
    mine = [f for f in g["features"] if f["properties"]["address"] == f"{num} {road}"]
    assert len(mine) == 1 and mine[0]["geometry"]["type"] == "Point"
    lon, lat = mine[0]["geometry"]["coordinates"]; assert 165 < lon < 179 and -48 < lat < -34              # NZ, WGS84 order lon,lat
    assert mine[0]["properties"]["verdict"] in ("GREEN", "AMBER", "RED")                                  # inputs were saved above: no longer GREY
    assert "incomplete" in g["source_coverage"]
    assert client.get("/api/map/listings", params={"verdict": "GREY"}).json()["verdict_counts"]["GREY"] == 0
    client.put("/api/settings/assumptions", json={"values": {"clinical_lead_cost_per_week": None}})
    assert [f for f in client.get("/api/map/listings").json()["features"] if f["properties"]["address"] == f"{num} {road}"][0]["properties"]["verdict"] == "GREY"   # back to needs input
    client.put("/api/settings/assumptions", json={"values": {"clinical_lead_cost_per_week": 2000}})

def test_parcel_at_point_and_pages(client, addrs):
    pid = addrs["single"][4]
    with admin() as c: lon, lat = c.execute("SELECT ST_X(ST_Transform(ST_PointOnSurface(geom),4326)), ST_Y(ST_Transform(ST_PointOnSurface(geom),4326)) FROM core.sites WHERE parcel_id = %s", (pid,)).fetchone()
    assert client.get("/api/sites/at", params={"lat": lat, "lon": lon}).json()["parcel_id"] == pid
    assert client.get("/api/sites/at", params={"lat": -36.0, "lon": 177.9}).status_code == 404                       # open sea
    assert client.get("/api/sites/at", params={"lat": 10, "lon": 10}).status_code == 422
    assert "Rest Home Finder" in client.get("/").text and "Plans and Property Record" in client.get("/plans").text
