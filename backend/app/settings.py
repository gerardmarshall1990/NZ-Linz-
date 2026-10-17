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

FLAGS = ("owner_entered", "estimate", "quote", "confirmed")

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
