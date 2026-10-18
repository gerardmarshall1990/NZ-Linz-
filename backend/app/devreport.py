"""Detailed report (MASTER_SPEC Part 2 section 1.3, Site Panel button 2): extends the latest scenario run. Enabled only after button 1 has run. Sections follow the spec; where an input is blank the section says so."""
from datetime import date
from functools import lru_cache
import yaml
from fastapi import HTTPException
from . import devrules, services
from .config import ROOT
from .devscenarios import FOOTER, TIMELINE_STAGES, latest, get_run
from .pack_pdf import md_to_pdf

@lru_cache
def site_rates() -> dict: return yaml.safe_load((ROOT / "config" / "dev_rates.yaml").read_text())["lines"]
def _m(x): return "needs input" if x is None else f"${x:,.0f}"

BRIEFS = [("Planner", "consent pathway and activity status for any infringement"), ("Licensed surveyor", "boundaries, levels, scheme plan (subdivision), easements"), ("Civil engineer", "servicing, stormwater, earthworks, retaining"),
          ("Geotechnical engineer", "ground conditions where hazards are flagged"), ("Architect / designer", "the actual building design: this report is a concept layout only"), ("Quantity surveyor", "replace allowances with priced quantities")]

def build(parcel_id: int, run_id: int | None = None) -> dict:
    run = get_run(run_id) if run_id else latest(parcel_id)
    if not run or run.get("status") == "none": raise HTTPException(409, "run the feasibility summary (button 1) first: the detailed report extends that run")
    if run.get("status") == "needs_input": raise HTTPException(409, "the latest run needs input (" + ", ".join(run.get("needs_input", [])) + "): complete it first")
    sc = (run.get("scenarios") or [None])[0]; fin = run.get("financials") or {}; svc = services.get(parcel_id); inp = run["inputs"]
    L = [f"# Detailed development report: {run['address']}", f"Parcel {parcel_id} | zone {run['zone']} | run {run['run_id']} | {date.today().isoformat()}", ""]
    if run.get("superseded"): L += ["**This run has been superseded by a newer one.**", ""]
    L += ["## 1. Executive summary"]
    if inp["typology"] == "lots":
        sub = run["subdivision"]; L += [f"- Subdivision upper bound by area: {sub.get('max_lots_by_area', 'n/a')} lots ({sub.get('note', '')})"]
    elif sc: L += [f"- Scenario: {sc['unit_count']} {inp['typology']} ({sc['kind'].replace('_', ' ')}); rules badge: **{run.get('badge_label')}**", f"- Binding constraint: {run['binding_constraint']['explanation']}"]
    L += [f"- Profit: {_m(fin.get('profit')) if fin.get('status') == 'ok' else 'needs input (' + ', '.join(fin.get('needs_input', [])[:4]) + ')'}", f"- Open items: {len(run.get('open_items', []))}", ""]
    L += ["## 2. Site and planning analysis", f"- Area {run['site']['area_m2']} m2; title type {run['site']['title_type'] or 'unknown'}; existing buildings recorded: {run['site']['existing_buildings']} (assumed demolished).", f"- Overlays: {run['site']['overlays'] or 'none recorded'}.",
          f"- Hazards: {run['site']['hazards']['hazard_flags']}. {run['site']['hazards']['note']}", f"- Māori land flag: {run['site']['maori_land']}.", f"- Plan Change 120 depends flag: {run['site']['pc120_depends']} (proposed rules are not applied).",
          "- Easements, covenants and neighbouring context are not in the data: a title search and survey are needed.", ""]
    L += ["## 3. How the density is achieved"]
    if sc and inp["typology"] != "lots":
        m = sc["meta"]; L += [f"The buildable envelope is the parcel minus the yard strips (front, side, rear) from the rules corpus ({run['envelope_area_m2']} m2). Units of the stated footprint, each with its own ground-floor outdoor living space, are packed in rows; {run['candidates_evaluated']} arrangements (orientations, offsets and driveway options) were generated and each unit count was run through the rules evaluator. Chosen: orientation {m['theta']} degrees, driveway: {m['access']}.",
                              f"**Binding constraint:** {run['binding_constraint']['explanation']}.", ""]
    L += ["## 4. Consent pathway", "Activity status rows for related activities in this zone (the planner decides which one applies; a breach of a standard moves the activity status):", "| Activity | Status | Rule |", "|--|--|--|"]
    L += [f"| {a['activity']} | {a['status_class']} | {a['section_ref']} |" for a in run.get("activity_rows", [])] or ["| (none found) | | |"]
    L += ["", "Likely approvals to confirm: " + "; ".join(["resource consent (land use and/or subdivision) if any standard is infringed", "building consent", *services.CONSENT_TRIGGERS]) + "."]
    L += ["", "## 5. Timeline (your durations; none are assumed)", "| Stage | Weeks | Starts week | Ends week |", "|--|--|--|--|"]; cur = 0; tl = inp.get("timeline_weeks", {})
    for k in TIMELINE_STAGES:
        w = tl.get(k); L += [f"| {k.replace('_', ' ')} | {w if w is not None else 'set duration'} | {cur if w is not None else ''} | {cur + w if w is not None else ''} |"]; cur += w or 0
    L += ["", "Stages run in sequence here; overlaps are for you to set. Council processing times are not assumed.", "", "## 6. Site works and cost lines"]
    L += ["| Line | Unit | Rate |", "|--|--|--|"] + [f"| {k.replace('_', ' ')} | {v['unit']} | {_m(v['value']) if v['value'] is not None else 'needs rate'} |" for k, v in site_rates().items()] + ["", f"Site works allowance used in the financials: {_m(inp['finance'].get('site_works_allowance'))}. Earthworks volumes need elevation data (not loaded).", ""]
    L += ["## 7. Services", f"Capacity: **{svc['capacity_status']}**. {svc['capacity_note']}", f"Manual entries: {svc['completeness']}.", "Confirmations needed:"] + [f"- {c}" for c in svc["confirmations_needed"]] + ["", "## 8. Financials"]
    if fin.get("status") == "ok":
        c = fin["costs"]; L += ["| Item | Amount |", "|--|--|", f"| Revenue | {_m(fin['revenue'])} |"] + [f"| {k.replace('_', ' ')} | {_m(v)} |" for k, v in c.items()] + [f"| Total cost | {_m(fin['total_cost'])} |", f"| **Profit** | **{_m(fin['profit'])}** |",
              f"| Margin on cost / revenue | {fin['margin_on_cost_pct']:.1f}% / {fin['margin_on_revenue_pct']:.1f}% |", f"| Peak funding (approx) | {_m(fin['peak_funding_approx'])} |", f"| Break-even price per unit | {_m(fin['break_even_price_per_unit'])} |", ""]
        sens = run.get("sensitivity", {}).get("profit")
        if sens: L += ["Sensitivity (profit, one change at a time):"] + [f"- {k.replace('_', ' ')}: {_m(v)}" for k, v in sens.items()]
    else: L += ["Needs input: " + ", ".join(fin.get("needs_input", [])) + "."]
    L += ["", "Formulas:"] + [f"- {f}" for f in fin.get("formulas", [])]
    L += ["", "## 9. Risks, assumptions and sensitivities", "- Front boundary, rear boundary and roof form are assumed (see the evaluator definitions); a surveyor and designer confirm.", "- Rule values come from the plan corpus and are not yet confirmed by you.",
          "- Vehicle access standards are not loaded: access is UNKNOWN in every scenario.", "- Comparable sales are not available: prices are your inputs.", "", "## 10. Professional briefs index"] + [f"- {a}: {b}" for a, b in BRIEFS]
    L += ["", "## 11. Provenance appendix: rules used", "| Rule | Reference | Confirmed by you |", "|--|--|--|"]
    seen = {}
    for c in (sc["checks"] if sc else []):
        if c.get("rule"): seen[(c["id"], c["rule"])] = c
    L += [f"| {k[0]} | {k[1]} (last verified {v.get('last_verified') or 'n/a'}) | {'yes' if v['owner_verified'] else 'not yet'} |" for k, v in sorted(seen.items())] + ["", FOOTER]
    return {"run_id": run["run_id"], "markdown": "\n".join(L)}

def pdf(parcel_id: int, run_id: int | None = None) -> bytes: return md_to_pdf(build(parcel_id, run_id)["markdown"], "", stamp="Screening report: concept only")
