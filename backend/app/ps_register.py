"""Producer statement author register check (MASTER_SPEC 7.1, Part 2 section 8).
Auckland Council publishes the register as an online search only (docs/council_forms/README.md), with no list that can be downloaded from here. Two routes, both recorded with a date and who checked:
  1. A register export the owner drops in docs/sources_manual/ps_register/*.csv (columns: name, company, registration_no, discipline, valid_until; extra columns ignored). The match is exact on normalised name and company.
  2. A manual check the owner makes on the Council's search page and records here (status, date).
With no file loaded and no manual check, the status stays 'not_checked' and the statement does not count as valid."""
import csv, re
from datetime import date
from pathlib import Path
from .config import ROOT

REG_DIR = ROOT / "docs" / "sources_manual" / "ps_register"
MAX_AGE_DAYS = 30        # a manual or file check older than this must be repeated before lodging

def _n(s): return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def load() -> list[dict]:
    rows = []
    for p in sorted(REG_DIR.glob("*.csv")):
        with p.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
                if r.get("name"): rows.append({**r, "_file": p.name})
    return rows

def loaded() -> bool: return bool(list(REG_DIR.glob("*.csv")))

def check(name: str | None, company: str | None, discipline: str | None = None, on: date | None = None) -> dict:
    """-> {status, note, source}. status: valid | not_on_register | expired | not_checked (no register loaded)."""
    on = on or date.today()
    if not loaded(): return {"status": "not_checked", "note": "No register file loaded (docs/sources_manual/ps_register/*.csv): check the Council's online search and record the result.", "source": None}
    if not name: return {"status": "not_on_register", "note": "author name not given", "source": None}
    hits = [r for r in load() if _n(r["name"]) == _n(name) and (not company or not r.get("company") or _n(r["company"]) == _n(company))]
    if not hits: return {"status": "not_on_register", "note": f"'{name}' not found in the loaded register file(s)", "source": ", ".join(sorted({p.name for p in REG_DIR.glob('*.csv')}))}
    for r in hits:
        vu = r.get("valid_until")
        try: ok = (not vu) or date.fromisoformat(vu) >= on
        except ValueError: ok = True
        if ok: return {"status": "valid", "note": f"found in {r['_file']}" + (f" (registration {r['registration_no']})" if r.get("registration_no") else ""), "source": r["_file"]}
    return {"status": "expired", "note": f"found but valid_until {hits[0].get('valid_until')} is past", "source": hits[0]["_file"]}
