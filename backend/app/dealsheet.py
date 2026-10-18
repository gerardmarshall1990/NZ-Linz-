"""Rest Home Deal Sheet (MASTER_SPEC 6.3): one PDF per property with the confidence banner, bed scenarios, compliance status, retrofit range, economics and walk-away rent.
Built from the same engines as the screens, so it shows exactly what they show, including 'needs input' where a figure is not available: nothing is filled in to make the page look complete."""
from datetime import date
from fastapi import HTTPException
from . import economics, retrofit, settings
from .compliance import _facts, run as run_checks
from .db import conn
from .facts import get_property
from .layout import get_option, list_options
from .pack_pdf import md_to_pdf

def _m(x): return "needs input" if x is None else f"${x:,.0f}"
def _p(x): return "needs input" if x is None else f"{x * 100:.0f}%"
FOOT = "Screening and preparation tool. Illustrative projections from your stated assumptions; a quantity surveyor, accountant, planner and the relevant engineers must confirm. Not advice. Council decides applications. Natural hazard flags are information only for conversions of existing buildings."

def build(parcel_id: int, option_id: int | None = None) -> dict:
    rec = get_property(parcel_id); opts = list_options(parcel_id)
    if not opts: raise HTTPException(409, "no layout options yet: confirm a plan and generate layouts first (a deal sheet needs bed scenarios)")
    o = get_option(option_id) if option_id else max(opts, key=lambda x: x["beds"])
    if o["parcel_id"] != parcel_id: raise HTTPException(404, "option belongs to another property")
    site = rec["site"]; tier = rec["lowest_confidence"] or "ESTIMATED"; p = settings.assumptions(); facts = _facts(parcel_id)
    chk = run_checks(parcel_id, o["id"]); r = retrofit.cost(o, chk, facts, settings.rates_cfg()); rc = (r["total"] or {}).get("base")
    f = economics.feasibility(o["beds"], p, rc, tier); sens = economics.sensitivity(o["beds"], p, rc)
    ph = settings.used_not_decision_grade(settings.OPEX_NEEDED, None) if (f.get("stabilised") or {}).get("net") is not None else []
    bn = settings.banner_for(ph); L = [f"# Rest Home Deal Sheet: {site['address']}, {site['suburb']}", f"Parcel {parcel_id} | zone {site['zone_name']} | title {site['title_type'] or 'unknown'} | generated {date.today().isoformat()} | evidence level {rec['evidence_level']}", ""]
    if tier in (None, "ESTIMATED"): L += ["**Screening only: bedrooms/plans not confirmed**", ""]
    if bn.get("placeholder_banner"): L += [f"**{bn['placeholder_banner']}.** Placeholders that drove this: " + "; ".join(f"{x['label']} = {x['value']} ({x['flag']})" for x in bn["placeholders_used"]) + ".", ""]
    if r["banner"]: L += [f"**{r['banner']}**", ""]
    L += ["## Bed scenarios", "| Scenario | Beds | Binding constraint | New-work items | |", "|--|--|--|--|--|"]
    L += [f"| {x['scenario']} | {x['beds']} | {x['binding_constraint']} | {x['new_work_items']} | {'shown below' if x['id'] == o['id'] else ''} |" for x in opts]
    if o["below_target"]: L += ["", "Below the 50-bed single-consent target."]
    if o["rules_not_applied"]: L += ["", "Bed rules not yet applied: " + ", ".join(o["rules_not_applied"]) + " (the bed count is an upper bound until the standard's values are loaded)."]
    c = chk["counts"]; L += ["", "## Compliance (screening)", " | ".join(f"{k} {v}" for k, v in c.items()), ""]
    if chk["deal_breakers"]: L += ["Deal-breaker flags: " + ", ".join(chk["deal_breakers"]), ""]
    L += [chk["label"], "", "## Retrofit cost (screening estimate; a QS must confirm)"]
    if r["total"] is None: L += [f"Total withheld: rates still needed for {len(r['needs_rate'])} line(s) ({', '.join(r['needs_rate'][:6])}{'...' if len(r['needs_rate']) > 6 else ''}). Enter them under My inputs or from quotes."]
    else: L += [f"Low {_m(r['total']['low'])} | **Base {_m(r['total']['base'])}** | High {_m(r['total']['high'])}; per bed (base) {_m(r['per_bed']['base'])}; allowances {r['allowance_share_pct']:.0f}% of the base subtotal. Top drivers: " + ", ".join(f"{d['line']} ({_m(d['base'])})" for d in r["top_drivers"])]
    L += ["", "## Economics (stabilised, illustrative)"]
    if (f.get("stabilised") or {}).get("net") is None: L += ["Needs input: " + ", ".join(sorted(set(f["needs_input"]))) + "."]
    else:
        be = f["break_even_occupancy"]
        L += [f"- Stabilised annual profit before rent: **{_m(f['stabilised_annual_profit_before_rent'])}** (margin {_p(f['margin'])}) at {_p(p['stabilised_occupancy'])} occupancy",
              f"- **Walk-away rent per week: {_m(f['walk_away_rent_per_week'])}**; rent headroom per week: {_m(f['rent_headroom_per_week'])}",
              f"- Break-even occupancy (profit zero): {_p(be.get('profit_zero'))}; to reach target profit: {_p(be.get('profit_target'))}",
              f"- Retrofit charge per week: {_m((f.get('retrofit_charge') or {}).get('weekly'))}"]
        if f["needs_input"]: L += ["- Still needs input: " + ", ".join(sorted(set(f["needs_input"])))]
        g = sens.get("grid") or {}
        if len(g) > 1:
            L += ["", "| Case | Weekly profit before rent | Walk-away rent / week |", "|--|--|--|"] + [f"| {k.replace('_', ' ')} | {_m(v['N'])} | {_m(v['walk_away_rent_per_week'])} |" for k, v in g.items()]
    with conn() as cn:
        off = cn.execute("SELECT id, output, created_at FROM core.rh_scenario WHERE parcel_id=%s AND option_id=%s AND kind='offer' ORDER BY id DESC LIMIT 1", (parcel_id, o["id"])).fetchone()
    if off and off["output"].get("modes"):
        L += ["", f"## Latest Offer Builder run ({off['created_at'].date().isoformat()})"]
        for mode, m in off["output"]["modes"].items():
            if m.get("blocked"): L += [f"- {mode}: blocked"]; continue
            L += [f"- {mode}: owner weekly at stabilisation {_m(m['owner']['weekly_at_stabilisation'])}; operator cash required {_m((m.get('operator') or {}).get('cash_required'))}, full-timeline payback {(m.get('operator') or {}).get('payback_weeks_full_timeline_from_lease_start') or 'n/a'} weeks"]
    L += ["", "---", FOOT]
    md = "\n".join(L)
    return {"parcel_id": parcel_id, "option_id": o["id"], "markdown": md, "tier": tier, "placeholders_used": bn.get("placeholders_used", [])}

def pdf(parcel_id: int, option_id: int | None = None) -> bytes:
    d = build(parcel_id, option_id); return md_to_pdf(d["markdown"], "", stamp="Screening only. Not advice.")
