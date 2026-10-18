"""Validation gate settings (MASTER_SPEC Part 5 section 4): the owner's tolerance and the 3 to 5 properties chosen for the calibration check. Both stay blank until the owner sets them."""
from fastapi import HTTPException
from . import settings
from .db import conn

def get_config() -> dict:
    s = settings.stored(); return {"tolerance_pct": s.get("validation:tolerance_pct"), "properties": s.get("validation:properties") or []}

def set_config(tolerance_pct: float | None, properties: list[int] | None) -> dict:
    with conn() as c:
        if tolerance_pct is not None or properties is None:
            if tolerance_pct is not None and (isinstance(tolerance_pct, bool) or tolerance_pct < 0): raise HTTPException(422, "tolerance must be a non-negative number")
            if tolerance_pct is not None: settings._put(c, "validation:tolerance_pct", tolerance_pct)
        if properties is not None:
            if not 0 <= len(properties) <= 5 or any(not isinstance(p, int) for p in properties): raise HTTPException(422, "choose up to 5 parcel ids")
            settings._put(c, "validation:properties", properties)
        c.commit()
    return get_config()
