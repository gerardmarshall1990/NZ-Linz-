#!/usr/bin/env python3
"""Demo: import 3 SAMPLE listings (real Auckland addresses, invented rent and bedrooms: NOT real listings), show verdicts with your saved inputs (blank today) and with clearly-labelled
ILLUSTRATIVE demo inputs, show an Offer Builder result, take phone-width screenshots, then remove everything the demo created. Usage: demo_listings.py <out_dir> [path/to/your.csv]"""
import json, os, socket, subprocess, sys, time
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
csv_path = sys.argv[2] if len(sys.argv) > 2 else None
SAMPLE = """source_id,address,suburb,rent_per_week,bedrooms,bathrooms,listing_type,url
SAMPLE-1,80 Hinemoa Street,Birkenhead,4800,30,12,rent,
SAMPLE-2,282 Lincoln Road,Henderson,3900,24,10,rent,
SAMPLE-3,14 Shipherds Avenue,Epsom,1950,7,3,rent,
"""
DEMO = {"clinical_lead_cost_per_week": 2000, "manager_cost_per_week": 2500, "cook_cleaner_laundry_per_week": 1500, "utilities_per_week": 500, "insurance_per_year": 26000,
        "supplies_per_occupied_bed_per_week": 40, "repairs_maintenance_per_year": 26000, "compliance_and_certification_per_year": 13000, "other_opex_per_week": 300, "roster_coverage_multiplier": 1.5,
        "stabilised_occupancy": 0.9, "fill_ramp_by_month": [0.3, 0.6, 0.8], "pre_opening_costs": 20000, "working_capital": 15000, "lease_term_years": 10, "cost_of_capital_pct": 8,
        "target_profit_per_year": 260000, "minimum_acceptable_profit_per_year": 130000, "retrofit_cost_per_bed_screening": 10000}
import psycopg
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
DSN = f"host=localhost dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
with psycopg.connect(DSN, autocommit=True) as c0:       # remember what you had saved so the demo leaves it exactly as it was
    SAVED = c0.execute("SELECT key, value FROM core.user_setting WHERE key LIKE 'assumption:%' OR key LIKE 'flag:assumption:%'").fetchall()
    HIST0 = c0.execute("SELECT coalesce(max(id), 0) FROM core.user_setting_history").fetchone()[0]
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
PW = "demo-password-0123456789"; env = {**os.environ, "APP_PASSWORD": PW}
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
base = f"http://127.0.0.1:{port}"; cl = httpx.Client(base_url=base, timeout=60)
try:
    for _ in range(60):
        try:
            if httpx.get(base + "/api/health", timeout=2).status_code == 200: break
        except Exception: time.sleep(0.5)
    assert cl.post("/login", json={"password": PW}).status_code == 200
    csv = Path(csv_path).read_text() if csv_path else SAMPLE
    r = cl.post("/api/listings/import", files={"file": ("l.csv", csv.encode())}, data={"source": "csv_manual", "dry_run": "false"}).json()
    print(f"IMPORT ({'your CSV' if csv_path else 'SAMPLE listings: real addresses, invented rent and bedrooms'}): new {r['new']}, matched high {r['matched']['high']} medium {r['matched']['medium']} low {r['matched']['low']} none {r['matched']['none']}")
    print("Source coverage:", r["coverage"], "\n")
    def show(title, assumptions=None):
        res = cl.post("/api/listings/search", json={"filters": {"source": "csv_manual"}, "assumptions": assumptions}).json(); print(title); print("  counts:", res["verdict_counts"])
        for o in res["listings"]:
            l = o["listing"]; e = o.get("economics") or {}; mb = (o.get("minimum_beds") or {}).get("minimum_beds")
            print(f"  [{o['verdict']:5}] {l['raw_address']}: {l['bedrooms']} beds, asking ${l['rent_per_week']:,.0f}/wk, confidence {o['confidence']}"
                  + ((f", min beds {mb}, " + (f"walk-away rent ${e['offer_ceiling']:,.0f}/wk ({e['rent_multiple_possible']:.2f}x asking)" if e.get('rent_multiple_possible') else "NO walk-away rent: " + (e.get('ceiling_note') or "")) ) if e.get('offer_ceiling') is not None else ""))
            for x in o["reasons"][:3]: print("         -", x[:150])
            if o.get("needs_input"): print("         needs input:", ", ".join(o["needs_input"][:6]), "...")
        return res
    show("VERDICTS WITH YOUR SAVED INPUTS (nothing entered yet, so nothing is guessed):")
    print("\nNow the same listings with ILLUSTRATIVE DEMO INPUTS (my placeholders to show how verdicts look; NOT your numbers, NOT saved to your account afterwards):")
    # save the demo inputs only for the screenshots, then remove them again
    if not os.environ.get("DEMO_REAL"): cl.put("/api/settings/assumptions", json={"values": DEMO, "flags": {k: "estimate" for k in DEMO}, "notes": {k: "DEMO placeholder" for k in DEMO}})
    res = show("VERDICTS WITH DEMO INPUTS:")
    ids = {o["listing"]["raw_address"]: o["listing"]["id"] for o in res["listings"]}
    terms = {"multiple": 1.5, "s": 0.4, "floor": 800, "s_h": 0.3, "threshold": 1500, "conversion_payment_per_week": 500}
    target = next((a for a in ids if "Lincoln" in a), next(iter(ids)))
    off = cl.post(f"/api/listings/{ids[target]}/offer", json={"terms": terms}).json()
    print(f"\nOFFER BUILDER for {target} (screening: {off['beds']} listed bedrooms; retrofit = beds x $10,000 demo screening cost = ${off['range']['retrofit']['base']:,.0f}, all an allowance):")
    print(f"  walk-away rent ${off['walk_away_rent_per_week']:,.0f}/wk; ranking by fewest red flags then operator net: {off['ranking']}")
    for k, m in off["modes"].items():
        if m.get("blocked"): print(f"  {k}: blocked ({m['needs_input']})"); continue
        o_, p_ = m["owner"], m["operator"]
        print(f"  {k:6} owner ${o_['weekly_at_stabilisation']:,.0f}/wk ({o_['multiple_of_current']:.2f}x asking) | during conversion ${o_['weekly_during_conversion']:,.0f}/wk | at 60% occ ${o_['cases']['occ_60']:,.0f} | N-30% ${o_['cases']['n_lower']:,.0f}"
              f" || you: net after owner ${p_['stabilised_weekly_net_after_owner']:,.0f}/wk, cash required ${p_['cash_required']:,.0f}, peak ${p_['peak_cash']:,.0f}, payback {(str(round(p_['payback_weeks_stabilised_only'])) + ' wk') if p_['payback_weeks_stabilised_only'] else 'never'} (stabilised only) / {(str(p_['payback_weeks_full_timeline_from_lease_start']) + ' wk') if p_['payback_weeks_full_timeline_from_lease_start'] else 'not within 3 years'} (full timeline)")
        for f in m["flags"]:
            if f["level"] != "info": print(f"         [{f['level']}] {f['text']}")
    for f in off["flags"]: print(f"  [{f['level']}] {f['text']}")
    print("  " + off["banner"])
    shot = subprocess.run(["node", str(ROOT / "tests/ui/demo_shots.js"), base, str(out), target.split(",")[0]], capture_output=True, text=True, env={**os.environ, "UI_PASSWORD": PW})
    print("\nscreenshots:", shot.stdout.strip() or shot.stderr.strip()[:300])
finally:
    srv.terminate(); srv.wait(timeout=10)
    with psycopg.connect(DSN, autocommit=True) as c:
        if not csv_path:
            c.execute("DELETE FROM core.rh_scenario WHERE parcel_id IN (SELECT parcel_id FROM core.user_listing WHERE source_id LIKE 'SAMPLE-%')")
            c.execute("DELETE FROM core.rh_property p WHERE p.created_by = 'listing' AND p.parcel_id IN (SELECT parcel_id FROM core.user_listing WHERE source_id LIKE 'SAMPLE-%') AND NOT EXISTS (SELECT 1 FROM core.rh_property_fact f WHERE f.parcel_id = p.parcel_id)")
            c.execute("DELETE FROM core.user_listing WHERE source_id LIKE 'SAMPLE-%'")
        c.execute("DELETE FROM core.user_setting WHERE key LIKE 'assumption:%' OR key LIKE 'flag:assumption:%'")
        for k, v in SAVED: c.execute("INSERT INTO core.user_setting (key, value) VALUES (%s, %s::jsonb)", (k, json.dumps(v)))
        c.execute("DELETE FROM core.user_setting_history WHERE id > %s", (HIST0,))
    print("\n(demo data removed: sample listings, demo inputs and their history; your saved inputs restored exactly: %d)" % len(SAVED))
