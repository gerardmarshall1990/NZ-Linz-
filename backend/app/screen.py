"""Bulk Auckland screening (MASTER_SPEC Part 4 section 1): one row per candidate dwelling in analytics.rh_screen, rebuilt by `make screen` (incremental: a row is rewritten only when its inputs or your assumptions changed).
Candidates: parcels with a building (not a school, hospital or other recorded non-residential use) in a zone where some residential-care activity has a consent path (permitted, controlled, restricted discretionary or discretionary in the operative plan). Beds: confirmed plan facts (CONFIRMED) > listing bedrooms (DOCUMENTED) >
footprint estimate (ESTIMATED: footprint x assumed storeys / a placeholder m2 per bed, cautious). Economics use YOUR inputs; blanks give NULL and 'needs_input', never a number. Rows using placeholders are flagged. Natural hazard flags are stored for information only."""
import hashlib, json
from datetime import datetime
import yaml
from . import economics as E, ranking, settings, verdict as V
from .config import ROOT
from .db import conn

def cfg() -> dict: return yaml.safe_load((ROOT / "config" / "screening.yaml").read_text())

def candidate_zones() -> list[str]:
    with conn() as c:
        return [r["zone"] for r in c.execute("""SELECT DISTINCT zone FROM analytics.rules WHERE topic='activity_status' AND status='operative' AND (activity ILIKE 'Supported residential care%%' OR activity ILIKE 'Healthcare facilities%%')
                                                  AND status_class IN ('permitted','controlled','restricted_discretionary','discretionary')""").fetchall()]

def _hash(*xs) -> str: return hashlib.sha1(json.dumps(xs, default=str, sort_keys=True).encode()).hexdigest()[:20]

def run(bbox: tuple | None = None, limit: int | None = None, progress=print) -> dict:
    """bbox = (minE, minN, maxE, maxN) in EPSG:2193 limits the scope (tests, slices). Returns counts."""
    zones = candidate_zones(); p = settings.assumptions(); sc = cfg(); gpb = sc["gfa_per_bed_m2"]["value"]; st = sc["storeys_assumed"]
    w = ranking.weights(); ph = settings.used_not_decision_grade(settings.OPEX_NEEDED, None); uses_ph = bool(ph)
    ahash = _hash(p, gpb, st, w, uses_ph)
    mb = V.minimum_beds(p); cache = {}
    def econ(beds):
        if beds in cache: return cache[beds]
        a = V.at_beds(beds, p); cache[beds] = a; return a
    with conn() as c:
        run_id = c.execute("INSERT INTO analytics.rh_screen_run (scope) VALUES (%s) RETURNING id", ("bbox" if bbox else "all",)).fetchone()["id"]; c.commit()
    seen = wrote = same = 0; last = 0
    while True:
        with conn() as c:
            q = """SELECT s.parcel_id, s.address, s.suburb, s.zone_name, s.title_type, ST_X(ST_Transform(ST_Centroid(s.geom),4326)) AS lon, ST_Y(ST_Transform(ST_Centroid(s.geom),4326)) AS lat,
                          s.building_count, s.total_footprint_m2::float AS fp, s.hazard_flags,
                          (SELECT max(l.bedrooms) FROM core.user_listing l WHERE l.parcel_id = s.parcel_id AND l.status='active' AND l.bedrooms IS NOT NULL AND l.source_id NOT LIKE 'DEMO-%%') AS lbeds,
                          (SELECT (f.value #>> '{}')::int FROM core.rh_property_fact f WHERE f.parcel_id = s.parcel_id AND f.field='bedrooms_total' AND f.confidence IN ('CONFIRMED','DOCUMENTED') LIMIT 1) AS fbeds,
                          (SELECT f.confidence FROM core.rh_property_fact f WHERE f.parcel_id = s.parcel_id AND f.field='bedrooms_total' LIMIT 1) AS ftier,
                          (SELECT a.bedrooms FROM core.user_property_attribute a WHERE a.parcel_id = s.parcel_id) AS abeds, (SELECT a.floor_area_m2::float FROM core.user_property_attribute a WHERE a.parcel_id = s.parcel_id) AS afloor,
                          o.hash AS oldhash
                   FROM core.sites s LEFT JOIN (SELECT parcel_id, inputs_hash AS hash FROM analytics.rh_screen) o ON o.parcel_id = s.parcel_id
                   WHERE s.parcel_id > %s AND s.building_count > 0 AND s.zone_name = ANY(%s) AND NOT coalesce(s.is_reserve, false)
                         AND NOT EXISTS (SELECT 1 FROM core.building_site b WHERE b.parcel_id = s.parcel_id AND b.use IS NOT NULL AND b.use <> 'Unknown')"""
            a = [last, zones]
            if bbox: q += " AND s.geom && ST_MakeEnvelope(%s,%s,%s,%s,2193)"; a += list(bbox)
            q += " ORDER BY s.parcel_id LIMIT 5000"
            rows = c.execute(q, a).fetchall()
            if not rows: break
            out = []
            for r in rows:
                seen += 1; last = r["parcel_id"]
                if limit and seen > limit: break
                fp = r["fp"] or 0; gfa = r["afloor"] if r["afloor"] else fp * st; est = int(gfa // gpb)
                if r["fbeds"] is not None: beds, tier, src = r["fbeds"], r["ftier"], "Property Record bedrooms"
                elif r["lbeds"] is not None: beds, tier, src = r["lbeds"], "DOCUMENTED", "listing bedrooms"
                elif r["abeds"] is not None: beds, tier, src = r["abeds"], "DOCUMENTED", "licensed property attributes (bedrooms)"
                else: beds, tier, src = est, "ESTIMATED", (f"licensed floor area {gfa:.0f} m2" if r["afloor"] else f"footprint {fp:.0f} m2 x {st} storey") + f" / {gpb} m2 per bed (placeholder)"
                h = _hash(r["parcel_id"], fp, r["zone_name"], r["title_type"], beds, tier, ahash)
                if h == r["oldhash"]: same += 1; continue
                a_ = econ(beds) if beds >= 1 else {"needs_input": []}; need = a_.get("needs_input") or []
                prof = None if need or beds < 1 else (a_["N"] - a_["retrofit_charge"]) * E.W
                tk = {"fee_simple": 0, "freehold": 0, "cross lease": 3, "unit title": 4}.get((r["title_type"] or "").lower(), 2)
                eff = 1 + w["weights"]["parties"] * tk * 0 + w["weights"]["parties"] * (w["title_parties_points"].get((r["title_type"] or "").lower().replace(" ", "_"), w["title_parties_points"]["unknown"])) + w["weights"]["beds_to_fill"] * beds / 10
                too_small = None if mb.get("minimum_beds") is None else beds < mb["minimum_beds"]
                out.append((r["parcel_id"], r["address"], r["suburb"], r["zone_name"], r["title_type"], r["lon"], r["lat"], r["building_count"], fp, gfa, beds, tier, src, a_.get("retrofit_cost"), prof, a_.get("walk_away_rent"),
                            mb.get("minimum_beds"), mb.get("target_beds"), too_small, round(eff, 2), None if prof is None else round(prof / eff, 0), json.dumps(r["hazard_flags"]) if r["hazard_flags"] else None, uses_ph, ",".join(need) or None, h))
            for o in out:
                c.execute("""INSERT INTO analytics.rh_screen (parcel_id, address, suburb, zone, title_type, lon, lat, building_count, footprint_m2, gfa_est_m2, beds_base, beds_tier, beds_source, retrofit_est, profit_before_rent_annual, walk_away_rent,
                             min_beds_minimum, min_beds_target, too_small, effort_points, profit_per_effort, hazard_flags, uses_placeholders, needs_input, inputs_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                             ON CONFLICT (parcel_id) DO UPDATE SET address=EXCLUDED.address, suburb=EXCLUDED.suburb, zone=EXCLUDED.zone, title_type=EXCLUDED.title_type, lon=EXCLUDED.lon, lat=EXCLUDED.lat, building_count=EXCLUDED.building_count,
                             footprint_m2=EXCLUDED.footprint_m2, gfa_est_m2=EXCLUDED.gfa_est_m2, beds_base=EXCLUDED.beds_base, beds_tier=EXCLUDED.beds_tier, beds_source=EXCLUDED.beds_source, retrofit_est=EXCLUDED.retrofit_est,
                             profit_before_rent_annual=EXCLUDED.profit_before_rent_annual, walk_away_rent=EXCLUDED.walk_away_rent, min_beds_minimum=EXCLUDED.min_beds_minimum, min_beds_target=EXCLUDED.min_beds_target, too_small=EXCLUDED.too_small,
                             effort_points=EXCLUDED.effort_points, profit_per_effort=EXCLUDED.profit_per_effort, hazard_flags=EXCLUDED.hazard_flags, uses_placeholders=EXCLUDED.uses_placeholders, needs_input=EXCLUDED.needs_input,
                             inputs_hash=EXCLUDED.inputs_hash, last_computed=now()""", o)
            wrote += len(out)
            c.execute("UPDATE analytics.rh_screen_run SET rows_seen=%s, rows_written=%s, rows_unchanged=%s WHERE id=%s", (seen, wrote, same, run_id)); c.commit()
        if progress: progress(f"screen: seen {seen}, written {wrote}, unchanged {same}")
        if limit and seen >= limit: break
    with conn() as c: c.execute("UPDATE analytics.rh_screen_run SET finished_at=now(), status='done', rows_seen=%s, rows_written=%s, rows_unchanged=%s, note=%s WHERE id=%s", (seen, wrote, same, "uses placeholders" if uses_ph else None, run_id)); c.commit()
    return {"run_id": run_id, "seen": seen, "written": wrote, "unchanged": same, "zones": len(zones), "uses_placeholders": uses_ph, "needs_input": mb.get("needs_input")}

def status() -> dict:
    with conn() as c:
        r = c.execute("SELECT * FROM analytics.rh_screen_run ORDER BY id DESC LIMIT 1").fetchone(); n = c.execute("SELECT count(*) AS n, count(*) FILTER (WHERE beds_tier='ESTIMATED') AS e, count(*) FILTER (WHERE beds_tier='DOCUMENTED') AS d, count(*) FILTER (WHERE beds_tier='CONFIRMED') AS c, max(last_computed) AS at FROM analytics.rh_screen").fetchone()
    return {"rows": n["n"], "by_tier": {"ESTIMATED": n["e"], "DOCUMENTED": n["d"], "CONFIRMED": n["c"]}, "last_computed": n["at"].isoformat() if n["at"] else None,
            "last_run": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()} if r else None, "assumptions": {"gfa_per_bed_m2": cfg()["gfa_per_bed_m2"], "storeys_assumed": cfg()["storeys_assumed"]},
            "banner": "Screening on ESTIMATED data: bedrooms are guessed from building footprints with a placeholder. Confirm plans before relying on any row."}
