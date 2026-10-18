"""Services module (MASTER_SPEC Part 2 section 6), licence-aware.
- Watercare network data is non-commercial / no-derivatives: it is NOT loaded, no distance is computed from it; the screen links to Watercare and holds manual fields you fill from their viewer.
- Healthy Waters stormwater (open, CC BY 4.0) and Vector's indicative capacity map are not loaded yet (discovery pending): manual fields too.
- Capacity is ALWAYS UNKNOWN unless a confirmation letter is uploaded and linked; 'available' is never stated.
- Cost lines come from config/services_rates.yaml (blank) and your inputs."""
import json
from functools import lru_cache
import yaml
from fastapi import HTTPException
from .config import ROOT
from .db import conn

FIELDS = {"water_main_dist_m": float, "water_main_dia_mm": float, "wastewater_dist_m": float, "wastewater_dia_mm": float, "stormwater_dist_m": float, "power_flag": str, "notes": str}
CAPACITY = ("UNKNOWN", "INDICATIVE_OK", "INDICATIVE_CONSTRAINED", "CONFIRMED")
SOURCES = [
    {"key": "watercare", "label": "Watercare water and wastewater network", "status": "not_loaded", "licence": "non-commercial / no-derivatives: written permission needed before loading", "action": "Use Watercare's own viewer (watercare.co.nz) and enter distances and diameters by hand below."},
    {"key": "healthy_waters", "label": "Auckland Council Healthy Waters stormwater network", "status": "not_loaded", "licence": "open (CC BY 4.0)", "action": "Layer not yet discovered and ingested (BLOCKERS 27); enter the nearest stormwater pipe by hand."},
    {"key": "vector", "label": "Vector network capacity map", "status": "manual", "licence": "indicative map only", "action": "View on Vector's site; record what it shows. Indicative only: never a confirmation."},
]
CONFIRMATIONS = ["Watercare: written confirmation of water and wastewater connection and capacity", "Vector (or the local lines company): connection application and capacity", "Healthy Waters: stormwater management and flood requirements",
                 "Fire engineer: sprinkler flow and pressure (care sites only)", "Surveyor / civil engineer: levels, connection points and whether a pump or private drain is needed"]
CONSENT_TRIGGERS = ["Watercare connection / network approval", "Vector connection application", "Engineering plan approval and vested assets, where applicable"]

@lru_cache
def rates() -> dict: return yaml.safe_load((ROOT / "config" / "services_rates.yaml").read_text())["lines"]

def get(parcel_id: int) -> dict:
    with conn() as c:
        site = c.execute("SELECT parcel_id, address FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone()
        if not site: raise HTTPException(404, "no such parcel")
        r = c.execute("SELECT data, updated_at FROM core.user_site_services WHERE parcel_id=%s", (parcel_id,)).fetchone()
    d = (r or {}).get("data") or {}; known = [k for k in FIELDS if k != "notes" and d.get(k) is not None]
    cap = d.get("capacity_status", "UNKNOWN"); conf = d.get("confirmation_upload_id")
    if cap == "CONFIRMED" and not conf: cap = "UNKNOWN"
    lines = [{"line": k, "unit": v["unit"], "rate": v["value"], "status": "needs rate" if v["value"] is None else "ok", "source": v["source"]} for k, v in rates().items()]
    return {"parcel_id": parcel_id, "address": site["address"], "sources": SOURCES, "manual": d, "capacity_status": cap, "capacity_note": "Capacity is UNKNOWN until a written confirmation is uploaded and linked." if cap != "CONFIRMED" else "Confirmed by an uploaded letter (see the upload): re-check its date.",
            "completeness": f"{len(known)}/{len(FIELDS) - 1} manual fields entered", "cost_lines": lines, "confirmations_needed": CONFIRMATIONS, "consent_triggers": CONSENT_TRIGGERS,
            "last_updated": r["updated_at"].isoformat() if r else None, "label": "Screening only. Distances are what you entered from the providers' viewers; nothing here states that a connection or capacity is available."}

def put(parcel_id: int, data: dict) -> dict:
    get(parcel_id); clean = {}
    for k, v in data.items():
        if k == "capacity_status":
            if v not in CAPACITY: raise HTTPException(422, f"capacity_status must be one of {list(CAPACITY)}")
            clean[k] = v
        elif k == "confirmation_upload_id":
            if v is not None:
                with conn() as c:
                    u = c.execute("SELECT id FROM core.rh_upload WHERE id=%s AND parcel_id=%s", (v, parcel_id)).fetchone()
                if not u: raise HTTPException(422, "that upload does not belong to this parcel")
            clean[k] = v
        elif k in FIELDS:
            if v is None: clean[k] = None
            elif FIELDS[k] is float:
                if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0: raise HTTPException(422, f"{k} must be a non-negative number")
                clean[k] = float(v)
            else: clean[k] = str(v)[:500]
        elif k == "last_verified": clean[k] = str(v)
        else: raise HTTPException(422, f"unknown services field {k!r}")
    if clean.get("capacity_status") == "CONFIRMED":
        with conn() as c: cur = (c.execute("SELECT data FROM core.user_site_services WHERE parcel_id=%s", (parcel_id,)).fetchone() or {}).get("data") or {}
        if not (clean.get("confirmation_upload_id") or cur.get("confirmation_upload_id")): raise HTTPException(422, "CONFIRMED needs the confirmation letter uploaded and linked (confirmation_upload_id)")
    with conn() as c:
        cur = (c.execute("SELECT data FROM core.user_site_services WHERE parcel_id=%s", (parcel_id,)).fetchone() or {}).get("data") or {}
        c.execute("""INSERT INTO core.user_site_services (parcel_id, data) VALUES (%s,%s::jsonb) ON CONFLICT (parcel_id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()""", (parcel_id, json.dumps({**cur, **clean}))); c.commit()
    return get(parcel_id)
