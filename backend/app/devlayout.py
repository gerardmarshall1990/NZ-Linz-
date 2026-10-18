"""Development layout engine (MASTER_SPEC Part 2 section 4), deterministic: buildable envelope = parcel minus yard bands; units (each with its ground-floor outdoor living space) packed in rows over a grid of orientations, offsets and access
strategies (none, central driveway from the front, side driveway); every candidate and every unit count is run through the rules evaluator; compliant scenarios (zero FAIL) are ranked; the best near-miss and the binding constraint are kept.
Unit sizes and the driveway width are INPUTS (blank = not run). No rule value is invented: yards, coverage, outdoor living space come from the rules corpus; a rule that is not loaded makes the check UNKNOWN."""
import math
from shapely import affinity
from shapely.geometry import box, LineString, Polygon
from shapely.ops import unary_union
from . import devrules

def principal_angle(poly: Polygon) -> float:
    pts = list(poly.minimum_rotated_rectangle.exterior.coords); dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
    return math.degrees(math.atan2(dy, dx))

def envelope(parcel: Polygon, R: dict, B: dict) -> Polygon:
    cuts = []
    for key, es in (("yard_front_min", B["front"]), ("yard_side_min", B["side"]), ("yard_rear_min", B["rear"])):
        r = R.get(key)
        if r:
            for e in es: cuts.append(e.buffer(r["v"], cap_style="flat"))
    env = parcel.difference(unary_union(cuts)) if cuts else parcel
    if env.is_empty: return Polygon()
    if env.geom_type != "Polygon": env = max(env.geoms, key=lambda g: g.area)
    return env

def _cell(unit: dict, R: dict):
    w, d = unit["width_m"], unit["depth_m"]; a, m = R.get("ols_ground_floor_min_area"), R.get("ols_ground_floor_min_dimension")
    if a and m: cw = max(w, m["v"]); od = max(a["v"] / cw, m["v"]); return cw, d + od, (cw - w) / 2, d, cw, od
    return w, d, 0.0, d, 0.0, 0.0

def _pack(env: Polygon, unit: dict, R: dict, theta: float, xo: float, yo: float, ols_front: bool, blocked: Polygon | None) -> list[dict]:
    c = env.centroid; e = affinity.rotate(env, -theta, origin=c); bl = affinity.rotate(blocked, -theta, origin=c) if blocked is not None else None
    cw, ch, ux, ud, ow, od = _cell(unit, R); minx, miny, maxx, maxy = e.bounds; out = []
    y = miny + yo * ch
    while y + ch <= maxy + 1e-9:
        x = minx + xo * cw
        while x + cw <= maxx + 1e-9:
            cell = box(x, y, x + cw, y + ch)
            if e.buffer(1e-6).contains(cell) and (bl is None or not cell.intersects(bl)):
                fy = y + (od if ols_front else 0)       # ols_front: outdoor space on the low-y side, building on the high-y side
                fp = box(x + ux, fy, x + ux + unit["width_m"], fy + ud)
                ols = box(x, y if ols_front else y + ud, x + cw, (y + od) if ols_front else y + ch) if od else None
                out.append((fp, ols)); 
            x += cw
        y += ch
    res = []
    for i, (fp, ols) in enumerate(out, 1):
        res.append({"id": f"u{i}", "footprint": affinity.rotate(fp, theta, origin=c), "ols": affinity.rotate(ols, theta, origin=c) if ols is not None else None,
                    "height_m": unit["height_m"], "wall_height_m": unit.get("wall_height_m"), "gfa_m2": unit["gfa_m2"], "bedrooms": unit.get("bedrooms", 2)})
    return res

def access_options(parcel: Polygon, env: Polygon, B: dict, width: float | None) -> list:
    if not width or not B["front"] or env.is_empty: return [("none", None)]
    f = B["front"][0]; mid = f.interpolate(0.5, normalized=True); (x1, y1), (x2, y2) = f.coords[0], f.coords[-1]
    nx, ny = (y2 - y1), -(x2 - x1); L = math.hypot(nx, ny) or 1; nx, ny = nx / L, ny / L
    probe = LineString([(mid.x, mid.y), (mid.x + nx * 500, mid.y + ny * 500)])
    if not probe.intersects(parcel) or (probe.intersection(parcel).length < 1):       # flip the normal to point into the parcel
        nx, ny = -nx, -ny; probe = LineString([(mid.x, mid.y), (mid.x + nx * 500, mid.y + ny * 500)])
    spine = probe.intersection(parcel); spine = spine if spine.geom_type == "LineString" else max(spine.geoms, key=lambda g: g.length)
    centre = spine.buffer(width / 2, cap_style="flat").intersection(parcel)
    side = max(B["side"], key=lambda e: e.length, default=None); sidestrip = side.buffer(width, cap_style="flat").intersection(parcel) if side is not None else None
    return [("none", None), ("central driveway", centre)] + ([("side driveway", sidestrip)] if sidestrip is not None and not sidestrip.is_empty else [])

def candidates(parcel: Polygon, zone: str, unit: dict, access_width: float | None, front_point=None, R: dict | None = None) -> dict:
    R = R if R is not None else devrules.zone_rules(zone); B = devrules.classify_boundaries(parcel, front_point); env = envelope(parcel, R, B)
    theta0 = principal_angle(parcel); thetas = sorted({round(theta0 % 180, 3), round((theta0 + 90) % 180, 3), 0.0}); seen = {}; out = []
    for acc_label, acc in access_options(parcel, env, B, access_width):
        for th in thetas:
            for xo in (0.0, 0.5):
                for yo in (0.0, 0.5):
                    for of in (False, True):
                        placed = _pack(env, unit, R, th, xo, yo, of, acc)
                        if not placed: continue
                        for k in range(len(placed), 0, -1):
                            if access_width and acc is None and k > 1: continue          # several units need a driveway: a layout with no driveway is only offered for a single unit
                            units = placed[:k]; key = (k, tuple(sorted((round(u["footprint"].centroid.x, 1), round(u["footprint"].centroid.y, 1)) for u in units)), acc is not None)
                            if key in seen: continue
                            seen[key] = 1
                            sc = {"units": units, "access": acc, "meta": {"theta": th, "x_off": xo, "y_off": yo, "ols_front": of, "access": acc_label, "max_fit": len(placed)}}
                            ev = devrules.evaluate(parcel, zone, sc, front_point, R); sc["checks"] = ev["checks"]; sc["summary"] = devrules.summarize(ev["checks"]); sc["unit_count"] = k
                            out.append(sc)
                            if sc["summary"]["counts"]["FAIL"] == 0: break         # fewer units of this arrangement are also compliant: keep the largest only
    return {"envelope": env, "boundaries": B, "candidates": out, "rules_used": sorted(k for k in R)}

def best(parcel, zone, unit, access_width, front_point=None, R=None) -> dict:
    cs = candidates(parcel, zone, unit, access_width, front_point, R); ok = [c for c in cs["candidates"] if c["summary"]["counts"]["FAIL"] == 0]; bad = [c for c in cs["candidates"] if c["summary"]["counts"]["FAIL"] > 0]
    ok.sort(key=lambda c: (-c["unit_count"], c["summary"]["counts"]["UNKNOWN"], c["summary"]["counts"]["NEEDS_PROFESSIONAL"]))
    bad.sort(key=lambda c: (c["summary"]["counts"]["FAIL"], -c["unit_count"]))
    return {**cs, "compliant": ok, "near_misses": bad[:3]}

def binding_constraint(res: dict) -> dict:
    """Why not one more unit: if the best compliant scenario used every unit that physically fitted, the envelope is the limit; otherwise the failing rules of the next unit count."""
    if not res["compliant"]: return {"binding": [f"{c['id']}" for c in (res["near_misses"][0]["checks"] if res["near_misses"] else []) if c["status"] == "FAIL"], "explanation": "no compliant scenario: these rules fail in the nearest miss"}
    top = res["compliant"][0]; more = [c for c in res["candidates"] if c["unit_count"] == top["unit_count"] + 1]
    if not more: return {"binding": ["buildable_envelope"], "explanation": f"no arrangement fits {top['unit_count'] + 1} units inside the envelope (parcel minus yards{' and the driveway' if top['access'] is not None else ''}): space is the limit"}
    nxt = min(more, key=lambda c: c["summary"]["counts"]["FAIL"]); fails = sorted({c["id"] for c in nxt["checks"] if c["status"] == "FAIL"})
    return {"binding": fails or ["unknown"], "explanation": f"{top['unit_count'] + 1} units fit physically but the nearest arrangement breaks: {', '.join(fails) or 'unknown'}"}

def fit_units(parcel, zone, unit, access_width=None, front_point=None, R=None) -> dict:
    r = best(parcel, zone, unit, access_width, front_point, R); top = r["compliant"][0] if r["compliant"] else None
    return {"max_compliant_units": top["unit_count"] if top else 0, "physically_fits": top["meta"]["max_fit"] if top else (r["near_misses"][0]["unit_count"] if r["near_misses"] else 0), "binding": binding_constraint(r)}

def _equal_strips(poly: Polygon, n: int) -> list:
    """Cut the parcel into n strips of equal area, perpendicular to its long axis (bisection on the cut position)."""
    if n <= 1: return [poly]
    ang = principal_angle(poly); c = poly.centroid; rp = affinity.rotate(poly, -ang, origin=c); minx, miny, maxx, maxy = rp.bounds; target = rp.area / n; out = []; rest = rp; x0 = minx
    for _ in range(n - 1):
        lo, hi = x0, maxx
        for _ in range(60):
            mid = (lo + hi) / 2; left = rest.intersection(box(minx - 1, miny - 1, mid, maxy + 1))
            if left.area < target: lo = mid
            else: hi = mid
        cut = rest.intersection(box(minx - 1, miny - 1, hi, maxy + 1)); rest = rest.difference(box(minx - 1, miny - 1, hi, maxy + 1)); x0 = hi
        out.append(cut)
    out.append(rest)
    return [affinity.rotate(g if g.geom_type == "Polygon" else max(g.geoms, key=lambda q: q.area), ang, origin=c) for g in out if not g.is_empty]

def subdivision_yield(parcel: Polygon, zone: str, R: dict | None = None) -> dict:
    """Upper bound of lots by the minimum net site area rule, and a bisection layout. Frontage, shape factor and access are NOT checked (not in the corpus): the result is an upper bound for a person to confirm."""
    R = R if R is not None else devrules.zone_rules(zone); r = R.get("min_net_site_area_vacant_site_parent_lt_1ha")
    if not r: return {"status": "UNKNOWN", "note": "minimum net site area rule not loaded for this zone"}
    if parcel.area >= 10000: return {"status": "NEEDS_PROFESSIONAL", "note": "parent site is 1 ha or more: a different rule set applies (averaging); not evaluated here"}
    n = int(parcel.area // r["v"]); lots = _equal_strips(parcel, n) if n >= 1 else []
    ok = [l for l in lots if l.area >= r["v"]]
    return {"status": "NEEDS_PROFESSIONAL", "max_lots_by_area": n, "lots_in_layout": len(ok), "min_net_site_area_m2": r["v"], "rule": r["section_ref"], "owner_verified": bool(r["owner_verified"]), "lot_areas_m2": [round(l.area, 1) for l in ok],
            "lots": [list(l.exterior.coords) for l in ok], "note": "area rule only (vacant site, parent site under 1 ha): frontage, shape factor, access and servicing are not evaluated; a licensed surveyor confirms"}
