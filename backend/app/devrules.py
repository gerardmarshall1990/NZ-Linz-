"""Rules evaluator for development scenarios (MASTER_SPEC Part 2 section 3.2): deterministic geometry checks against the structured rules in analytics.rules (operative plan). Every check carries the measured value, the required value,
the rule reference, whether YOU have confirmed that rule value (owner_verified) and an honest status: PASS, FAIL, NEEDS_PROFESSIONAL, UNKNOWN, NOT_APPLICABLE. A rule that is not in the corpus is UNKNOWN ('requirement not loaded'): never PASS.
Simplifications are stated in each check's note and in the engine's definitions below; they are part of what 'PASS' means here.
Definitions: the front boundary is the parcel edge nearest the address point (assumed: a surveyor confirms); the rear boundary is the non-front edge furthest from the front; the others are side boundaries. Height in relation to boundary
is tested at two points per unit against each non-front boundary: the nearest wall at its wall height and the ridge half a footprint further in at the ridge height (symmetric roof), allowed height = start height + tan(angle) x distance."""
import math
from shapely.geometry import LineString, Point, Polygon
from .db import conn

ST = ("PASS", "FAIL", "NEEDS_PROFESSIONAL", "UNKNOWN", "NOT_APPLICABLE")

def zone_rules(zone: str) -> dict:
    with conn() as c:
        rows = c.execute("""SELECT parameter, operator, value_num::float AS v, unit, section_ref, owner_verified, last_verified, source_url, plan_version_id FROM analytics.rules
                            WHERE zone = %s AND status = 'operative' AND value_num IS NOT NULL ORDER BY section_ref""", (zone,)).fetchall()
    return {r["parameter"]: r for r in rows}

def activity_rows(zone: str, patterns: tuple = ("Dwellings%", "Dwelling%", "Supported residential care%", "Healthcare facilities%", "Subdivision%")) -> list[dict]:
    with conn() as c:
        return c.execute("""SELECT activity, status_class, section_ref FROM analytics.rules WHERE topic='activity_status' AND status='operative' AND zone=%s AND activity ILIKE ANY (%s) ORDER BY section_ref LIMIT 25""", (zone, list(patterns))).fetchall()

def edges(poly: Polygon) -> list[LineString]:
    pts = list(poly.exterior.coords); return [LineString([pts[i], pts[i + 1]]) for i in range(len(pts) - 1)]

def classify_boundaries(parcel: Polygon, front_point: tuple | None) -> dict:
    """-> {'front': [edges], 'rear': [edges], 'side': [edges], 'assumed': bool, 'note': str}"""
    es = [e for e in edges(parcel) if e.length > 0.5]
    if not es: return {"front": [], "rear": [], "side": [], "assumed": True, "note": "degenerate parcel"}
    if front_point is None: front = max(es, key=lambda e: e.length); note = "no address point on the parcel: the longest edge is assumed to be the front"
    else: fp = Point(front_point); front = min(es, key=lambda e: e.distance(fp)); note = "front boundary = edge nearest the address point (assumed; a surveyor confirms)"
    others = [e for e in es if e is not front]
    mid = front.interpolate(0.5, normalized=True)
    rear = max(others, key=lambda e: e.distance(mid)) if others else None
    return {"front": [front], "rear": [rear] if rear else [], "side": [e for e in others if e is not rear], "assumed": True, "note": note}

def _chk(id_, topic, status, measured, required, unit, rule, note, geom=None, extra=None):
    return {"id": id_, "topic": topic, "status": status, "measured": measured, "required": required, "unit": unit, "rule": (rule or {}).get("section_ref") if isinstance(rule, dict) else rule,
            "owner_verified": bool((rule or {}).get("owner_verified")) if isinstance(rule, dict) else None, "last_verified": str((rule or {}).get("last_verified") or "") if isinstance(rule, dict) else None, "note": note, "evidence": geom, **(extra or {})}

def _need(R, name): return R.get(name)
def _unknown(id_, topic, name): return _chk(id_, topic, "UNKNOWN", None, None, None, None, f"requirement not loaded ({name} is not in the rules corpus for this zone): never counted as a pass")

def min_dim(poly: Polygon) -> float:
    r = poly.minimum_rotated_rectangle; pts = list(r.exterior.coords); a, b = Point(pts[0]).distance(Point(pts[1])), Point(pts[1]).distance(Point(pts[2])); return min(a, b)

def evaluate(parcel: Polygon, zone: str, scenario: dict, front_point: tuple | None = None, R: dict | None = None) -> dict:
    """scenario: {"units": [{"id", "footprint": Polygon, "height_m", "gfa_m2", "bedrooms", "ols": Polygon|None}], "access": Polygon|None}"""
    R = R if R is not None else zone_rules(zone)
    B = classify_boundaries(parcel, front_point); units = scenario["units"]; acc = scenario.get("access"); out = []; site = parcel.area
    # yards
    for key, name, edges_ in (("yard_front_min", "front", B["front"]), ("yard_side_min", "side", B["side"]), ("yard_rear_min", "rear", B["rear"])):
        r = _need(R, key)
        if not r: out.append(_unknown(f"yard_{name}", "Yards", key)); continue
        if not edges_ or not units: out.append(_chk(f"yard_{name}", "Yards", "NOT_APPLICABLE", None, r["v"], r["unit"], r, f"no {name} boundary or no buildings")); continue
        d = min(u["footprint"].distance(e) for u in units for e in edges_)
        out.append(_chk(f"yard_{name}", "Yards", "PASS" if d + 1e-9 >= r["v"] else "FAIL", round(d, 2), r["v"], r["unit"], r, B["note"]))
    # coverage
    bld = sum(u["footprint"].area for u in units)
    r = _need(R, "building_coverage_max_pct")
    out.append(_unknown("building_coverage", "Coverage", "building_coverage_max_pct") if not r else _chk("building_coverage", "Coverage", "PASS" if bld / site * 100 <= r["v"] + 1e-9 else "FAIL", round(bld / site * 100, 1), r["v"], "% of site area", r, "net site area taken as the whole parcel (no access-lot deduction)"))
    paved = bld + (acc.area if acc is not None else 0)
    r = _need(R, "impervious_max_pct")
    if not r: out.append(_unknown("impervious", "Coverage", "impervious_max_pct"))
    else:
        m = paved / site * 100
        out.append(_chk("impervious", "Coverage", "FAIL" if m > r["v"] + 1e-9 else "NEEDS_PROFESSIONAL", round(m, 1), r["v"], "% of site area", r, "buildings and access only are modelled (a lower bound): paths, patios and parking are not, so a pass cannot be stated"))
    r = _need(R, "landscaped_min_pct")
    if not r: out.append(_unknown("landscaped", "Coverage", "landscaped_min_pct"))
    else:
        m = (site - paved) / site * 100
        out.append(_chk("landscaped", "Coverage", "FAIL" if m < r["v"] - 1e-9 else "NEEDS_PROFESSIONAL", round(m, 1), r["v"], "% of site area", r, "upper bound (all non-built area counted): hard surfaces not modelled, so a pass cannot be stated"))
    # height and HIRB
    r = _need(R, "building_height_max")
    if not r: out.append(_unknown("height", "Height", "building_height_max"))
    elif not units: out.append(_chk("height", "Height", "NOT_APPLICABLE", None, r["v"], r["unit"], r, "no buildings"))
    else:
        h = max(u["height_m"] for u in units); out.append(_chk("height", "Height", "PASS" if h <= r["v"] + 1e-9 else "FAIL", h, r["v"], r["unit"], r, "unit height is an input; roof form not modelled"))
    ang, start = _need(R, "hirb_angle"), _need(R, "hirb_start_height")
    if not (ang and start): out.append(_unknown("hirb", "Height in relation to boundary", "hirb_angle/hirb_start_height"))
    elif not units: out.append(_chk("hirb", "Height in relation to boundary", "NOT_APPLICABLE", None, None, None, ang, "no buildings"))
    else:
        worst = None
        for u in units:
            wall = u.get("wall_height_m") or u["height_m"]
            for e in B["side"] + B["rear"]:
                d = u["footprint"].distance(e); half = min(u["footprint"].bounds[2] - u["footprint"].bounds[0], u["footprint"].bounds[3] - u["footprint"].bounds[1]) / 2
                for label, hh, dd in (("wall", wall, d), ("ridge", u["height_m"], d + half)):
                    allowed = start["v"] + dd * math.tan(math.radians(ang["v"])); gap = allowed - hh
                    if worst is None or gap < worst[0]: worst = (gap, label, allowed, hh)
        out.append(_chk("hirb", "Height in relation to boundary", "PASS" if worst is None or worst[0] >= -1e-9 else "FAIL", None if worst is None else round(worst[3], 2), None if worst is None else round(worst[2], 2), "m (height vs allowed at the tightest point)", ang,
                        "tested at the nearest wall (wall height) and at the ridge (half the footprint further in), assuming a symmetric roof; with no wall height input the full height is used at the wall (conservative); the alternative HIRB option is not modelled"))
    # outdoor living space, dwelling floor area
    a, m_ = _need(R, "ols_ground_floor_min_area"), _need(R, "ols_ground_floor_min_dimension")
    if not (a and m_): out.append(_unknown("outdoor_living", "Outdoor living space", "ols_ground_floor_min_area/min_dimension"))
    else:
        bad = [u["id"] for u in units if not u.get("ols") or u["ols"].area + 1e-9 < a["v"] or min_dim(u["ols"]) + 1e-9 < m_["v"]]
        out.append(_chk("outdoor_living", "Outdoor living space", "FAIL" if bad else ("PASS" if units else "NOT_APPLICABLE"), None, a["v"], "m2 and min dimension %.1f m" % m_["v"], a, ("units without compliant ground-floor space: " + ", ".join(map(str, bad))) if bad else "each unit has a ground-floor space meeting area and minimum dimension (sun, privacy and slope not assessed)"))
    s1, s2 = _need(R, "dwelling_min_net_floor_area_studio"), _need(R, "dwelling_min_net_floor_area_1br_plus")
    if not (s1 and s2): out.append(_unknown("dwelling_size", "Dwelling size", "dwelling_min_net_floor_area_*"))
    else:
        bad = [u["id"] for u in units if u["gfa_m2"] < (s1["v"] if u.get("bedrooms", 1) == 0 else s2["v"])]
        out.append(_chk("dwelling_size", "Dwelling size", "FAIL" if bad else ("PASS" if units else "NOT_APPLICABLE"), None, s2["v"], "m2 net floor area (gross used)", s2, ("too small: " + ", ".join(map(str, bad))) if bad else "gross floor area input used as net floor area (a net figure is lower: designer confirms)"))
    # judgement rules
    for pid, topic, keys in (("outlook", "Outlook", [k for k in R if k.startswith("outlook_")]), ("daylight", "Daylight", [k for k in R if k.startswith("daylight")])):
        if keys: out.append(_chk(pid, topic, "NEEDS_PROFESSIONAL", None, None, None, R[keys[0]], "design assessment: " + "; ".join(f"{k} {R[k]['operator']} {R[k]['v']:g} {R[k]['unit'] or ''}" for k in keys[:6])))
        else: out.append(_unknown(pid, topic, pid))
    # access: no vehicle access standard is loaded
    out.append(_chk("vehicle_access", "Access", "UNKNOWN", None, None, None, None, "driveway / JOAL width and gradient standards (transport chapter) are not in the rules corpus yet: never counted as a pass"))
    return {"checks": out, "boundaries": {k: [list(e.coords) for e in v] for k, v in B.items() if isinstance(v, list)}, "boundary_note": B["note"]}

def summarize(checks: list[dict]) -> dict:
    c = {s: sum(1 for x in checks if x["status"] == s) for s in ST}
    unverified = sorted({x["rule"] for x in checks if x["rule"] and x["owner_verified"] is False})
    badge = "does_not_comply" if c["FAIL"] else ("rules_checked" if not c["UNKNOWN"] else "incomplete")
    return {"counts": c, "badge": badge, "unconfirmed_rule_values": unverified,
            "badge_label": {"does_not_comply": "Does not comply", "rules_checked": "Rules-checked (no failures found)", "incomplete": "Incomplete: some rules could not be evaluated"}[badge],
            "note": "Rule values come from the operative plan text in the corpus and are not yet confirmed by you (owner_verified false): confirm them on the key standards page before relying on a result." if unverified else None}
