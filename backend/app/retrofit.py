"""Retrofit quantities and cost range (MASTER_SPEC Part 3 section 5, Part 7 step 7). Quantities come from the layout option and the compliance run; rates come only from config/rates.yaml,
which is blank until you fill it with QS quotes. A line with no rate is reported 'needs rate' and the total is None: never a partial total that looks complete. Allowance lines are flagged ALLOWANCE."""
from functools import lru_cache
import yaml
from .config import ROOT

@lru_cache
def rates() -> dict: return yaml.safe_load((ROOT / "config/rates.yaml").read_text())

def quantities(option: dict, checks: dict | None, facts: dict) -> dict:
    """Quantity per rate line, each with where it came from. None = cannot be derived (an allowance line applies instead)."""
    rooms = [a for lv in option["levels"] for a in lv["rooms"]]
    convert = [a for a in rooms if a["action"] == "convert"]
    new_ens = sum(1 for a in rooms if any("ensuite" in i for i in a["items"]) or (a["action"] == "convert" and a["becomes"] == "ensuite"))   # once per room
    beds_rooms = option["resident_rooms"]
    communal = sum(1 for a in rooms if a["type"] in ("lounge", "dining", "kitchen", "laundry", "office"))
    by = {c["id"]: c for c in (checks or {}).get("checks", [])}
    lifts = by.get("lift_levels", {}).get("quantity") or {}
    q = {"strip_out_demolition": (len(convert), "rooms changing use in the option"), "ensuite_build_or_upgrade": (new_ens, "new or converted ensuites in the option"),
         "room_change_of_use_fitout": (len([a for a in convert if a["becomes"] in ("resident room",)]), "rooms converted to resident rooms"),
         "nurse_call": (beds_rooms + communal, "resident rooms + communal rooms (one point each)"), "fire_alarm_detection": (beds_rooms + communal, "resident rooms + communal rooms (one point each)"),
         "emergency_lighting_exit_signs": (None, "needs the exit and escape route survey: allowance"), "furniture_fitout_per_bed": (option["beds"], "beds in the option"),
         "door_widening": (None, "needs a door width requirement and calibrated doors"), "corridor_widening": (None, "needs a corridor width requirement"),
         "flooring_finishes_painting": ((facts.get("net_room_area_m2") or {}).get("value"), "net room area fact (calibrated plan), if known"),
         "lift_or_platform_lift": (1 if lifts.get("lifts_to_add") else None, "lift check result")}
    return {k: {"qty": v[0], "from": v[1]} for k, v in q.items()}

def cost(option: dict, checks: dict | None, facts: dict, rate_cfg: dict | None = None) -> dict:
    cfg = rate_cfg or rates(); qs = quantities(option, checks, facts)
    lines, missing = [], []
    for name, r in cfg["lines"].items():
        q = qs.get(name, {"qty": None, "from": "allowance line: no quantity derived"}); have = all(r.get(k) is not None for k in ("low", "base", "high"))
        qty = q["qty"] if r["basis"] == "plan" and q["qty"] is not None else (1 if r["basis"] == "allowance" or q["qty"] is None else q["qty"])
        is_allowance = r["basis"] == "allowance" or q["qty"] is None
        if not have: missing.append(name); lines.append({"line": name, "unit": r["unit"], "quantity": qty if not is_allowance else None, "allowance": is_allowance, "status": "needs rate", "from": q["from"]}); continue
        lines.append({"line": name, "unit": r["unit"], "quantity": qty, "allowance": is_allowance, "from": q["from"], "source": r.get("source"), "date": r.get("date"),
                      **{k: qty * r[k] for k in ("low", "base", "high")}})
    pct_missing = [k for k, r in cfg["pct_lines"].items() if any(r.get(x) is None for x in ("low", "base", "high"))]
    out = {"lines": lines, "needs_rate": missing + pct_missing, "label": "Screening estimate; a quantity surveyor must confirm.", "total": None, "allowance_share_pct": None, "banner": None}
    if out["needs_rate"]: out["note"] = "Total withheld: every line needs a rate (config/rates.yaml). A partial total would look complete and is not shown."; return out
    sub = {k: sum(l[k] for l in lines) for k in ("low", "base", "high")}
    total = {}
    for k in sub:
        v = sub[k]
        for pl in cfg["pct_lines"].values(): v += sub[k] * pl[k] / 100
        total[k] = v
    allow = sum(l["base"] for l in lines if l["allowance"]); share = allow / sub["base"] * 100 if sub["base"] else 0.0
    out.update(subtotal=sub, total=total, allowance_share_pct=share, per_bed={k: total[k] / option["beds"] for k in total} if option["beds"] else None,
               top_drivers=sorted(({"line": l["line"], "base": l["base"]} for l in lines), key=lambda x: -x["base"])[:5],
               banner="Mostly allowances; get QS pricing before relying on this" if share > 30 else None)
    return out
