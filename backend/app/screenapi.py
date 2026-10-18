"""Queries over analytics.rh_screen: filter and sort any column server-side, map points, polygon / radius search, suburb analytics, saved shortlists with an audit trail and a re-run diff, CSV / XLSX export.
Every row carries its confidence tier; filters can restrict to Confirmed or Documented only. Natural hazard flags are information only for conversions: the 'no_hazard_flag' filter is your preference, not a rule."""
import csv, io, json, math
from fastapi import HTTPException
from . import screen
from .db import conn

COLS = ["parcel_id", "address", "suburb", "zone", "title_type", "lon", "lat", "building_count", "footprint_m2", "gfa_est_m2", "beds_base", "beds_tier", "beds_source", "retrofit_est", "profit_before_rent_annual", "walk_away_rent",
        "min_beds_minimum", "min_beds_target", "too_small", "effort_points", "profit_per_effort", "hazard_flags", "uses_placeholders", "needs_input", "last_computed"]
SORT = set(COLS)
TIERS = ("ESTIMATED", "DOCUMENTED", "CONFIRMED")

def _where(f: dict) -> tuple[str, list]:
    q, a = ["TRUE"], []
    for k, col, op in (("min_beds", "beds_base", ">="), ("max_beds", "beds_base", "<="), ("min_profit", "profit_before_rent_annual", ">="), ("min_walk_away_rent", "walk_away_rent", ">=")):
        if f.get(k) is not None: q.append(f"{col} {op} %s"); a.append(f[k])
    if f.get("tiers"):
        if any(t not in TIERS for t in f["tiers"]): raise HTTPException(422, f"tiers must be from {list(TIERS)}")
        q.append("beds_tier = ANY(%s)"); a.append(list(f["tiers"]))
    for k, col in (("zone", "zone"), ("suburb", "suburb"), ("title_type", "title_type")):
        if f.get(k): q.append(f"lower({col}) = lower(%s)"); a.append(f[k])
    if f.get("exclude_too_small"): q.append("(too_small IS NOT TRUE)")
    if f.get("no_hazard_flag"): q.append("hazard_flags IS NULL")
    if f.get("single_title"): q.append("lower(coalesce(title_type,'')) IN ('freehold','fee simple')")
    if f.get("bbox"):
        x0, y0, x1, y1 = f["bbox"]; q.append("lon BETWEEN %s AND %s AND lat BETWEEN %s AND %s"); a += [x0, x1, y0, y1]
    if f.get("radius"):
        lat, lon, km = f["radius"]; dlat = km / 111.0; dlon = km / (111.0 * max(0.2, math.cos(math.radians(lat))))
        q.append("lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s AND (6371*2*asin(sqrt(power(sin(radians(lat-%s)/2),2)+cos(radians(%s))*cos(radians(lat))*power(sin(radians(lon-%s)/2),2)))) <= %s"); a += [lat - dlat, lat + dlat, lon - dlon, lon + dlon, lat, lat, lon, km]
    if f.get("polygon"):
        ring = f["polygon"]
        if len(ring) < 4: raise HTTPException(422, "polygon needs at least 4 points (closed ring of [lon, lat])")
        q.append("ST_Contains(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326), ST_SetSRID(ST_MakePoint(lon,lat),4326))"); a.append(json.dumps({"type": "Polygon", "coordinates": [ring]}))
    return " AND ".join(q), a

def query(f: dict, sort: str = "profit_per_effort", desc: bool = True, limit: int = 100, offset: int = 0) -> dict:
    if sort not in SORT: raise HTTPException(422, f"sort must be one of {sorted(SORT)}")
    limit = max(1, min(int(limit), 2000)); w, a = _where(f)
    with conn() as c:
        total = c.execute(f"SELECT count(*) AS n FROM analytics.rh_screen WHERE {w}", a).fetchone()["n"]
        rows = c.execute(f"SELECT {', '.join(COLS)} FROM analytics.rh_screen WHERE {w} ORDER BY {sort} {'DESC' if desc else 'ASC'} NULLS LAST, parcel_id LIMIT %s OFFSET %s", a + [limit, offset]).fetchall()
    return {"total": total, "rows": [_row(r) for r in rows], "banner": screen.status()["banner"], "filters": f}

def _row(r: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else (float(v) if hasattr(v, "as_tuple") else v)) for k, v in r.items()}

def points(bbox: tuple, f: dict | None = None, limit: int = 2000) -> dict:
    f = {**(f or {}), "bbox": bbox}; w, a = _where(f)
    with conn() as c: rows = c.execute(f"SELECT parcel_id, lon, lat, beds_base, beds_tier, profit_before_rent_annual, too_small FROM analytics.rh_screen WHERE {w} ORDER BY beds_base DESC LIMIT %s", a + [limit]).fetchall()
    return {"points": [[r["lon"], r["lat"], r["parcel_id"], r["beds_base"], r["beds_tier"], None if r["profit_before_rent_annual"] is None else round(float(r["profit_before_rent_annual"])), r["too_small"]] for r in rows], "truncated": len(rows) >= limit,
            "note": "[lon, lat, parcel_id, beds, tier, annual profit before rent, too_small]; ESTIMATED means bedrooms are guessed from footprints"}

def suburbs(min_candidates: int = 1) -> dict:
    with conn() as c:
        rows = c.execute("""SELECT suburb, count(*) AS candidates, sum(beds_base) AS beds_possible, avg(profit_before_rent_annual) AS avg_profit, avg(walk_away_rent) AS avg_walk_away, count(*) FILTER (WHERE beds_tier<>'ESTIMATED') AS better_than_estimated
                            FROM analytics.rh_screen WHERE suburb IS NOT NULL GROUP BY suburb HAVING count(*) >= %s ORDER BY sum(beds_base) DESC""", (min_candidates,)).fetchall()
    return {"suburbs": [{**_row(r), "certified_beds_existing": None, "beds_per_1000_aged_75_plus": None} for r in rows],
            "notes": ["certified_beds_existing is blank: the HealthCERT list is not loaded (BLOCKERS 5)", "beds_per_1000_aged_75_plus is blank: census data is not loaded (source and licence to be discovered; BLOCKERS 28)", "beds_possible sums ESTIMATED bedrooms for most rows: indicative only"]}

# ------------------------------------------------------------------ shortlists
def _audit(c, sid, action, detail=None): c.execute("INSERT INTO core.user_shortlist_audit (shortlist_id, action, detail) VALUES (%s,%s,%s::jsonb)", (sid, action, json.dumps(detail or {}, default=str)))

def save_shortlist(name: str, filters: dict, weights: dict | None, notes: str | None) -> dict:
    if not (name or "").strip(): raise HTTPException(422, "name required")
    _where(filters)
    with conn() as c:
        r = c.execute("INSERT INTO core.user_shortlist (name, filters, weights, notes) VALUES (%s,%s::jsonb,%s::jsonb,%s) RETURNING id", (name.strip(), json.dumps(filters), json.dumps(weights) if weights else None, notes)).fetchone(); _audit(c, r["id"], "created", {"name": name, "filters": filters}); c.commit()
    return get_shortlist(r["id"])

def get_shortlist(sid: int) -> dict:
    with conn() as c:
        s = c.execute("SELECT * FROM core.user_shortlist WHERE id=%s", (sid,)).fetchone()
        if not s: raise HTTPException(404, "no such shortlist")
        n = c.execute("SELECT count(*) AS n FROM core.user_shortlist_run WHERE shortlist_id=%s", (sid,)).fetchone()["n"]
    return {**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in s.items()}, "runs": n}

def list_shortlists() -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.user_shortlist ORDER BY id").fetchall()]
    return [get_shortlist(i) for i in ids]

def run_shortlist(sid: int, limit: int = 200) -> dict:
    s = get_shortlist(sid); res = query(s["filters"], (s["weights"] or {}).get("sort", "profit_per_effort"), True, limit)
    ranks = {str(r["parcel_id"]): i + 1 for i, r in enumerate(res["rows"])}
    with conn() as c:
        prev = c.execute("SELECT parcel_ids, ranks, run_at FROM core.user_shortlist_run WHERE shortlist_id=%s ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
        c.execute("INSERT INTO core.user_shortlist_run (shortlist_id, parcel_ids, ranks) VALUES (%s,%s,%s::jsonb)", (sid, [int(k) for k in ranks], json.dumps(ranks))); c.execute("UPDATE core.user_shortlist SET updated_at=now() WHERE id=%s", (sid,)); _audit(c, sid, "run", {"rows": len(ranks)}); c.commit()
    diff = None
    if prev:
        old = {k: v for k, v in prev["ranks"].items()}; new = [k for k in ranks if k not in old]; dropped = [k for k in old if k not in ranks]
        moved = [{"parcel_id": int(k), "from": old[k], "to": ranks[k]} for k in ranks if k in old and old[k] != ranks[k]]
        reasons = {}
        if dropped or new or moved:
            with conn() as c:
                for k in dropped[:50]:
                    r = c.execute("SELECT beds_base, beds_tier, too_small, last_computed FROM analytics.rh_screen WHERE parcel_id=%s", (int(k),)).fetchone()
                    reasons[k] = "no longer in the screening table (inputs or scope changed)" if not r else f"now {r['beds_base']} beds ({r['beds_tier']}); filters or inputs changed"
        diff = {"since": prev["run_at"].isoformat(), "new": [int(k) for k in new], "dropped": [int(k) for k in dropped], "re_ranked": moved[:200], "dropped_reasons": reasons}
    return {"shortlist": s["name"], "total": res["total"], "rows": res["rows"], "diff": diff, "banner": res["banner"]}

def audit(sid: int) -> list[dict]:
    with conn() as c: return [_row(r) for r in c.execute("SELECT action, detail, at FROM core.user_shortlist_audit WHERE shortlist_id=%s ORDER BY id", (sid,)).fetchall()]

def export(rows: list[dict], fmt: str = "csv") -> tuple[bytes, str, str]:
    cols = [c for c in COLS if c not in ("lon", "lat")]
    if fmt == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active; ws.append(cols)
        for r in rows: ws.append([r.get(c) if not isinstance(r.get(c), (dict, list)) else json.dumps(r.get(c)) for c in cols])
        ws.append([]); ws.append(["Screening on ESTIMATED data where tier says so. Placeholders flagged. Not advice."]); b = io.BytesIO(); wb.save(b); return b.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "shortlist.xlsx"
    out = io.StringIO(); w = csv.writer(out); w.writerow(cols)
    for r in rows: w.writerow([r.get(c) for c in cols])
    out.write("# Screening on ESTIMATED data where the tier says so. Placeholders are flagged. Not advice.\n"); return out.getvalue().encode(), "text/csv", "shortlist.csv"

def explain_parcel(parcel_id: int) -> dict:
    """Row for any parcel, computing it on demand when it is a candidate and not yet in the table; otherwise why it is not a candidate."""
    def one():
        with conn() as c: return c.execute(f"SELECT {', '.join(COLS)} FROM analytics.rh_screen WHERE parcel_id=%s", (parcel_id,)).fetchone()
    r = one()
    if not r:
        with conn() as c: s = c.execute("SELECT ST_XMin(geom) a, ST_YMin(geom) b, ST_XMax(geom) c, ST_YMax(geom) d, zone_name, building_count FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone()
        if not s: raise HTTPException(404, "no such parcel")
        screen.run((s["a"] - 1, s["b"] - 1, s["c"] + 1, s["d"] + 1), progress=None); r = one()
    if not r:
        with conn() as c: s = c.execute("SELECT zone_name, building_count FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone()
        why = ("no building on the parcel" if not s["building_count"] else (f"zone '{s['zone_name']}' has no consent path for residential care in the operative plan" if s["zone_name"] not in screen.candidate_zones() else "recorded non-residential building use"))
        return {"candidate": False, "reason": why}
    return {"candidate": True, "row": _row(r), "assumed": {"gfa_per_bed_m2": screen.cfg()["gfa_per_bed_m2"], "storeys": screen.cfg()["storeys_assumed"]}}
