"""'My inputs': deal assumptions and retrofit rates entered in the app. Stored in core.user_setting (user data, backed up) and layered over the blank config files.
Nothing is ever defaulted: a cleared value goes back to blank (None) and dependent outputs go back to 'needs input'. Every change is kept in core.user_setting_history."""
import json
from fastapi import HTTPException
from . import economics, retrofit
from .db import conn

ENUMS = {"retrofit_funding_mode": ["i_fund", "owner_funds_via_rent"], "care_level": ["rest_home"]}
FRACTIONS = {"stabilised_occupancy"}
LISTS = {"fill_ramp_by_month", "roster_step_thresholds"}

def _validate_assumption(name: str, v):
    if name not in economics.default_assumptions(): raise HTTPException(422, f"unknown assumption {name!r}")
    if v is None: return None
    if name in ENUMS:
        if v not in ENUMS[name]: raise HTTPException(422, f"{name} must be one of {ENUMS[name]}")
        return v
    if name in LISTS:
        if not isinstance(v, list) or not all(isinstance(x, (int, float)) and 0 <= x for x in v): raise HTTPException(422, f"{name} must be a list of non-negative numbers")
        if name == "fill_ramp_by_month" and any(x > 1 for x in v): raise HTTPException(422, "fill_ramp_by_month values are fractions between 0 and 1")
        return v
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0: raise HTTPException(422, f"{name} must be a non-negative number or blank")
    if name in FRACTIONS and v > 1: raise HTTPException(422, f"{name} is a fraction between 0 and 1 (for example 0.9)")
    return v

def _put(c, key, value):
    old = c.execute("SELECT value FROM core.user_setting WHERE key = %s", (key,)).fetchone()
    if old and old["value"] == value: return False
    c.execute("INSERT INTO core.user_setting (key, value, updated_by) VALUES (%s,%s::jsonb,'owner') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()", (key, json.dumps(value)))
    c.execute("INSERT INTO core.user_setting_history (key, old_value, new_value) VALUES (%s,%s::jsonb,%s::jsonb)", (key, json.dumps(old["value"]) if old else None, json.dumps(value))); return True

def stored() -> dict:
    with conn() as c: return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM core.user_setting").fetchall()}

def assumptions() -> dict:
    d = dict(economics.default_assumptions()); s = stored()
    for k, v in s.items():
        if k.startswith("assumption:") and k[11:] in d: d[k[11:]] = v
    return d

def rates_cfg() -> dict:
    cfg = json.loads(json.dumps(retrofit.rates())); s = stored()
    for k, v in s.items():
        if k.startswith("rate:") and k[5:] in cfg["lines"]: cfg["lines"][k[5:]].update(v)
        if k.startswith("pct:") and k[4:] in cfg["pct_lines"]: cfg["pct_lines"][k[4:]].update(v)
    return cfg

FLAGS = ("owner_entered", "estimate", "quote", "confirmed", "placeholder")
NOT_DECISION_GRADE = ("placeholder", "estimate")      # inputs that cap verdicts at AMBER and trigger the banner
from .labels import PLACEHOLDER_BANNER as BANNER

def set_assumptions(values: dict, flags: dict | None = None, notes: dict | None = None) -> dict:
    """Save assumptions. Each saved value carries a flag (owner_entered by default; estimate / quote / confirmed on request) and an optional note, with the date."""
    clean = {n: _validate_assumption(n, v) for n, v in values.items()}
    flags = flags or {}; notes = notes or {}
    for n, f in flags.items():
        if f not in FLAGS: raise HTTPException(422, f"flag for {n} must be one of {list(FLAGS)}")
    import datetime
    with conn() as c:
        for n, v in clean.items():
            if _put(c, f"assumption:{n}", v) or n in flags or n in notes:
                if v is None: c.execute("DELETE FROM core.user_setting WHERE key = %s", (f"flag:assumption:{n}",))
                else: _put(c, f"flag:assumption:{n}", {"flag": flags.get(n, "owner_entered"), "note": notes.get(n), "on": datetime.date.today().isoformat()})
        c.commit()
    return view()

def set_rates(lines: dict | None, pct: dict | None) -> dict:
    cfg = retrofit.rates()
    with conn() as c:
        for name, r in (lines or {}).items():
            if name not in cfg["lines"]: raise HTTPException(422, f"unknown rate line {name!r}")
            _put(c, f"rate:{name}", _rate(r))
        for name, r in (pct or {}).items():
            if name not in cfg["pct_lines"]: raise HTTPException(422, f"unknown percentage line {name!r}")
            _put(c, f"pct:{name}", _rate(r, pct=True))
        c.commit()
    return view()

def _rate(r: dict, pct: bool = False) -> dict:
    out = {}
    for k in ("low", "base", "high"):
        v = r.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0): raise HTTPException(422, f"{k} must be a non-negative number or blank")
        out[k] = v
    given = [out[k] for k in ("low", "base", "high") if out[k] is not None]
    if given and (None in (out["low"], out["base"], out["high"]) or not (out["low"] <= out["base"] <= out["high"])): raise HTTPException(422, "give low, base and high together, with low <= base <= high")
    if not pct:
        out["source"] = (r.get("source") or "").strip() or None; out["date"] = r.get("date") or None
        if given and not out["source"]: raise HTTPException(422, "a rate needs a source (QS quote, supplier, own estimate) and ideally a date")
    return out

def view() -> dict:
    d = assumptions(); a = economics.default_assumptions(); s = stored()
    return {"assumptions": {k: {"value": v, "from": "you" if f"assumption:{k}" in s else ("config" if v is not None else "blank"), "flag": (s.get(f"flag:assumption:{k}") or {}).get("flag"), "note": (s.get(f"flag:assumption:{k}") or {}).get("note"), "on": (s.get(f"flag:assumption:{k}") or {}).get("on")} for k, v in d.items()},
            "blank_assumptions": [k for k, v in d.items() if v is None and not isinstance(a[k], list)],
            "rates": rates_cfg(), "note": "Blank means not set. Dependent outputs show 'needs input' until you set them."}


# ------------------------------------------------------------------------------------ placeholders
import yaml
from .config import ROOT as _ROOT

def placeholder_defs() -> dict: return yaml.safe_load((_ROOT / "config/placeholders.yaml").read_text())

def meta() -> dict:
    s = stored(); return {k[len("flag:assumption:"):]: v for k, v in s.items() if k.startswith("flag:assumption:")}

def load_placeholders() -> dict:
    """Fill ONLY blank inputs with the placeholders (flag 'placeholder', source as note) and record the confirmed roster multiplier. Never overwrites a value you entered."""
    defs = placeholder_defs(); cur = assumptions(); st = stored(); loaded, kept = [], []
    vals, flags, notes = {}, {}, {}
    for k, d in defs["placeholders"].items():
        if f"assumption:{k}" in st and st[f"assumption:{k}"] is not None: kept.append(k); continue
        vals[k] = d["value"]; flags[k] = "placeholder"; notes[k] = d["source"]; loaded.append(k)
    for k, d in defs["confirmed"].items():
        if f"assumption:{k}" in st and st[f"assumption:{k}"] is not None: kept.append(k); continue
        vals[k] = d["value"]; flags[k] = d["flag"]; notes[k] = d["source"]; loaded.append(k)
    if vals: set_assumptions(vals, flags, notes)
    return {"loaded": loaded, "kept_your_values": kept}

def placeholder_rows() -> list[dict]:
    d = placeholder_defs(); a = view()["assumptions"]; out = []
    for k, x in a.items():
        if x.get("flag") in NOT_DECISION_GRADE:
            info = d["placeholders"].get(k, {})
            out.append({"key": k, "label": info.get("label", k.replace("_", " ")), "value": x["value"], "flag": x["flag"], "source": x.get("note"), "basis": info.get("basis", "owner estimate"), "on": x.get("on")})
    return out

def used_not_decision_grade(keys, overrides: dict | None = None) -> list[dict]:
    """The not-decision-grade inputs (placeholders and owner estimates) that a result actually depends on, excluding any you overrode for that one deal."""
    ov = set(overrides or {}); rows = {r["key"]: r for r in placeholder_rows()}
    return [{"key": k, "label": rows[k]["label"], "value": rows[k]["value"], "flag": rows[k]["flag"], "source": rows[k]["source"]} for k in keys if k in rows and k not in ov]

OPEX_NEEDED = list(economics.OPEX_KEYS) + ["stabilised_occupancy", "retrofit_cost_per_bed_screening", "lease_term_years", "cost_of_capital_pct", "minimum_acceptable_profit_per_year"]
OFFER_NEEDED = OPEX_NEEDED + ["pre_opening_costs", "working_capital", "fill_ramp_by_month", "target_profit_per_year"]

def banner_for(used: list[dict]) -> dict:
    return {"placeholder_banner": BANNER if used else None, "placeholders_used": used}
