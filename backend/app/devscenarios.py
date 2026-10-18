"""Development scenarios for a parcel: Button 1 of the Site Panel (MASTER_SPEC Part 2 section 1.2). Loads the parcel geometry, runs the layout engine and rules evaluator, attaches the financial snapshot (or 'needs input'),
the compliance table, open items, consent path and a concept sketch. Each run is stored; a new run supersedes the old one."""
import json
from fastapi import HTTPException
from shapely import wkt
from shapely.geometry import Polygon
from . import devfin, devlayout, devrules
from .db import conn
from .stamp import STAMP

TYPOLOGIES = ("houses", "terraces", "transportable", "lots")
UNIT_KEYS = ("width_m", "depth_m", "height_m", "gfa_m2")
OPT_UNIT_KEYS = ("bedrooms", "storeys", "wall_height_m")
TIMELINE_STAGES = ["pre_application", "professional_reports", "lodgement", "council_processing_incl_rfi", "engineering_plan_approval", "site_works", "building_consent", "construction", "code_compliance", "s223_s224_survey_and_title", "sales"]
FOOTER = "Screening and preparation tool. Not planning, legal, engineering or financial advice. Council decides applications. Confirm with a qualified planner and the relevant professionals."

def load_site(parcel_id: int) -> dict:
    with conn() as c:
        s = c.execute("""SELECT parcel_id, address, suburb, zone_name, area_m2::float AS area, title_type, hazard_flags, overlays, maori_land_linz, ST_AsText((ST_Dump(geom)).geom) AS wkt, building_count, pc120_depends
                         FROM core.sites WHERE parcel_id=%s ORDER BY ST_Area((ST_Dump(geom)).geom) DESC LIMIT 1""", (parcel_id,)).fetchone()
        if not s: raise HTTPException(404, "no such parcel")
        pt = c.execute("""SELECT ST_X(ST_Centroid(a.geom)) x, ST_Y(ST_Centroid(a.geom)) y FROM raw.linz_addresses a, core.sites s WHERE s.parcel_id=%s AND ST_Intersects(s.geom, a.geom) LIMIT 1""", (parcel_id,)).fetchone()
        bl = c.execute("SELECT ST_AsText(geom) AS w FROM core.building_site WHERE parcel_id=%s LIMIT 40", (parcel_id,)).fetchall()
    poly = wkt.loads(s["wkt"])
    return {**s, "poly": poly, "front_point": (pt["x"], pt["y"]) if pt else None, "buildings": [wkt.loads(b["w"]) for b in bl if b["w"]]}

def _coords(g): return [[round(x, 2), round(y, 2)] for x, y in g.exterior.coords]

def sketch_svg(site: dict, env, sc: dict | None, title: str) -> str:
    p = site["poly"]; minx, miny, maxx, maxy = p.bounds; w, h = maxx - minx, maxy - miny; pad = max(w, h) * 0.06 or 1; k = 400 / max(w, h)
    tx = lambda x, y: f"{(x - minx + pad) * k:.1f},{(maxy - y + pad) * k:.1f}"
    pts = lambda g: " ".join(tx(x, y) for x, y in g.exterior.coords)
    W, H = (w + 2 * pad) * k, (h + 2 * pad) * k + 36; parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="100%" role="img" aria-label="{title}"><rect width="100%" height="100%" fill="#fff"/>']
    parts.append(f'<polygon points="{pts(p)}" fill="#f4f7f1" stroke="#222" stroke-width="2"/>')
    if env is not None and not env.is_empty and env.geom_type == "Polygon": parts.append(f'<polygon points="{pts(env)}" fill="none" stroke="#888" stroke-dasharray="5 4"/>')
    for b in site["buildings"]:
        if b.geom_type == "Polygon": parts.append(f'<polygon points="{pts(b)}" fill="none" stroke="#b91c1c" stroke-dasharray="3 3"/>')
    if sc:
        if sc.get("access") is not None and sc["access"].geom_type == "Polygon": parts.append(f'<polygon points="{pts(sc["access"])}" fill="#d9d9d9" stroke="#999"/>')
        for u in sc["units"]:
            if u.get("ols") is not None: parts.append(f'<polygon points="{pts(u["ols"])}" fill="#e3f1d8" stroke="#8bb870"/>')
            c = u["footprint"].centroid
            parts.append(f'<polygon points="{pts(u["footprint"])}" fill="#bcd4f0" stroke="#0b5cab" stroke-width="1.5"/><text x="{tx(c.x, c.y).split(",")[0]}" y="{tx(c.x, c.y).split(",")[1]}" font-size="11" text-anchor="middle">{u["id"]}</text>')
    parts.append(f'<text x="6" y="{H - 22:.0f}" font-size="11" fill="#b91c1c">Concept sketch, not a design. Dashed grey = buildable envelope; red dashed = existing buildings (assumed demolished); green = outdoor living space.</text><text x="6" y="{H - 8:.0f}" font-size="10" fill="#555">{FOOTER[:96]}</text></svg>')
    return "".join(parts)

def clean_inputs(inp: dict) -> dict:
    t = inp.get("typology", "houses")
    if t not in TYPOLOGIES: raise HTTPException(422, f"typology must be one of {list(TYPOLOGIES)} (apartments and rest-home new builds are compared on the Best Use tab, not packed here)")
    unit = {k: inp.get("unit", {}).get(k) for k in UNIT_KEYS + OPT_UNIT_KEYS}
    for k, v in unit.items():
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0): raise HTTPException(422, f"unit.{k} must be a non-negative number")
    fin = {k: inp.get("finance", {}).get(k) for k in devfin.REQUIRED + devfin.OPTIONAL}
    for k, v in fin.items():
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0): raise HTTPException(422, f"finance.{k} must be a non-negative number")
    aw = inp.get("access_width_m")
    if aw is not None and (isinstance(aw, bool) or not isinstance(aw, (int, float)) or aw <= 0): raise HTTPException(422, "access_width_m must be positive")
    tw = inp.get("timeline_weeks") or {}
    bad = [k for k in tw if k not in TIMELINE_STAGES]
    if bad or any(v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0) for v in tw.values()): raise HTTPException(422, f"timeline_weeks: stages must be from {TIMELINE_STAGES} with non-negative numbers")
    return {"typology": t, "unit": unit, "finance": fin, "access_width_m": aw, "timeline_weeks": {k: tw.get(k) for k in TIMELINE_STAGES}}

def _scenario_json(sc: dict, fin_inputs: dict, gfa: float) -> dict:
    f = devfin.feasibility(sc["unit_count"], gfa, fin_inputs)
    return {"unit_count": sc["unit_count"], "meta": sc["meta"], "summary": sc["summary"], "checks": [{**c} for c in sc["checks"]], "financials": f,
            "geometry": {"units": [{"id": u["id"], "footprint": _coords(u["footprint"]), "ols": _coords(u["ols"]) if u.get("ols") is not None else None} for u in sc["units"]], "access": _coords(sc["access"]) if sc.get("access") is not None and sc["access"].geom_type == "Polygon" else None}}

def run(parcel_id: int, raw_inputs: dict) -> dict:
    inp = clean_inputs(raw_inputs); site = load_site(parcel_id); zone = site["zone_name"]
    if not zone: raise HTTPException(409, "zone not known for this parcel")
    R = devrules.zone_rules(zone); res = {"parcel_id": parcel_id, "address": site["address"], "zone": zone, "inputs": inp, "footer": FOOTER}
    hazards = {"hazard_flags": site["hazard_flags"], "note": "Natural hazard flags count for development feasibility: treat flagged sites with a geotechnical / hydrology review before any commitment."}
    res["site"] = {"area_m2": round(site["area"], 1), "title_type": site["title_type"], "overlays": site["overlays"], "maori_land": site["maori_land_linz"], "existing_buildings": len(site["buildings"]), "hazards": hazards, "pc120_depends": site["pc120_depends"]}
    res["rules_not_loaded"] = [k for k in ("yard_front_min", "yard_side_min", "yard_rear_min", "building_coverage_max_pct", "impervious_max_pct", "landscaped_min_pct", "building_height_max", "hirb_angle", "ols_ground_floor_min_area") if k not in R]
    res["activity_rows"] = devrules.activity_rows(zone)
    if inp["typology"] == "lots":
        sub = devlayout.subdivision_yield(site["poly"], zone, R); res["subdivision"] = sub; res["scenarios"] = []
        n = sub.get("lots_in_layout"); fin = inp["finance"]
        res["financials"] = devfin.feasibility(n, 0.0, fin) if n else {"status": "needs_input", "needs_input": ["a lot count"]}
        res["open_items"] = ["Licensed surveyor: scheme plan, frontage, shape factor, access", "Civil engineer: servicing and stormwater", "Planner: consent pathway and activity status", "Watercare / Vector confirmation (capacity is always UNKNOWN until confirmed)"]
    else:
        missing = [k for k in UNIT_KEYS if inp["unit"].get(k) is None]
        if missing: res.update(status="needs_input", needs_input=[f"unit.{k}" for k in missing], scenarios=[]); return _store(parcel_id, inp, res)
        best = devlayout.best(site["poly"], zone, inp["unit"], inp["access_width_m"], site["front_point"], R); res["binding_constraint"] = devlayout.binding_constraint(best)
        gfa = inp["unit"]["gfa_m2"]; top = best["compliant"][:3]; rank = lambda c: ((devfin.feasibility(c["unit_count"], gfa, inp["finance"]).get("profit") or 0), c["unit_count"])
        if all(not devfin.needs(inp["finance"]) for _ in [0]): top = sorted(best["compliant"], key=rank, reverse=True)[:3]
        res["scenarios"] = [{"rank": i + 1, "kind": "compliant", **_scenario_json(c, inp["finance"], gfa), "sketch_svg": sketch_svg(site, best["envelope"], c, f"Scenario {i + 1}")} for i, c in enumerate(top)]
        if not best["compliant"] and best["near_misses"]:
            c = best["near_misses"][0]; res["scenarios"].append({"rank": 1, "kind": "nearest_miss", **_scenario_json(c, inp["finance"], gfa), "sketch_svg": sketch_svg(site, best["envelope"], c, "Nearest miss")})
        res["candidates_evaluated"] = len(best["candidates"]); res["envelope_area_m2"] = round(best["envelope"].area, 1)
        sel = res["scenarios"][0] if res["scenarios"] else None
        if sel:
            res["financials"] = sel["financials"]; res["sensitivity"] = devfin.sensitivity(sel["unit_count"], gfa, inp["finance"]); res["break_even_build_cost_per_m2"] = devfin.break_even_build_cost(sel["unit_count"], gfa, inp["finance"])
            res["badge"] = sel["summary"]["badge"]; res["badge_label"] = sel["summary"]["badge_label"]
            res["open_items"] = [f"{c['topic']}: {c['id']} ({c['status']})" + (f": {c['note']}" if c.get("note") else "") for c in sel["checks"] if c["status"] in ("NEEDS_PROFESSIONAL", "UNKNOWN")]
        res["status"] = "ok"
    res["services_note"] = "Servicing: see the Services section (capacity is UNKNOWN until Watercare / Vector confirm in writing)."
    return _store(parcel_id, inp, res)

def _store(parcel_id: int, inp: dict, res: dict) -> dict:
    with conn() as c:
        r = c.execute("INSERT INTO core.user_dev_run (parcel_id, inputs, result) VALUES (%s,%s::jsonb,%s::jsonb) RETURNING id", (parcel_id, json.dumps(inp), json.dumps(res, default=str))).fetchone()
        c.execute("UPDATE core.user_dev_run SET superseded_by=%s WHERE parcel_id=%s AND id<>%s AND superseded_by IS NULL", (r["id"], parcel_id, r["id"])); c.commit()
    return {"run_id": r["id"], **res}

def get_run(run_id: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.user_dev_run WHERE id=%s", (run_id,)).fetchone()
    if not r: raise HTTPException(404, "no such run")
    return {"run_id": r["id"], "superseded": r["superseded_by"] is not None, **r["result"]}

def latest(parcel_id: int) -> dict | None:
    with conn() as c: r = c.execute("SELECT id FROM core.user_dev_run WHERE parcel_id=%s AND superseded_by IS NULL ORDER BY id DESC LIMIT 1", (parcel_id,)).fetchone()
    return get_run(r["id"]) if r else None
