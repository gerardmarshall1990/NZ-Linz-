"""Importers for pending or paid feeds (MASTER_SPEC Part 5 section 2): licensed property attributes and sales, rest homes (HealthCERT export), census (population aged 75+). Each works with a sample file the day it arrives: column mapping from
config/importer_mappings.yaml (or a mapping you pass), a DRY RUN that reports row counts, null rates, address match rate against LINZ, rejects with reasons and a sample, and an APPLY that upserts and keeps an import log with the file's SHA-256.
Nothing is scraped, and a file is used only under the licence you hold for it: this tool does not check your licence, so confirm that it allows an AI-queried private database before importing (BLOCKERS 10)."""
import csv, hashlib, io
from datetime import date
from functools import lru_cache
import yaml
from fastapi import HTTPException
from . import listings
from .config import ROOT
from .db import conn

KINDS = ("property_attributes", "sales", "rest_homes", "demographics")

@lru_cache
def mappings() -> dict: return yaml.safe_load((ROOT / "config" / "importer_mappings.yaml").read_text())

def _read(text: str) -> tuple[list[str], list[dict]]:
    rdr = csv.DictReader(io.StringIO(text)); hdr = [h.strip() for h in (rdr.fieldnames or [])]
    rows = []
    for r in rdr:
        bad = None in r         # more fields than headers: an unquoted comma inside a value
        rows.append({**{(k or "").strip(): (v or "").strip() for k, v in r.items() if k is not None and not isinstance(v, list)}, "_malformed": bad})
    return hdr, rows

def resolve(kind: str, hdr: list[str], override: dict | None) -> tuple[dict, list[str]]:
    spec = mappings()[kind]; low = {h.lower(): h for h in hdr}; col = {}; missing = []
    for field, s in spec.items():
        src = (override or {}).get(field)
        if src is None: src = next((low[x.lower()] for x in s["synonyms"] if x.lower() in low), None)
        elif src not in hdr: raise HTTPException(422, f"mapping for {field} names a column {src!r} that is not in the file")
        col[field] = src
        if src is None and s.get("required"): missing.append(field)
    return col, missing

def _conv(v: str, t: str | None):
    if v in ("", None): return None
    if t == "int": return int(float(v.replace(",", "")))
    if t == "float": return float(v.replace(",", "").replace("$", ""))
    if t == "date":
        from datetime import datetime
        for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try: return datetime.strptime(v, f).date()
            except ValueError: pass
        raise ValueError(f"unreadable date {v!r}")
    return v

def run(kind: str, text: str, filename: str | None = None, mapping: dict | None = None, dry_run: bool = True, source: str | None = None) -> dict:
    if kind not in KINDS: raise HTTPException(422, f"kind must be one of {list(KINDS)}")
    if not dry_run and not (source or "").strip(): raise HTTPException(422, "say where the file came from (supplier and licence) to apply it")
    hdr, rows = _read(text); col, missing = resolve(kind, hdr, mapping); sha = hashlib.sha256(text.encode()).hexdigest(); spec = mappings()[kind]
    out = {"kind": kind, "rows": len(rows), "columns_mapped": col, "required_missing": missing, "dry_run": dry_run, "file_sha256": sha}
    if missing: out.update(applied=0, rejected=len(rows), note=f"required column(s) not found: {missing}: pass a mapping"); return out
    parsed, rejects = [], []
    for n, r in enumerate(rows, 2):
        try:
            if r.get("_malformed"): raise ValueError("more values than columns: quote any value that contains a comma")
            v = {f: _conv(r.get(c, ""), spec[f].get("type")) if c else None for f, c in col.items()}
            if any(spec[f].get("required") and v[f] is None for f in spec): raise ValueError("a required value is empty")
            parsed.append((n, v))
        except Exception as e: rejects.append({"row": n, "reason": str(e)[:120]})
    nulls = {f: round(sum(1 for _, v in parsed if v[f] is None) / len(parsed), 3) if parsed else None for f in spec}
    need_match = "address" in spec and kind in ("property_attributes", "sales", "rest_homes"); mr = {"high": 0, "medium": 0, "low": 0, "none": 0}; matched = []
    with conn() as c:
        for n, v in parsed:
            if need_match and v.get("address"):
                m = listings.match_address(c, v["address"], v.get("suburb")); mr[m["confidence"]] += 1; matched.append((n, v, m))
            else: matched.append((n, v, None))
        rate = (mr["high"] + mr["medium"]) / len(parsed) if parsed and need_match else None
        out.update(null_rates=nulls, match=mr if need_match else None, match_rate=round(rate, 3) if rate is not None else None, rejects=rejects[:20], rejected=len(rejects), sample=[v for _, v in parsed[:5]])
        if dry_run: out["applied"] = 0; c.execute("INSERT INTO core.user_import_log (kind, file_sha256, filename, rows, applied, rejected, match_rate, dry_run) VALUES (%s,%s,%s,%s,0,%s,%s,true)", (kind, sha, filename, len(rows), len(rejects), rate)); c.commit(); out["note"] = "dry run: nothing was written"; return out
        applied = 0
        for n, v, m in matched:
            pid = m["parcel_id"] if m and m["confidence"] in ("high", "medium") else None
            if kind == "property_attributes":
                if pid is None: rejects.append({"row": n, "reason": "address not matched to a LINZ parcel with high or medium confidence"}); continue
                c.execute("""INSERT INTO core.user_property_attribute (parcel_id, address_raw, bedrooms, bathrooms, floor_area_m2, storeys, build_year, construction_type, land_use, source, file_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                             ON CONFLICT (parcel_id) DO UPDATE SET address_raw=EXCLUDED.address_raw, bedrooms=EXCLUDED.bedrooms, bathrooms=EXCLUDED.bathrooms, floor_area_m2=EXCLUDED.floor_area_m2, storeys=EXCLUDED.storeys, build_year=EXCLUDED.build_year,
                             construction_type=EXCLUDED.construction_type, land_use=EXCLUDED.land_use, source=EXCLUDED.source, file_sha256=EXCLUDED.file_sha256, loaded_at=now()""",
                          (pid, v["address"], v["bedrooms"], v["bathrooms"], v["floor_area_m2"], v["storeys"], v["build_year"], v["construction_type"], v["land_use"], source, sha))
            elif kind == "sales": c.execute("INSERT INTO core.user_sale (parcel_id, address_raw, sale_date, price, source, file_sha256) VALUES (%s,%s,%s,%s,%s,%s)", (pid, v["address"], v["sale_date"], v["price"], source, sha))
            elif kind == "rest_homes":
                pt = c.execute("SELECT ST_X(ST_Transform(ST_Centroid(geom),4326)) lon, ST_Y(ST_Transform(ST_Centroid(geom),4326)) lat FROM core.sites WHERE parcel_id=%s", (pid,)).fetchone() if pid else None
                c.execute("INSERT INTO core.user_rest_home (name, address_raw, parcel_id, beds, lon, lat, source, file_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (v["name"], v["address"], pid, v["beds"], pt["lon"] if pt else None, pt["lat"] if pt else None, source, sha))
            else: c.execute("""INSERT INTO core.user_demographic (area_name, year, population_75_plus, source, file_sha256) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (area_name, year) DO UPDATE SET population_75_plus=EXCLUDED.population_75_plus, source=EXCLUDED.source, file_sha256=EXCLUDED.file_sha256, loaded_at=now()""",
                                (v["area_name"], v["year"], v["population_75_plus"], source, sha))
            applied += 1
        c.execute("INSERT INTO core.user_import_log (kind, file_sha256, filename, rows, applied, rejected, match_rate, dry_run) VALUES (%s,%s,%s,%s,%s,%s,%s,false)", (kind, sha, filename, len(rows), applied, len(rejects), rate)); c.commit()
    out.update(applied=applied, rejected=len(rejects), rejects=rejects[:20], note="applied"); return out

def log() -> list[dict]:
    with conn() as c: return [{**r, "at": r["at"].isoformat(), "match_rate": float(r["match_rate"]) if r["match_rate"] is not None else None} for r in c.execute("SELECT * FROM core.user_import_log ORDER BY id DESC LIMIT 50").fetchall()]
