"""Development engine: rules evaluator against hand-calculated geometry, layout engine, financial formulas, subdivision. Synthetic rule values (test only) so results are hand-checkable; one DB test on a real parcel."""
import pytest
from shapely.geometry import box
from backend.app import devfin, devlayout as L, devrules as D

def rules(**over):
    base = {"yard_front_min": 3, "yard_side_min": 1, "yard_rear_min": 1, "building_coverage_max_pct": 40, "impervious_max_pct": 60, "landscaped_min_pct": 20, "building_height_max": 11, "hirb_angle": 45, "hirb_start_height": 3,
            "ols_ground_floor_min_area": 20, "ols_ground_floor_min_dimension": 4, "dwelling_min_net_floor_area_studio": 30, "dwelling_min_net_floor_area_1br_plus": 45, "min_net_site_area_vacant_site_parent_lt_1ha": 300}
    base.update(over); return {k: {"parameter": k, "v": v, "unit": "u", "section_ref": "TEST", "owner_verified": False, "last_verified": None} for k, v in base.items() if v is not None}

PARCEL = box(0, 0, 20, 50); FRONT = (10, 0)        # front edge is y=0 (address point on it); rear y=50; sides x=0 and x=20
def unit(x, y, w=6, d=9, h=7, wall=None, ols=None, gfa=90, i=1):
    return {"id": f"u{i}", "footprint": box(x, y, x + w, y + d), "height_m": h, "wall_height_m": wall, "gfa_m2": gfa, "bedrooms": 2, "ols": ols}
def ev(units, access=None, R=None): return {c["id"]: c for c in D.evaluate(PARCEL, "x", {"units": units, "access": access}, FRONT, R or rules())["checks"]}

def test_boundaries_front_rear_side():
    B = D.classify_boundaries(PARCEL, FRONT)
    assert [list(e.coords) for e in B["front"]] == [[(0.0, 0.0), (20.0, 0.0)]] and [list(e.coords) for e in B["rear"]] == [[(20.0, 50.0), (0.0, 50.0)]] and len(B["side"]) == 2

def test_yards_hand_calculated():
    c = ev([unit(5, 5)]); assert (c["yard_front"]["status"], c["yard_front"]["measured"]) == ("PASS", 5.0) and c["yard_side"]["measured"] == 5.0 and c["yard_rear"]["measured"] == 36.0
    assert ev([unit(5, 1)])["yard_front"]["status"] == "FAIL" and ev([unit(0.5, 10)])["yard_side"]["status"] == "FAIL"
    assert ev([unit(5, 3)])["yard_front"]["status"] == "PASS"                       # exactly the minimum passes

def test_coverage_impervious_landscaped():
    c = ev([unit(2, 5, 15, 30)]); assert c["building_coverage"]["measured"] == 45.0 and c["building_coverage"]["status"] == "FAIL"
    assert ev([unit(2, 5, 10, 35)])["building_coverage"]["status"] == "PASS"          # 35%
    assert ev([unit(2, 5, 15, 43)])["impervious"]["status"] == "FAIL" and ev([unit(2, 5, 10, 35)])["impervious"]["status"] == "NEEDS_PROFESSIONAL"    # a pass is never stated for a lower bound
    assert ev([unit(0.5, 4, 19, 44)])["landscaped"]["status"] == "FAIL" and ev([unit(2, 5, 10, 10)])["landscaped"]["status"] == "NEEDS_PROFESSIONAL"

def test_height_and_hirb():
    assert ev([unit(5, 5, h=12)])["height"]["status"] == "FAIL" and ev([unit(5, 5, h=11)])["height"]["status"] == "PASS"
    assert ev([unit(1, 10, wall=5, h=8)])["hirb"]["status"] == "FAIL"                  # d=1: allowed 3+1=4 < wall 5
    assert ev([unit(3, 10, wall=5, h=8)])["hirb"]["status"] == "PASS"                  # d=3: wall 6>=5; ridge at d+3=6: 9>=8
    assert ev([unit(2, 10, wall=5, h=8)])["hirb"]["status"] == "PASS"                  # d=2: wall allowed 5 (equal), ridge 8 (equal): passes at the limit
    assert ev([unit(2, 10, wall=5, h=8.1)])["hirb"]["status"] == "FAIL"
    assert ev([unit(5, 10, h=7)])["hirb"]["measured"] is not None

def test_outdoor_living_and_dwelling_size():
    assert ev([unit(5, 5, ols=box(0, 0, 4, 4))])["outdoor_living"]["status"] == "FAIL"        # 16 m2
    assert ev([unit(5, 5, ols=box(0, 0, 5, 4.1))])["outdoor_living"]["status"] == "PASS"
    assert ev([unit(5, 5, ols=box(0, 0, 10, 2))])["outdoor_living"]["status"] == "FAIL"       # 20 m2 but 2 m wide
    assert ev([unit(5, 5, gfa=40)])["dwelling_size"]["status"] == "FAIL" and ev([unit(5, 5, gfa=45)])["dwelling_size"]["status"] == "PASS"

def test_rule_not_loaded_is_unknown_never_pass_and_badge_logic():
    c = ev([unit(5, 5)], R=rules(hirb_angle=None, yard_front_min=None)); assert c["hirb"]["status"] == "UNKNOWN" and c["yard_front"]["status"] == "UNKNOWN" and "never counted as a pass" in c["hirb"]["note"]
    s = D.summarize(list(ev([unit(5, 5, ols=box(0, 0, 5, 4.1))]).values())); assert s["badge"] == "incomplete" and s["counts"]["UNKNOWN"] >= 1                 # vehicle access standard is not loaded: never 'rules-checked'
    assert D.summarize(list(ev([unit(5, 1)]).values()))["badge"] == "does_not_comply"
    assert D.summarize([{"status": "PASS", "rule": "A", "owner_verified": True}])["badge"] == "rules_checked"
    assert D.summarize([{"status": "PASS", "rule": "A", "owner_verified": False}])["unconfirmed_rule_values"] == ["A"]

def test_layout_engine_hand_checked_yield_and_binding():
    u = {"width_m": 6, "depth_m": 9, "height_m": 7, "wall_height_m": 4, "gfa_m2": 90, "bedrooms": 2}
    env = L.envelope(PARCEL, rules(), D.classify_boundaries(PARCEL, FRONT)); assert env.area == pytest.approx(18 * 46)           # yards: front 3, rear 1, sides 1
    r = L.best(PARCEL, "x", u, None, FRONT, rules()); top = r["compliant"][0]
    assert top["unit_count"] == 7 and top["summary"]["counts"]["FAIL"] == 0 and len(r["candidates"]) >= 20       # 9 cells of 6x13 fit; 8 units = 43.2% and 9 = 48.6% breach 40% coverage; 7 = 37.8%
    assert L.binding_constraint(r)["binding"] == ["building_coverage"]
    assert all(c["summary"]["counts"]["FAIL"] > 0 for c in r["near_misses"])
    assert L.fit_units(PARCEL, "x", u, None, FRONT, rules())["max_compliant_units"] == 7
    big = L.fit_units(PARCEL, "x", u, None, FRONT, rules(building_coverage_max_pct=60)); assert big["max_compliant_units"] == 9 and big["binding"]["binding"] == ["buildable_envelope"]

def test_driveway_reduces_yield_and_serves_units():
    u = {"width_m": 6, "depth_m": 9, "height_m": 7, "wall_height_m": 4, "gfa_m2": 90, "bedrooms": 2}
    r = L.best(PARCEL, "x", u, 3.5, FRONT, rules(building_coverage_max_pct=60)); top = r["compliant"][0]
    assert top["meta"]["access"] != "none" and top["unit_count"] <= 9 and top["access"] is not None and all(not top["access"].intersects(x["footprint"]) for x in top["units"])

def test_subdivision_area_rule():
    s = L.subdivision_yield(box(0, 0, 20, 50), "x", rules()); assert s["max_lots_by_area"] == 3 and s["lots_in_layout"] == 3 and all(a >= 300 for a in s["lot_areas_m2"]) and "frontage" in s["note"]
    assert L.subdivision_yield(box(0, 0, 20, 50), "x", rules(min_net_site_area_vacant_site_parent_lt_1ha=None))["status"] == "UNKNOWN"
    assert L.subdivision_yield(box(0, 0, 200, 100), "x", rules())["status"] == "NEEDS_PROFESSIONAL"

G = {"price_per_unit": 900000, "build_cost_per_m2": 3000, "site_works_allowance": 100000, "contingency_pct": 10, "land_cost": 1500000, "consent_professional_fees": 150000, "development_contributions": 100000, "holding_months": 18, "interest_rate_pct": 8, "selling_costs_pct": 3}
def test_dev_financials_hand_calculated():
    f = devfin.feasibility(4, 100, G); c = f["costs"]
    assert f["revenue"] == 3_600_000 and c["build"] == pytest.approx(1_320_000) and c["holding"] == pytest.approx(180_000 + 85_200) and c["selling"] == pytest.approx(108_000)
    assert f["total_cost"] == pytest.approx(3_543_200) and f["profit"] == pytest.approx(56_800) and f["margin_on_cost_pct"] == pytest.approx(56_800 / 3_543_200 * 100)
    assert f["peak_funding_approx"] == pytest.approx(3_435_200) and f["break_even_price_per_unit"] == pytest.approx((3_543_200 - 108_000) / (4 * 0.97))
    assert devfin.feasibility(4, 100, {**G, "build_cost_per_m2": devfin.break_even_build_cost(4, 100, G)})["profit"] == pytest.approx(0, abs=1)
    s = devfin.sensitivity(4, 100, G)["profit"]; assert s["price_minus_10pct"] < s["base"] < s["price_plus_10pct"] and s["delay_plus_3_months"] < s["base"] and s["interest_plus_2pts"] < s["interest_minus_2pts"]

def test_dev_financials_need_input_never_numbers():
    f = devfin.feasibility(4, 100, {**G, "land_cost": None, "price_per_unit": None}); assert f["status"] == "needs_input" and "Land cost" in f["needs_input"] and "profit" not in f
    assert devfin.feasibility(0, 100, G)["status"] == "needs_input" and devfin.sensitivity(4, 100, {}) == {"status": "needs_input"}

def test_real_parcel_end_to_end():
    from backend.app import devscenarios as S
    r = S.run(4756180, {"typology": "houses", "unit": {"width_m": 7, "depth_m": 10, "height_m": 7.5, "wall_height_m": 5.5, "gfa_m2": 120, "bedrooms": 3}, "access_width_m": 3.5, "finance": {}})
    assert r["status"] == "ok" and r["zone"].startswith("Residential") and r["scenarios"] and r["scenarios"][0]["summary"]["counts"]["FAIL"] == 0 and r["financials"]["status"] == "needs_input"
    assert "Concept sketch, not a design" in r["scenarios"][0]["sketch_svg"] and r["badge"] == "incomplete" and r["scenarios"][0]["summary"]["unconfirmed_rule_values"]
    assert S.get_run(r["run_id"])["run_id"] == r["run_id"]
    r2 = S.run(4756180, {"typology": "houses", "unit": {"width_m": 7}, "finance": {}}); assert r2["status"] == "needs_input" and "unit.depth_m" in r2["needs_input"]
    assert S.get_run(r["run_id"])["superseded"] is True and S.latest(4756180)["run_id"] == r2["run_id"]
    with __import__("backend.app.db", fromlist=["conn"]).conn() as c: c.execute("DELETE FROM core.user_dev_run WHERE parcel_id=4756180"); c.commit()
