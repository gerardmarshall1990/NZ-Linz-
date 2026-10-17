"""Economics and Offer Builder tests. Worked example from MASTER_SPEC Part 6.4 (must pass exactly), operating-model maths checked by hand, needs-input blocking, flags, ranking."""
import math
import pytest
from backend.app import economics as E

# ---- Part 6.4 worked example: R0 = 1000/wk, N = 5000/wk stabilised, s = 50%, C = 50,000
def example(**over):
    inp = {"asking_rent": 1000, "N": 5000, "retrofit": 50000, "stabilised_occupancy": 1.0, "pre_opening_costs": 0, "working_capital": 0,
           "timeline": {"consent_weeks": 12, "works_weeks": 8, "audit_weeks": 4}, "funding": "i_fund", "terms": {"s": 0.5}, "confidence": {"N": "ESTIMATED", "C": "ESTIMATED"}}
    inp.update(over); return inp

def test_worked_example_exact():
    r = E.run_offer(example()); jv = r["modes"]["jv"]
    assert jv["owner"]["weekly_at_stabilisation"] == 2500                       # take = 2,500/wk
    assert jv["owner"]["multiple_of_current"] == 2.5                            # = 2.5 x R0
    assert jv["operator"]["stabilised_weekly_net_after_owner"] == 2500          # operator net after share
    assert jv["operator"]["payback_weeks_stabilised_only"] == 20                # simple payback on C = 20 weeks, at stabilisation only
    assert "excludes the conversion period" in jv["operator"]["excludes_note_for_simple_payback"]
    assert jv["owner"]["cases"]["occ_60"] == 1500                               # owner's take if occupancy is 60%
    assert jv["owner"]["cases"]["n_lower"] == 1750                              # and if N is 30% lower
    assert "Lawyer review required" in r["banner"] and "guarantee" not in str(r).lower() and "assured" not in str(r).lower()

def test_worked_example_full_timeline_beside_it():
    # a 1,000/wk payment to the owner over the 24-week target timeline adds 24,000 to cash required
    r = E.run_offer(example(terms={"s": 0.5, "conversion_payment_per_week": 1000})); op = r["modes"]["jv"]["operator"]
    assert op["payback_weeks_stabilised_only"] == 20                            # unchanged: it excludes the conversion period
    assert op["cash_components"]["owner_payments_during_conversion"] == 24000 and op["cash_components"]["retrofit"] == 50000
    assert op["cash_required"] == 74000
    assert op["payback_weeks_full_timeline_from_lease_start"] == 24 + math.ceil(74000 / 2500)   # 54 weeks from lease start
    assert op["peak_cash"] == pytest.approx(74000)
    own = r["modes"]["jv"]["owner"]
    assert own["weekly_during_conversion"] == 1000 and own["cumulative_12m"] == 24000 + 2500 * 28

def test_jv_without_minimum_payment_flags_owner_downside():
    r = E.run_offer(example()); m = r["modes"]["jv"]
    assert any(f["level"] == "amber" and "no minimum payment" in f["text"] for f in m["flags"])
    assert m["owner"]["weekly_during_conversion"] == 0

# ---- operating model checked by hand
P = {**{k: None for k in E.OPEX_KEYS}, "fee_per_bed_per_week": 1600, "food_per_occupied_bed_per_week": 200, "staff_wage_per_week": 800, "staff_positions_per_8_beds": 4,
     "roster_coverage_multiplier": 1.5, "clinical_lead_cost_per_week": 2000, "manager_cost_per_week": 2500, "cook_cleaner_laundry_per_week": 1500, "utilities_per_week": 500,
     "insurance_per_year": 26000, "supplies_per_occupied_bed_per_week": 40, "repairs_maintenance_per_year": 26000, "compliance_and_certification_per_year": 13000, "other_opex_per_week": 300,
     "stabilised_occupancy": 0.9, "retrofit_funding_mode": "i_fund", "lease_term_years": 10, "cost_of_capital_pct": 8, "target_profit_per_year": 260000, "minimum_acceptable_profit_per_year": 130000}

def test_operating_hand_calculation():
    o = E.operating(40, 0.9, P)                       # 40 beds, 36 occupied
    assert o["revenue"] == pytest.approx(36 * 1600) and o["food"] == pytest.approx(36 * 200) and o["supplies"] == pytest.approx(36 * 40)
    assert o["staffing"] == pytest.approx(40 / 8 * 4 * 800 * 1.5)                 # 24,000/wk; fixed to the roster
    assert o["fixed_other"] == pytest.approx(2000 + 2500 + 1500 + 500 + 300 + (26000 + 26000 + 13000) / 52)
    assert o["net"] == pytest.approx(57600 - 7200 - 1440 - 24000 - o["fixed_other"])
    assert E.operating(40, 0.5, P)["staffing"] == o["staffing"]                   # staffing does not fall with occupancy

def test_unset_input_blocks_outputs():
    p = dict(P, utilities_per_week=None)
    assert E.operating(40, 0.9, p)["net"] is None and "utilities_per_week" in E.operating(40, 0.9, p)["needs_input"]
    f = E.feasibility(40, p, 500000, "ESTIMATED"); assert f["walk_away_rent_per_week"] is None and "utilities_per_week" in f["needs_input"]
    f2 = E.feasibility(40, dict(P, minimum_acceptable_profit_per_year=None), 500000, "ESTIMATED")
    assert f2["walk_away_rent_per_week"] is None and "minimum_acceptable_profit_per_year" in f2["needs_input"] and f2["rent_headroom_per_week"] is not None
    assert E.feasibility(40, P, None)["walk_away_rent_per_week"] is None          # no retrofit cost: needs input, never zero

def test_walk_away_and_headroom_hand_calculation():
    f = E.feasibility(40, P, 600000, "CONFIRMED"); N = f["stabilised"]["net"]
    r = 0.08 / 12; n = 120; monthly = 600000 * r / (1 - (1 + r) ** -n); weekly = monthly * 12 / 52
    assert f["retrofit_charge"]["weekly"] == pytest.approx(weekly)
    assert f["walk_away_rent_per_week"] == pytest.approx(N - weekly - 130000 / 52) and f["rent_headroom_per_week"] == pytest.approx(N - weekly - 260000 / 52)
    assert f["walk_away_rent_per_week"] > f["rent_headroom_per_week"]              # minimum profit < target profit
    assert f["banner"] is None and E.feasibility(40, P, 600000, "ESTIMATED")["banner"] == "Screening only: bedrooms/plans not confirmed"

def test_owner_funds_mode_uses_required_yield():
    p = dict(P, retrofit_funding_mode="owner_funds_via_rent", owner_required_yield_on_capex_pct=10)
    assert E.retrofit_charge_weekly(600000, p)["weekly"] == pytest.approx(600000 * 0.10 / 52)
    assert "owner_required_yield_on_capex_pct" in E.retrofit_charge_weekly(600000, dict(p, owner_required_yield_on_capex_pct=None))["needs_input"]

def test_break_even_occupancy_numerically_matches_closed_form():
    be = E.feasibility(40, P, 0)["break_even_occupancy"]["profit_zero"]
    o = E.operating(40, be, P); assert o["net"] == pytest.approx(0, abs=1e-6)
    # closed form: occupied beds x (fee - food - supplies) = staffing + fixed
    unit = 1600 - 200 - 40; fixed = 24000 + E.operating(40, 1, P)["fixed_other"]
    assert be == pytest.approx(fixed / (40 * unit), rel=1e-9)
    assert E.solve_occupancy(lambda o: o * 10, 100.0) is None                      # unreachable at 100%: None, not a number

# ---- Offer Builder modes
def full(**over):
    inp = {"asking_rent": 1000, "N": {"low": 4000, "base": 5000, "high": 6000}, "retrofit": {"low": 40000, "base": 50000, "high": 70000}, "stabilised_occupancy": 0.9,
           "fill_ramp_by_month": [0.3, 0.6, 0.8], "pre_opening_costs": 20000, "working_capital": 15000, "timeline": {"consent_weeks": 4, "works_weeks": 8, "audit_weeks": 4},
           "walk_away_rent": 2200, "cash_limit": 400000, "terms": {"multiple": 3.0, "s": 0.4, "floor": 800, "s_h": 0.3, "threshold": 1000, "conversion_payment_per_week": 500},
           "confidence": {"N": "DOCUMENTED", "C": "ESTIMATED"}}
    inp.update(over); return inp

def test_fixed_rent_never_above_walk_away():
    r = E.run_offer(full()); m = r["modes"]["fixed"]
    assert m["owner"]["weekly_at_stabilisation"] == 2200 and m["capped_at_walk_away"] is True and m["multiple_achieved"] == 2.2
    for mult in (0.5, 1.0, 2.0, 2.2, 2.5, 10.0):
        mm = E.run_offer(full(terms={"multiple": mult}))["modes"]["fixed"]
        assert mm["owner"]["weekly_at_stabilisation"] <= 2200 + 1e-9
    assert E.run_offer(full(walk_away_rent=None))["modes"]["fixed"]["blocked"] is True      # no walk-away rent: no fixed offer

def test_asking_rent_above_walk_away_is_not_viable():
    m = E.run_offer(full(asking_rent=2500, terms={"multiple": 1.0}))["modes"]["fixed"]
    assert any(f["level"] == "red" and "not viable" in f["text"] for f in m["flags"])

def test_hybrid_floor_through_conversion_and_share_above_threshold():
    m = E.run_offer(full())["modes"]["hybrid"]
    assert m["owner"]["weekly_during_conversion"] == 800
    N90 = 5000; assert m["owner"]["weekly_at_stabilisation"] == pytest.approx(800 + 0.3 * (N90 - 1000))
    assert m["owner"]["cases"]["occ_60"] == pytest.approx(800 + 0.3 * (5000 * 0.6 / 0.9 - 1000))
    assert m["operator"]["cash_components"]["owner_payments_during_conversion"] == 800 * 16

def test_cash_limit_flag_and_allowance_banner_and_confidence():
    r = E.run_offer(full(cash_limit=10000, allowance_pct=45))
    assert any(f["level"] == "red" and "cash limit" in f["text"] for f in r["modes"]["jv"]["flags"])
    assert any("allowances" in f["text"] and f["level"] == "red" for f in r["flags"])
    assert r["confidence"] == "ESTIMATED"                                            # lowest of N (DOCUMENTED) and C (ESTIMATED)
    assert E.run_offer(full(allowance_pct=20))["flags"] == []

def test_needs_input_returns_no_numbers():
    r = E.run_offer(full(pre_opening_costs=None)); assert r["modes"] == {} and "pre_opening_costs" in r["needs_input"]

def test_ranking_prefers_fewer_red_flags():
    r = E.run_offer(full(cash_limit=1))                                              # every mode breaches the cash limit: ties broken by operator net
    assert set(r["ranking"]) == {"fixed", "jv", "hybrid"}
    nets = [r["modes"][k]["operator"]["stabilised_weekly_net_after_owner"] for k in r["ranking"]]; assert nets == sorted(nets, reverse=True)

def test_breakeven_for_each_party_and_ramp_deficits():
    assert "needs_input" in E.run_offer(full())["modes"]["jv"]["break_even_occupancy"]        # proportional N cannot give a break-even
    m = E.run_offer(full(N_fn=lambda o: E.operating(40, o, P)["net"], N={"low": 1, "base": E.operating(40, 0.9, P)["net"], "high": 2}))["modes"]["jv"]
    assert 0 < m["break_even_occupancy"]["operator_zero_profit"] <= 1
    assert m["operator"]["cash_components"]["ramp_deficits"] >= 0 and m["operator"]["peak_cash"] > 0

def test_no_hazard_inputs_anywhere():
    import inspect; src = inspect.getsource(E).lower()
    assert "hazard" not in src and "flood" not in src
