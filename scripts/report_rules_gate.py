#!/usr/bin/env python3
"""Generate docs/RULES_STAGE3_GATE.md: 15 key standards for each of the four main residential zones, straight from analytics.rules,
with section reference, plan page, verbatim quote, source URL and last_verified. Run after `make rules`."""
import os, sys
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1); os.environ.setdefault(k, v)
ZONES = [("Residential - Single House Zone", "H3"), ("Residential - Mixed Housing Suburban Zone", "H4"),
         ("Residential - Mixed Housing Urban Zone", "H5"), ("Residential - Terrace Housing and Apartment Building Zone", "H6")]
# (label, topic, parameter)  -> value from analytics.rules
KEY = [("Building height (max)", "height", "building_height_max"), ("Height in relation to boundary: angle", "height_in_relation_to_boundary", "hirb_angle"),
       ("Height in relation to boundary: start height", "height_in_relation_to_boundary", "hirb_start_height"), ("Front yard (min)", "yards", "yard_front_min"),
       ("Side yard (min)", "yards", "yard_side_min"), ("Rear yard (min)", "yards", "yard_rear_min"), ("Maximum impervious area", "stormwater", "impervious_max_pct"),
       ("Maximum building coverage", "coverage", "building_coverage_max_pct"), ("Minimum landscaped area", "landscaping", "landscaped_min_pct"),
       ("Outlook space: principal living room depth", "outlook", "outlook_living_depth_min"), ("Outdoor living space, ground floor (min area)", "outdoor_living", "ols_ground_floor_min_area"),
       ("Minimum dwelling size, one or more bedrooms", "dwelling_size", "dwelling_min_net_floor_area_1br_plus"), ("Fence height in front yard (max)", "fences", "fence_front_yard_max"),
       ("Subdivision: min net site area, vacant site, parent < 1 ha", "subdivision", "min_net_site_area_vacant_site_parent_lt_1ha")]

def main():
    dsn = f"host={os.environ.get('PGHOST','localhost')} dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
    out = ["# Stage 3 gate: key standards for the four main residential zones", "",
           "Generated from `analytics.rules` by `scripts/report_rules_gate.py`. Source: operative Auckland Unitary Plan (July 2026), official chapter PDFs",
           "from unitaryplan.aucklandcouncil.govt.nz. Every numeric value below was matched by the loader to a verbatim quote in the extracted plan text. **None is owner-verified**: that needs your check (see docs/key_standards_check.html).",
           "Plan version: AUP fully operative 23 July 2026 (operative rows only; PC120 proposed rows are stored separately). PC120 (proposed) is NOT applied; sections marked † carry a PC 120 margin annotation in the plan.", ""]
    with psycopg.connect(dsn) as con, con.cursor() as cur:
        cur.execute("SELECT count(*) FROM analytics.rules WHERE evaluable AND topic <> 'activity_status'"); n_eval = cur.fetchone()[0]
        for zone, code in ZONES:
            out += [f"## {zone} ({code})", "", "| # | Standard | Value | Section | Page | Verbatim quote from the plan | Notes |", "|---|---|---|---|---|---|---|"]
            i = 0
            # dwellings per site from the activity table
            cur.execute("SELECT r.parameter, r.activity, r.value_text, r.section_ref, c.page_start, r.notes FROM analytics.rules r JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id "
                        "WHERE r.status = 'operative' AND r.topic = 'activity_status' AND r.zone = %s AND (r.activity ILIKE '%%dwelling%%per site%%' OR r.activity ILIKE 'Dwellings%%') ORDER BY r.id", (zone,))
            for par, act, st, sec, pg, notes in cur.fetchall():
                i += 1; out.append(f"| {i} | Activity: {act} | **{st}** | {sec} | {pg} | {act} | activity status; {notes or ''} |".replace("None", ""))
            for label, topic, param in KEY:
                cur.execute("SELECT r.value_num, r.value_text, r.unit, r.section_ref, c.page_start, r.quote, r.notes, c.pc120_flagged FROM analytics.rules r "
                            "LEFT JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id WHERE r.status = 'operative' AND r.zone = %s AND r.topic = %s AND r.parameter = %s", (zone, topic, param))
                row = cur.fetchone()
                if param.startswith("min_net_site_area_vacant"):
                    cur.execute("SELECT r.value_num, r.value_text, r.unit, r.section_ref, c.page_start, r.quote, r.notes, c.pc120_flagged FROM analytics.rules r "
                                "LEFT JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id WHERE r.status = 'operative' AND r.topic = 'subdivision' AND r.parameter = %s AND r.applies_if->>'zone_code' = (SELECT code::text FROM core.zone_lookup WHERE zone_name = %s OR zone_name = replace(%s,'Buildings','Building'))", (param, zone, zone))
                    row = cur.fetchone()
                i += 1
                if row is None: out.append(f"| {i} | {label} | not in this zone's standards | - | - | - | no such standard in {code}.6 |"); continue
                v, vt, u, sec, pg, q, notes, pc = row
                val = f"{v:g} {u}" if v is not None else f"{vt} {u or ''}"
                out.append(f"| {i} | {label} | **{val}** | {sec}{' †' if pc else ''} | {pg} | {q} | {notes or ''} |")
            out.append("")
        out += ["## Rest home relevant activity statuses (same tables)", "", "| Zone | Activity | Status | Section |", "|---|---|---|---|"]
        cur.execute("SELECT zone, activity, value_text, section_ref FROM analytics.rules r WHERE topic='activity_status' AND zone = ANY(%s) AND (activity ILIKE '%%residential care%%' OR activity ILIKE '%%care centre%%' OR activity ILIKE '%%boarding house%%' OR activity ILIKE '%%retirement%%') ORDER BY zone, id", ([z for z, _ in ZONES],))
        for z, a, s, sec in cur.fetchall(): out.append(f"| {z} | {a} | {s} | {sec} |")
        out += ["", f"_Evaluable numeric rules in database: {n_eval}. Non-numeric standards are stored as text-only rules and surface as NEEDS_PROFESSIONAL._", ""]
    (ROOT / "docs" / "RULES_STAGE3_GATE.md").write_text("\n".join(out))
    print("wrote docs/RULES_STAGE3_GATE.md")

if __name__ == "__main__":
    main()
