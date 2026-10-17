#!/usr/bin/env python3
"""Demo of the Part 6.4 worked example through the real Offer Builder code: asking rent 1,000/wk, net 5,000/wk at stabilisation, profit share 50%, retrofit 50,000.
Prints the stabilised-only view and the full-timeline view side by side, then the downside cases. Raw output is saved to docs/demo/worked_example.json."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app import economics as E

def run(conv_payment):
    return E.run_offer({"asking_rent": 1000, "N": 5000, "retrofit": 50000, "stabilised_occupancy": 1.0, "pre_opening_costs": 0, "working_capital": 0,
                        "timeline": {"consent_weeks": 4, "works_weeks": 8, "audit_weeks": 4}, "funding": "i_fund", "horizon_weeks": 104,
                        "terms": {"s": 0.5, "conversion_payment_per_week": conv_payment}, "confidence": {"N": "ESTIMATED", "C": "ESTIMATED"}})
a, b = run(0), run(1000)
m0, m1 = a["modes"]["jv"], b["modes"]["jv"]; m = lambda x: f"${x:,.0f}"
print("PART 6.4 WORKED EXAMPLE  (inputs: asking rent R0 = $1,000/wk; stabilised net N = $5,000/wk; owner share s = 50%; retrofit C = $50,000; I fund the retrofit)")
print("Timeline used (spec target): consent 4 wk, works 8 wk, audit and sign-off 4 wk = 16 weeks before the home opens. Occupancy assumed 100% from opening (no fill ramp, no pre-opening cost, no working capital in this example).\n")
print("A. STABILISED ONLY (what the spec's simple numbers describe)")
print(f"   Owner take at stabilisation ......... {m(m0['owner']['weekly_at_stabilisation'])}/wk = {m0['owner']['multiple_of_current']:.1f} x R0")
print(f"   Operator net after owner's share .... {m(m0['operator']['stabilised_weekly_net_after_owner'])}/wk")
print(f"   Simple payback on C ................. {m0['operator']['payback_weeks_stabilised_only']:.0f} weeks  (at stabilisation only)")
print(f"   NOTE: {m0['operator']['excludes_note_for_simple_payback']}\n")
print("B. FULL TIMELINE (a $1,000/wk minimum payment to the owner through the 16 conversion weeks; pure share afterwards)")
o, p = m1["owner"], m1["operator"]
print(f"   Owner income during conversion ...... {m(o['weekly_during_conversion'])}/wk for 16 weeks = {m(16*o['weekly_during_conversion'])}")
print(f"   Cash required ....................... {m(p['cash_required'])}  = retrofit {m(p['cash_components']['retrofit'])} + owner payments during conversion {m(p['cash_components']['owner_payments_during_conversion'])} + pre-opening {m(p['cash_components']['pre_opening'])} + ramp deficits {m(p['cash_components']['ramp_deficits'])} + working capital {m(p['cash_components']['working_capital'])}")
print(f"   Peak cash ........................... {m(p['peak_cash'])}")
print(f"   Simple payback (unchanged) .......... {p['payback_weeks_stabilised_only']:.0f} weeks")
print(f"   Full-timeline payback ............... {p['payback_weeks_full_timeline_from_lease_start']} weeks from lease start  (16 conversion weeks + {p['payback_weeks_full_timeline_from_lease_start']-16} weeks of operating at $2,500/wk net)")
print(f"   Owner cumulative income 12 months ... {m(o['cumulative_12m'])}  vs leaving the property as it is {m(o['current_income_used']*52)}  (difference {m(o['vs_leaving_as_is_12m'])})")
print(f"   Owner cumulative income 24 months ... {m(o['cumulative_24m'])}  vs {m(o['current_income_used']*104)}  (difference {m(o['vs_leaving_as_is_24m'])})")
print(f"   Cash curve by month (operator, $) ... {p['cash_curve_by_month'][:14]}\n")
print("C. DOWNSIDE CASES (owner's weekly take; N is the weekly net at stabilisation)")
c = m0["owner"]["cases"]
print(f"   Occupancy 100% ...... {m(c['occ_100'])}/wk   ({c['occ_100']/1000:.2f} x R0)")
print(f"   Occupancy  80% ...... {m(c['occ_80'])}/wk   ({c['occ_80']/1000:.2f} x R0)")
print(f"   Occupancy  60% ...... {m(c['occ_60'])}/wk   ({c['occ_60']/1000:.2f} x R0)")
print(f"   N 30% lower ......... {m(c['n_lower'])}/wk   ({c['n_lower']/1000:.2f} x R0)   (N = $3,500)")
print(f"   {a['assumptions'][0]}")
print(f"\nFLAGS (pure share, no minimum payment): " + "; ".join(f["text"] for f in m0["flags"]))
print(f"FLAGS (with the $1,000/wk minimum payment): " + ("; ".join(f["text"] for f in m1["flags"]) or "none"))
print(f"\n{b['banner']}")
Path("docs/demo/worked_example.json").write_text(json.dumps({"stabilised_only": a, "full_timeline": b}, indent=1, default=str))
