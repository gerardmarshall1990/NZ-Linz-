"""Property Record: create, read, edit facts with an audit trail; CSV import/export."""
import csv, io, json
from typing import Any
from fastapi import HTTPException
from .config import field_catalogue
from .db import conn
from .tiers import ORDER, tier_for, lowest

CONF = list(ORDER)

def coerce(field: str, value: Any):
    spec = field_catalogue()["fields"].get(field)
    if spec is None: raise HTTPException(422, f"unknown field {field!r}")
    t = spec["type"]
    try:
        if t == "int": return int(value)
        if t == "float": return float(value)
        if t == "bool":
            if isinstance(value, bool): return value
            if str(value).lower() in ("true", "yes", "1"): return True
            if str(value).lower() in ("false", "no", "0"): return False
            raise ValueError
        if t == "enum":
            if value not in spec["values"]: raise ValueError
            return value
        if t == "json": return value if not isinstance(value, str) else json.loads(value)
        return str(value)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(422, f"bad value for {field}: {value!r} (type {t}{', ' + '/'.join(spec['values']) if t == 'enum' else ''})")

def set_fact(c, parcel_id: int, field: str, value, source: str, confidence: str, method: str | None = None, note: str | None = None, by: str = "owner"):
    if confidence not in CONF: raise HTTPException(422, f"confidence must be one of {CONF}")
    if not source or not source.strip(): raise HTTPException(422, "source is required for every fact")
    v = coerce(field, value)
    old = c.execute("SELECT value, confidence FROM core.rh_property_fact WHERE parcel_id = %s AND field = %s", (parcel_id, field)).fetchone()
    if old and old["value"] == v and old["confidence"] == confidence: return False
    c.execute("""INSERT INTO core.rh_property_fact (parcel_id, field, value, source, confidence, method, note, updated_by) VALUES (%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                 ON CONFLICT (parcel_id, field) DO UPDATE SET value = EXCLUDED.value, source = EXCLUDED.source, confidence = EXCLUDED.confidence, method = EXCLUDED.method,
                 note = EXCLUDED.note, updated_at = now(), updated_by = EXCLUDED.updated_by""", (parcel_id, field, json.dumps(v), source, confidence, method, note, by))
    c.execute("""INSERT INTO core.rh_property_fact_history (parcel_id, field, old_value, new_value, old_confidence, new_confidence, source, note, changed_by)
                 VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)""", (parcel_id, field, json.dumps(old["value"]) if old else None, json.dumps(v), old["confidence"] if old else None, confidence, source, note, by))
    return True

def get_property(parcel_id: int) -> dict:
    with conn() as c:
        p = c.execute("SELECT * FROM core.rh_property WHERE parcel_id = %s", (parcel_id,)).fetchone()
        if not p: raise HTTPException(404, "no Property Record for this parcel (create it with POST /api/property/{parcel_id})")
        rows = c.execute("SELECT field, value, source, confidence, method, note, updated_at, updated_by FROM core.rh_property_fact WHERE parcel_id = %s ORDER BY field", (parcel_id,)).fetchall()
        facts = {r["field"]: {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items() if k != "field"} for r in rows}
        site = c.execute("""SELECT parcel_id, address, suburb, area_m2::float AS area_m2, zone_name, title_type, title_no, building_count, hazard_flags, overlays, pc120_depends
                            FROM core.sites WHERE parcel_id = %s""", (parcel_id,)).fetchone()
    cat = field_catalogue()
    overall = lowest(f["confidence"] for f in facts.values())
    return {"parcel_id": parcel_id, "site": site, "evidence_level": p["evidence_level"], "created_at": p["created_at"].isoformat(), "facts": facts,
            "catalogue": {g: [{"field": f, **cat["fields"][f], "fact": facts.get(f)} for f in fs] for g, fs in cat["groups"].items()},
            "lowest_confidence": overall, "banner": "Screening only: bedrooms/plans not confirmed" if overall == "ESTIMATED" or (overall is None) else None,
            "note": "Unknown facts are blank. Nothing is defaulted."}

def history(parcel_id: int, field: str | None = None) -> list:
    with conn() as c:
        q = "SELECT field, old_value, new_value, old_confidence, new_confidence, source, note, changed_at, changed_by FROM core.rh_property_fact_history WHERE parcel_id = %s"
        args = [parcel_id]
        if field: q += " AND field = %s"; args.append(field)
        return [{**r, "changed_at": r["changed_at"].isoformat()} for r in c.execute(q + " ORDER BY id DESC LIMIT 500", args).fetchall()]

def export_csv(parcel_id: int) -> str:
    p = get_property(parcel_id); out = io.StringIO(); w = csv.writer(out)
    w.writerow(["field", "value", "source", "confidence", "method", "note"])
    for f, d in p["facts"].items(): w.writerow([f, json.dumps(d["value"]) if isinstance(d["value"], (dict, list)) else d["value"], d["source"], d["confidence"], d.get("method") or "", d.get("note") or ""])
    return out.getvalue()

def import_csv(parcel_id: int, text: str, source: str, dry_run: bool = True) -> dict:
    """CSV with columns field,value[,confidence,note]. Dry run by default: validates every row and reports rejects without writing."""
    rows, rejects = list(csv.DictReader(io.StringIO(text))), []
    ok = []
    for i, r in enumerate(rows, 2):
        try:
            conf = (r.get("confidence") or "DOCUMENTED").upper()
            coerce(r["field"], r["value"]); assert conf in CONF; ok.append((r["field"], r["value"], conf, r.get("note")))
        except Exception as e:  # noqa: BLE001
            rejects.append({"line": i, "field": r.get("field"), "reason": getattr(e, "detail", str(e)) or "bad row"})
    if not dry_run:
        with conn() as c:
            for f, v, conf, note in ok: set_fact(c, parcel_id, f, v, source, conf, "csv import", note)
            c.commit()
    return {"rows": len(rows), "accepted": len(ok), "rejected": rejects, "written": not dry_run}
