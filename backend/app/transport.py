"""Vehicle access check for development scenarios, from AUP Chapter E27 (config/transport_rules.yaml). Width is tested; gradient, crossing approval and passing bays are flagged for a professional."""
from functools import lru_cache
import yaml
from .config import ROOT

@lru_cache
def rules() -> dict: return yaml.safe_load((ROOT / "config/transport_rules.yaml").read_text())

def row_for(spaces: int) -> dict:
    for r in rules()["width_rows"]:
        if r["max_spaces"] is None or spaces <= r["max_spaces"]: return r

def access_width_m(access) -> float | None:
    """Width of the driveway polygon: the shorter side of its minimum rotated rectangle."""
    if access is None or access.is_empty: return None
    c = list(access.minimum_rotated_rectangle.exterior.coords)[:4]
    sides = [((c[i][0] - c[(i + 1) % 4][0]) ** 2 + (c[i][1] - c[(i + 1) % 4][1]) ** 2) ** 0.5 for i in range(2)]
    return min(sides)

def check(units: int, access) -> dict:
    """-> {status, measured, required, unit, ref, note}"""
    R = rules(); crossing = R["crossing_note"]
    if access is None or access.is_empty:
        return {"status": "NEEDS_PROFESSIONAL", "measured": None, "required": None, "unit": None, "ref": "E27.6.4.2", "note": "no shared driveway in this layout (direct frontage): vehicle crossing needs Auckland Transport approval; gradient needs ground levels. " + crossing}
    spaces = units * R["spaces_per_unit_assumed"]; row = row_for(spaces); w = access_width_m(access)
    note = (f"assumed {R['spaces_per_unit_assumed']} parking spaces per unit = {spaces} spaces served, so {row['ref']} applies: a clear corridor of at least {row['corridor_clear_m']:g} m (formed width {row['formed_m']:g} m). "
            f"Not testable here: gradient ({R['gradient']['ref']}: {R['gradient']['other_residential']['max']} for other residential access, {R['gradient']['rear_site']['max']} for one rear site; needs ground levels), "
            f"passing bays if the access is over {R['passing_bay']['length_over_m']} m long, and vehicle crossing approval from Auckland Transport.")
    if w is not None and w + 1e-9 < row["corridor_clear_m"]:
        return {"status": "FAIL", "measured": round(w, 2), "required": row["corridor_clear_m"], "unit": "m clear corridor", "ref": row["ref"], "note": note}
    return {"status": "NEEDS_PROFESSIONAL", "measured": round(w, 2) if w is not None else None, "required": row["corridor_clear_m"], "unit": "m clear corridor (width passes; gradient and crossing need a professional)", "ref": row["ref"], "note": note}
