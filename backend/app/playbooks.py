"""Archetype playbooks and the delta view (MASTER_SPEC Part 8.3). A playbook holds an archetype's layout rules, fire strategy template, specification template, cost model, typical gaps and an engineer review checklist; the reviewing engineers
write the content ONCE (the YAML files are skeletons marked [TO COMPLETE], reviewed_by_engineer blank) and each property then shows only its DELTA: where the property differs from the archetype. Nothing transfers between consents automatically.
The apartment building playbook computes its checks from the Property Record (title type, fire systems, lift) and the bed count after units are sacrificed for communal rooms (unit counts are your inputs)."""
from functools import lru_cache
import yaml
from fastapi import HTTPException
from .compliance import _facts
from .config import ROOT
from .db import conn
from .facts import get_property

@lru_cache
def all_playbooks() -> dict:
    d = {}
    for p in sorted((ROOT / "config" / "playbooks").glob("*.yaml")): y = yaml.safe_load(p.read_text()); d[y["name"]] = y
    return d

def list_() -> list[dict]: return [{"name": k, "title": v["title"], "reviewed_by_engineer": v.get("reviewed_by_engineer"), "complete": "[TO COMPLETE" not in str(v.get("layout_rules"))} for k, v in all_playbooks().items()]

def match(parcel_id: int) -> list[str]:
    f = _facts(parcel_id); v = lambda k: (f.get(k) or {}).get("value"); out = []
    try: rec = get_property(parcel_id); site = rec["site"] or {}
    except HTTPException: site = {}
    tt = str(v("title_type") or site.get("title_type") or "").lower(); st = v("storeys_per_building"); st = st[0] if isinstance(st, list) and st else st
    for name, p in all_playbooks().items():
        a = p.get("applies_when", {}); ok = True
        if "title_type" in a: ok &= any(t.replace("_", " ") in tt for t in a["title_type"])
        if "storeys" in a: ok &= st in a["storeys"]
        if "current_use" in a: ok &= a["current_use"] in str(v("current_use") or "").lower()
        if "building_count_min" in a: ok &= (site.get("building_count") or 0) >= a["building_count_min"]
        if "bedrooms_min" in a: ok &= (v("bedrooms_total") or 0) >= a["bedrooms_min"]
        if "building_count" in a: ok &= site.get("building_count") == a["building_count"]
        if ok: out.append(name)
    return out

def apartment(parcel_id: int, units_total: int | None = None, units_per_role: dict | None = None, owners: int | None = None, single_party_controls: bool | None = None) -> dict:
    p = all_playbooks()["apartment_building"]; f = _facts(parcel_id); val = lambda k: (f.get(k) or {}).get("value"); res = []
    tt = str(val("title_type") or "").lower()
    if not tt: st, d = "UNKNOWN", "title type not known"
    elif "unit" in tt or "cross" in tt:
        if owners is None: st, d = "UNKNOWN", f"title type '{tt}': number of owners not entered"
        elif owners > 1 and not single_party_controls: st, d = "FAIL", f"{owners} owners and no single party controls the building: deal-breaker flag"
        else: st, d = "NEEDS_PROFESSIONAL", f"{owners} owner(s); body corporate rules and consent need a lawyer"
    else: st, d = "NOT_APPLICABLE", f"title type '{tt}'"
    res.append({"id": "title_owners", "status": st, "detail": d, "deal_breaker": st == "FAIL"})
    for c in p["checks"][1:3]:
        vals = {k: val(k) for k in c["facts"]}; unk = [k for k, x in vals.items() if x is None]
        res.append({"id": c["id"], "status": "UNKNOWN" if unk else "NEEDS_PROFESSIONAL", "detail": (f"not recorded: {', '.join(unk)}" if unk else f"recorded: {vals}; adequacy for care use needs the fire engineer / designer"), "deal_breaker": False})
    from . import bedrules
    reqs = {r["id"]: r for r in bedrules.requirements()}
    for rid in p["checks"][3]["requirements"]: res.append({"id": rid, "status": "UNKNOWN", "detail": f"requirement not loaded ({reqs[rid]['source']}): corridor and door widths cannot be judged", "deal_breaker": False} if reqs[rid].get("value") is None else {"id": rid, "status": "NEEDS_PROFESSIONAL", "detail": "value loaded: compare with calibrated plan", "deal_breaker": False})
    roles = p["communal_roles"]; given = units_per_role or {}; miss = [r for r in roles if r not in given]
    if units_total is None or miss: res.append({"id": "beds_after_communal", "status": "UNKNOWN", "detail": "needs: units_total" + (f" and units used for: {', '.join(miss)}" if miss else ""), "deal_breaker": False, "beds": None})
    else:
        lost = sum(given.values()); beds = max(0, units_total - lost); res.append({"id": "beds_after_communal", "status": "NEEDS_PROFESSIONAL", "detail": f"{units_total} units minus {lost} used for communal rooms = {beds} beds (one resident per unit: regulatory occupancy rules not loaded)", "deal_breaker": False, "beds": beds})
    res.append({"id": "building_wide_allowances", "status": "NEEDS_PROFESSIONAL", "detail": "allowances (all flagged ALLOWANCE, rates blank until quoted): " + ", ".join(p["cost_model"]["allowance_lines"]), "deal_breaker": False})
    return {"parcel_id": parcel_id, "playbook": "apartment_building", "checks": res, "deal_breakers": [c["id"] for c in res if c["deal_breaker"]], "engineer_review_checklist": p["engineer_review_checklist"], "reviewed_by_engineer": p.get("reviewed_by_engineer"),
            "label": "Screening checks from the apartment building archetype. Nothing transfers between consents automatically."}

def delta(parcel_id: int, option_id: int | None, name: str) -> dict:
    pb = all_playbooks().get(name)
    if not pb: raise HTTPException(404, "no such playbook")
    complete = "[TO COMPLETE" not in str(pb.get("layout_rules"))
    from .compliance import run
    chk = run(parcel_id, option_id); notable = [c for c in chk["checks"] if c["status"] in ("FAIL", "NEEDS_PROFESSIONAL", "UNKNOWN")]
    out = {"parcel_id": parcel_id, "playbook": name, "matches_archetype": name in match(parcel_id), "reviewed_by_engineer": pb.get("reviewed_by_engineer"), "playbook_content_complete": complete}
    if not complete or not pb.get("reviewed_by_engineer"):
        out.update(delta_available=False, reason="the playbook has not been written and reviewed by your engineers yet, so there is no baseline to compare against; every item below is shown in full", items=[{"id": c["id"], "status": c["status"], "detail": c["detail"]} for c in notable])
    else: out.update(delta_available=True, items=[{"id": c["id"], "status": c["status"], "detail": c["detail"]} for c in notable if c["id"] not in (pb.get("typical_gaps") or [])])
    return out
