#!/usr/bin/env python3
"""`make validate`: regenerate docs/VALIDATION.md (MASTER_SPEC Part 5 section 4). Each check is PASS, FAIL or PENDING (needs data only the owner has). The go/no-go is NO-GO unless every check passes. This script never flips a flag."""
import os, re, subprocess, sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT); sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_PASSWORD", "validate-run-0123456789")
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
from backend.app.db import conn
from backend.app import flags, validation

def pytest_run(*files):
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *files], capture_output=True, text=True)
    m = re.search(r"(\d+) passed", p.stdout); f = re.search(r"(\d+) failed", p.stdout)
    return p.returncode == 0, int(m.group(1)) if m else 0, int(f.group(1)) if f else 0, p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:]

R = []     # (number, title, status, [lines])
def add(n, title, status, lines): R.append((n, title, status, lines))

with conn() as c:
    # 1 rules spot-check
    zones = ["Residential - Single House Zone", "Residential - Mixed Housing Suburban Zone", "Residential - Mixed Housing Urban Zone", "Residential - Terrace Housing and Apartment Building Zone"]
    rows = {z: c.execute("SELECT count(*) FILTER (WHERE owner_verified) AS v, count(*) AS n FROM analytics.rules WHERE zone = %s", (z,)).fetchone() for z in zones}
    ok = all(r["v"] >= 15 for r in rows.values())
    add(1, "Rules: owner spot-check of at least 15 key standards in each of the four main residential zones", "PASS" if ok else "PENDING",
        [f"- {z}: {r['v']} confirmed by you of {r['n']} extracted rules (need 15)" for z, r in rows.items()] + ["Nothing is marked verified until you confirm it. Open docs/key_standards_check.html and reply with your checks."])
    # 5 data coverage
    L = c.execute("SELECT count(*) AS n, count(*) FILTER (WHERE match_confidence IN ('high','medium')) AS m FROM core.user_listing").fetchone()
    tiers = c.execute("SELECT confidence, count(DISTINCT parcel_id) AS n FROM core.rh_property_fact GROUP BY confidence").fetchall()
    al = c.execute("SELECT (output->>'allowance_share_pct')::float AS a FROM core.rh_scenario WHERE kind='retrofit' ORDER BY id DESC LIMIT 20").fetchall()
    cov = [f"- Listings matched to a LINZ address with high/medium confidence: {L['m']} of {L['n']}" + ("" if L["n"] else " (no listings imported yet)"),
           "- Properties with any fact, by confidence tier: " + (", ".join(f"{t['confidence']} {t['n']}" for t in tiers) or "none yet"),
           "- Allowance share of retrofit cost in recent runs: " + (", ".join(f"{a['a']:.0f}%" for a in al if a['a'] is not None) or "no retrofit total has been computed (rates blank)"),
           "- Licensed property feed match rate: not measurable (no feed yet)"]
    add(5, "Data coverage", "PENDING" if not L["n"] or not tiers else "PASS", cov)
    # 4 calibration on real properties
    cfg = validation.get_config(); tol = cfg["tolerance_pct"]; props = cfg["properties"]
    q = c.execute("SELECT line, count(*) AS n FROM core.rh_quote WHERE NOT voided GROUP BY line ORDER BY line").fetchall()
    lines4 = [f"- Tolerance (your input): {tol if tol is not None else 'not set'}", f"- Properties you chose: {props or 'none chosen (pick 3 to 5)'}", "- Quotes on file by line: " + (", ".join(f"{r['line']} {r['n']}" for r in q) or "none")]
    st4 = "PENDING"
    if tol is not None and 3 <= len(props) <= 5 and q:
        from backend.app import retrofit_calibration as rc
        bad = []
        for r in q:
            s = rc.summary_for(r["line"])
            for qq in s["quotes"]:
                if qq["variance_vs_model_pct"] is not None and abs(qq["variance_vs_model_pct"]) > tol: bad.append(f"{r['line']} quote {qq['id']}: {qq['variance_vs_model_pct']}% vs model")
        lines4 += [f"- Quote variance outside tolerance: {x}" for x in bad] or ["- All quotes within tolerance"]
        lines4 += ["- Bedrooms/layout vs confirmed plans and operator running costs vs real figures: compared per property below only when you have supplied them; none supplied yet."]
        st4 = "FAIL" if bad else "PENDING"
    else: lines4 += ["Needs from you: a tolerance %, 3 to 5 properties, at least one QS quote per rate line used, and one operator's real cost sheet."]
    add(4, "Calibration on real properties (tool vs reality)", st4, lines4)
# 2 geometry, 3 economics, 6 guardrails: automated tests
ok, n, f, last = pytest_run("tests/test_step2.py", "tests/test_property_record.py"); add(2, "Geometry: layout, compliance evaluator and plan reader hand-calculated test cases", "PASS" if ok else "FAIL", [f"- {n} passed, {f} failed", f"- `{last}`"])
ok, n, f, last = pytest_run("tests/test_economics.py", "tests/test_scenarios_api.py"); add(3, "Economics: hand-calculated formulas; unset inputs give 'needs input' and no numbers", "PASS" if ok else "FAIL", [f"- {n} passed, {f} failed (includes the Part 6.4 worked example)", f"- `{last}`"])
ok, n, f, last = pytest_run("tests/test_forbidden_words.py", "tests/test_auth.py", "tests/test_consent_pack.py")
g = flags.gated_flags()
add(6, "Compliance guardrails", "PASS" if ok and not any(g.values()) else "FAIL", [f"- {n} passed, {f} failed (forbidden-words scan, login/access control, no generated statements or signatures, review link flag)", f"- Outreach, field capture and offer-letter flags: {', '.join(f'{k}={v}' for k, v in g.items())} (gated routes answer 403 while false; tested)",
     "- CRM source/lawful-basis gates, do-not-contact enforcement and bulk-send limits: the outreach features are not built (flags stay off), so these cannot be tested yet. They must be built and tested before any flag is flipped."])
# 7 feeds
fs = subprocess.run([sys.executable, "scripts/feeds_status.py"], capture_output=True, text=True).stdout
bad = [l.split(None, 3)[0] + ": " + l.split(None, 3)[3] for l in fs.splitlines() if re.match(r"^(not_started|pending_licence|pending_purchase|blocked)\s", l)]
add(7, "Feeds: every feed live or consciously manual", "PASS" if not bad else "FAIL", [f"- {len(bad)} feed(s) are neither live nor consciously manual:"] + [f"  - {b}" for b in bad] + ["", "`make feeds-status`:", "```", fs.strip(), "```"])

order = sorted(R, key=lambda r: r[0]); passed = sum(1 for r in order if r[2] == "PASS")
out = [f"# Validation report", f"Generated {datetime.datetime.now().isoformat(timespec='seconds')} by `make validate`. {passed} of {len(order)} checks pass.", "",
       "| # | Check | Result |", "|---|---|---|"] + [f"| {n} | {t} | **{s}** |" for n, t, s, _ in order] + [""]
for n, t, s, L in order: out += [f"## {n}. {t}: {s}", ""] + L + [""]
blockers = [f"{n}. {t} ({s})" for n, t, s, _ in order if s != "PASS"]
out += ["## Go / no-go", "", "**NO-GO.** " + ("Not every check passes. " if blockers else "") + "The outreach, field capture and offer letter flags stay off. This report never flips a flag; you do, in `config/feature_flags.yaml`, only when you decide." if blockers
        else "**GO** on the automated checks. Flipping the flags is still your decision, made by editing `config/feature_flags.yaml`.", "", "Blocking items:"] + [f"- {b}" for b in blockers]
(ROOT / "docs" / "VALIDATION.md").write_text("\n".join(out) + "\n"); print("\n".join(out[:12]))
