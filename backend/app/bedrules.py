"""Bed rules and requirement slots from config. Regulatory values stay blank until sourced; a blank rule is never applied and is reported.
Values typed on the Standards screen (from the owner's own copy of the standard) are stored in core.user_setting and layered over the blank config."""
import copy, datetime, re
from functools import lru_cache
import yaml
from fastapi import HTTPException
from .config import ROOT
from .db import conn

@lru_cache
def _file() -> dict: return yaml.safe_load((ROOT / "config/bed_rules.yaml").read_text())

def load() -> dict:
    cfg = copy.deepcopy(_file())
    try:
        with conn() as c: rows = c.execute("SELECT key, value FROM core.user_setting WHERE key LIKE 'bedrule:%'").fetchall()
    except Exception: rows = []
    for r in rows:
        name = r["key"][len("bedrule:"):]
        if name in cfg["regulatory"] and isinstance(r["value"], dict): cfg["regulatory"][name] = r["value"]
    return cfg

def _check(name: str, v):
    if name == "min_resident_room_m2":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 1 <= v <= 100: raise HTTPException(422, "min_resident_room_m2 must be a number of square metres between 1 and 100")
    elif name == "communal_area_per_bed_m2":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100: raise HTTPException(422, "communal_area_per_bed_m2 must be a number between 0 and 100")
    elif name == "double_occupancy_allowed":
        if not isinstance(v, bool): raise HTTPException(422, "double_occupancy_allowed must be true or false")
    elif name == "ensuite_required":
        if not (v in ("per_room", "none") or (isinstance(v, str) and re.fullmatch(r"per_n_rooms:[1-9][0-9]?", v))): raise HTTPException(422, "ensuite_required must be per_room, none or per_n_rooms:N")

def save(values: dict) -> dict:
    """values: {name: {value, clause, last_verified?, source?}}; value null clears it back to blank. A value is refused without the clause it came from."""
    from .settings import _put
    reg = _file()["regulatory"]; bad = [k for k in values if k not in reg]
    if bad: raise HTTPException(422, f"unknown bed rule(s): {bad}")
    with conn() as c:
        for name, e in values.items():
            if e.get("not_stated"):
                _put(c, f"bedrule:{name}", {"value": None, "status": "not_stated", "clause": (e.get("clause") or "").strip() or None, "last_verified": e.get("last_verified") or datetime.date.today().isoformat(),
                                            "source": (e.get("source") or "owner's own copy").strip(), "entered_by": "owner"}); continue
            if e.get("value") is None:
                c.execute("DELETE FROM core.user_setting WHERE key = %s", (f"bedrule:{name}",)); continue
            _check(name, e["value"])
            if not (e.get("clause") or "").strip(): raise HTTPException(422, f"{name}: give the clause or section it came from (for example the Ngā Paerewa clause number)")
            when = e.get("last_verified") or datetime.date.today().isoformat()
            _put(c, f"bedrule:{name}", {"value": e["value"], "clause": e["clause"].strip(), "last_verified": when, "source": (e.get("source") or "owner's own copy").strip(), "entered_by": "owner"})
        c.commit()
    return view()

def view() -> dict:
    cfg = load(); ref = yaml.safe_load((ROOT / "config/building_code_clause_checklist.yaml").read_text())
    return {"regulatory": cfg["regulatory"], "states": {k: state(k) for k in cfg["regulatory"]}, "missing": missing_regulatory(), "building_code_clauses": ref["clauses"], "building_code_clauses_verified": ref["verified"],
            "note": "Values are blank until you type them from your own copy of the standard, with the clause and date. A blank rule is not applied and every layout option says so."}

def reg(name: str):
    return (load()["regulatory"].get(name) or {}).get("value")

def state(name: str) -> str:
    """'entered' (owner typed a value with its clause), 'not_stated' (owner checked their copy: the standard does not state it) or 'blank'."""
    e = load()["regulatory"].get(name) or {}
    return "entered" if e.get("value") is not None else ("not_stated" if e.get("status") == "not_stated" else "blank")

def missing_regulatory() -> list[str]:
    return [k for k in load()["regulatory"] if reg(k) is None]

def design() -> dict: return load()["design"]

@lru_cache
def requirements() -> list[dict]: return yaml.safe_load((ROOT / "config/rh_requirements.yaml").read_text())["requirements"]
