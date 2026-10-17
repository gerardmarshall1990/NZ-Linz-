#!/usr/bin/env python3
"""Load structured rules into analytics.rules, as OPERATIVE or PROPOSED rows (never merged).

Operative sources:
  1. config/rules_seed/auckland_*.yaml   numeric standards. Each `quote` must occur verbatim (normalised) in the extracted operative plan text for
                                         `standard_ref`, otherwise the load FAILS (no unquoted numbers reach the database).
  2. data/aup/activity_rows.jsonl        zone activity tables (P/C/RD/D/NC/Pr) parsed from the operative plan PDFs.
  3. every other zone standard section (X.6.n) without a seed becomes a text-only rule (evaluable=false -> NEEDS_PROFESSIONAL).
  `pc120_effect` on operative rows comes from config/rules_seed/pc120_effects.yaml (Council info sheets; quotes checked).
Proposed sources:
  config/rules_seed/pc120_proposed.yaml  rows with status='proposed', plan_change_id='PC120'; evidence quotes are checked against Council's PC120 plan text
                                         (data/pc120/sections.jsonl, proposed reading) or information sheets (data/pc120/txt). Linked to the operative rule they supersede.
Nothing is marked owner_verified here (decision 17). Requires analytics.rule_text_chunks (scripts/load_rule_chunks.py) and analytics.plan_versions.
"""
import csv, io, json, os, re, subprocess, sys
from datetime import date
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
STATUS_CLASS = {"P": "permitted", "C": "controlled", "RD": "restricted_discretionary", "D": "discretionary", "NC": "non_complying", "Pr": "prohibited"}
ZONE_CODE = {"H1": 23, "H2": 20, "H3": 19, "H4": 18, "H5": 60, "H6": 8, "H8": 35, "H9": 10, "H10": 22, "H11": 7, "H12": 44, "H13": 12, "H14": 49,
             "H15": 1, "H16": 5, "H17": 17, "H18": 4, "H20": 68, "H21": 69, "H22": 26, "H24": 53, "H25": 55, "H27": 52, "H28": 51, "H29": 63, "H30": 64}
PC_NOTE_TXT = "PC 120 annotation on this section (operative text shown; confirm legal effect)"
ASSESSED_ZONES = {19, 18, 60, 8}   # PC120 effects assessed for the four main residential zones
SHEET_KEYS = {"info_sheet_09_THAB": "10-info-Sheet-09", "info_sheet_10_MHU": "11-info-sheet-10", "info_sheet_11_MHS": "12-info-sheet-11", "info_sheet_12_SHZ": "13-info-sheet-12"}

def env():
    for l in (ROOT / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k, v)

def psql(args, **kw):
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    return subprocess.run(["psql", "-h", os.environ.get("PGHOST", "localhost"), "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"],
                           "-v", "ON_ERROR_STOP=1", "-q", "-At", *args], check=True, env=e, capture_output=kw.pop("capture", False), text=True, **kw)

def norm(t):
    t = t.lower().replace("²", "2").replace("?", "2").replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip()

def load_pc120_sources():
    sec = {}
    f = ROOT / "data/pc120/sections.jsonl"
    if f.exists():
        for line in open(f):
            r = json.loads(line); sec.setdefault((r["doc"], r["ref"]), norm(r["proposed_text"]))
    sheets = {}
    for key, prefix in SHEET_KEYS.items():
        for t in (ROOT / "data/pc120/txt").glob(prefix + "*.txt"): sheets[key] = norm(t.read_text())
    return sec, sheets

def base_row(**kw):
    r = dict(status="operative", plan_change_id=None, pc120_effect=None, pc120_evidence=None, evidence_doc=None, supersedes_param=None, pv="OP", operator=None, value_num=None,
             value_text=None, unit=None, quote=None, rule_text=None, overlay=None, chunk_id=None)
    r.update(kw); return r

def main():
    env()
    chunks = {}
    out = psql(["-F", "\x1f", "-c", "SELECT section_ref, id, pc120_flagged, replace(text, E'\\n', ' '), source_url, ref_unverified, page_start FROM analytics.rule_text_chunks ORDER BY id"], capture=True).stdout
    for line in out.splitlines():
        ref, cid, pc, text, url, unv, pg = line.split("\x1f", 6)
        chunks.setdefault(ref, dict(id=int(cid), pc=pc == "t", text=norm(text), url=url, unverified=unv == "t", page=int(pg)))
    zones = dict(l.split("|") for l in psql(["-c", "SELECT code || '|' || zone_name FROM core.zone_lookup"], capture=True).stdout.splitlines())
    pv_op = int(psql(["-c", "SELECT id FROM analytics.plan_versions WHERE plan_name = 'Auckland Unitary Plan'"], capture=True).stdout.strip())
    pv_pc = int(psql(["-c", "SELECT id FROM analytics.plan_versions WHERE plan_name LIKE 'PC 120%'"], capture=True).stdout.strip())
    today = date.today().isoformat()
    rows, bad, seeded = [], [], set()
    # ---- operative numeric seeds
    for f in sorted((ROOT / "config/rules_seed").glob("auckland_*.yaml")):
        for r in yaml.safe_load(f.read_text()):
            c = chunks.get(r["standard_ref"])
            if c is None: bad.append((r["standard_ref"], r["parameter"], "no such section in extracted plan text")); continue
            if norm(r["quote"]) not in c["text"]: bad.append((r["standard_ref"], r["parameter"], f"quote not found: {r['quote']!r}")); continue
            seeded.add(r["standard_ref"])
            is_act = r["topic"] == "activity_status"
            zname = zones[str(r["zone_code"])] if r["zone_code"] is not None else ("Māori land (Auckland-wide, E20)" if r["chapter"] == "E20" else "Residential (all residential zones)")
            num = isinstance(r["value"], (int, float))
            rows.append(base_row(zone=zname, topic=r["topic"], parameter=r["parameter"], operator=r["operator"], value_num=r["value"] if num else None, value_text=None if num else str(r["value"]),
                unit=r["unit"], applies_if={**({"zone_code": r["zone_code"]} if r["zone_code"] is not None else {}), **({"activity": r["activity"]} if r.get("activity") else {}), **(r.get("applies_if") or {})},
                status_class=STATUS_CLASS.get(str(r["value"])) if is_act else "standard", standard_ref=r["standard_ref"], section_ref=r["standard_ref"], chunk_id=c["id"], quote=r["quote"], url=c["url"],
                evaluable=r["evaluable"], notes="; ".join(x for x in [r.get("note"), PC_NOTE_TXT if c["pc"] else None] if x), page=c["page"]))
    if bad:
        print(f"{len(bad)} operative seed entries failed verification:"); [print("  ", b) for b in bad]; sys.exit(1)
    n_seed = len(rows); n_act = n_txt = 0
    # ---- operative activity tables
    for line in open(ROOT / "data/aup/activity_rows.jsonl"):
        a = json.loads(line); code = a["zone_code"]; c = chunks.get(f"{code}.4")
        note = "; ".join(x for x in [a.get("note"), None if a["status"] else "status not parsed from table: read the plan text", PC_NOTE_TXT if c and c["pc"] else None] if x)
        rows.append(base_row(zone=zones[str(ZONE_CODE[code])], topic="activity_status", parameter=a["id"], value_text=a["status"], applies_if={"zone_code": ZONE_CODE[code], "activity": a["activity"]},
            status_class=STATUS_CLASS.get(a["status"]), standard_ref="; ".join(a["standards"]) or None, section_ref=f"{code}.4.1 ({a['id']})", chunk_id=c["id"] if c else None, quote=a["activity"],
            rule_text=a["standards_text"] or None, url=a["url"], evaluable=a["status"] in STATUS_CLASS, notes=note or None, page=a["page"])); n_act += 1
    # ---- operative text-only standards
    for ref, c in chunks.items():
        m = re.match(r"^(H\d+)\.6\.\d+$", ref)
        if m and m.group(1) in ZONE_CODE and ref not in seeded and not c["unverified"]:
            heading = psql(["-c", f"SELECT heading FROM analytics.rule_text_chunks WHERE id = {c['id']}"], capture=True).stdout.strip()
            rows.append(base_row(zone=zones[str(ZONE_CODE[m.group(1)])], topic="standard_text", parameter=heading[:120], applies_if={"zone_code": ZONE_CODE[m.group(1)]}, status_class="standard",
                standard_ref=ref, section_ref=ref, chunk_id=c["id"], url=c["url"], evaluable=False, page=c["page"],
                notes="no numeric extraction: NEEDS_PROFESSIONAL unless a seed rule exists" + ("; PC 120 annotation (confirm legal effect)" if c["pc"] else ""))); n_txt += 1
    # ---- PC120 effects on operative rows (Council info sheets)
    sec, sheets = load_pc120_sources(); bad = []
    eff = {}
    for e in yaml.safe_load((ROOT / "config/rules_seed/pc120_effects.yaml").read_text()):
        if norm(e["quote"]) not in sheets.get(e["sheet"], ""): bad.append(("effect", e["zone_code"], e["parameters"][:1], f"quote not in {e['sheet']}: {e['quote']!r}")); continue
        for p in e["parameters"]: eff[(e["zone_code"], p)] = (e["effect"], f"{e['sheet']}: \"{e['quote']}\"" + (f" ({e['note']})" if e.get("note") else ""))
    for r in rows:
        if r["topic"] in ("activity_status", "standard_text"): continue
        z = r["applies_if"].get("zone_code"); k = (z, r["parameter"])
        if k in eff: r["pc120_effect"], r["pc120_evidence"] = eff[k]
        elif r["parameter"].startswith("min_net_site_area_vacant_site_parent_lt_1ha"):
            r["pc120_effect"], r["pc120_evidence"] = "unchanged", "computed: PC120 chapter E subdivision (53-pc120-chapter-e-subdivision.pdf) E38.8.2.3 table read with tracked-change detection shows no change"
        elif z in ASSESSED_ZONES or r["topic"] == "subdivision": r["pc120_effect"], r["pc120_evidence"] = "to_check", "not covered by Council's per-zone information sheets; read the PC120 text"
        else: r["pc120_effect"], r["pc120_evidence"] = "not_assessed", "PC120 effect not assessed for this zone/chapter yet"
    # ---- proposed rows
    n_prop = 0
    for e in yaml.safe_load((ROOT / "config/rules_seed/pc120_proposed.yaml").read_text()):
        ev = e["evidence"]
        src = sheets.get(ev["sheet"], "") if "sheet" in ev else sec.get((ev["doc"], ev["ref"]), "")
        label = ev.get("sheet") or f"{ev['doc']} {ev['ref']}"
        if norm(e["quote"]) not in src: bad.append(("proposed", e["zone_code"], e["parameter"], f"quote not found in {label}: {e['quote']!r}")); continue
        num = isinstance(e["value"], (int, float))
        rows.append(base_row(status="proposed", plan_change_id="PC120", pv="PC", zone=zones[str(e["zone_code"])], topic=e["topic"], parameter=e["parameter"], operator=e["operator"],
            value_num=e["value"] if num else None, value_text=None if num else str(e["value"]), unit=e["unit"], applies_if={"zone_code": e["zone_code"], **(e.get("applies_if") or {})},
            status_class="standard" if e["topic"] != "activity_status" else STATUS_CLASS.get(str(e["value"])), standard_ref=e["standard_ref"], section_ref=e["standard_ref"], quote=e["quote"], evaluable=False,
            url="https://www.aucklandcouncil.govt.nz/en/plans-policies-bylaws-reports-projects/our-plans-strategies/unitary-plan/auckland-unitary-plan-modifications/proposed-plan-changes/pc-120-housing-intensification-resilience.html",
            evidence_doc=label, pc120_effect=e["effect"], supersedes_param=e.get("supersedes_parameter"), page=None,
            notes="; ".join(x for x in [e.get("note"), "PROPOSED (not in force): PC120 submissions closed 24 Sep 2026; verdict depends on PC120"] if x))); n_prop += 1
    if bad:
        print(f"{len(bad)} PC120 entries failed verification:"); [print("  ", b) for b in bad]; sys.exit(1)
    # ---- write
    buf = io.StringIO(); w = csv.writer(buf)
    for r in rows:
        w.writerow(["Auckland Council", pv_pc if r["pv"] == "PC" else pv_op, r["zone"], "", r["topic"], r["parameter"], r["operator"] or "", "" if r["value_num"] is None else r["value_num"], r["value_text"] or "", r["unit"] or "",
                    json.dumps(r["applies_if"], ensure_ascii=False), r["status_class"] or "", r["standard_ref"] or "", r["section_ref"], r["chunk_id"] or "", r["quote"] or "", r["rule_text"] or "",
                    r["url"], today, "t" if r["evaluable"] else "f", r["notes"] or "", r["status"], r["plan_change_id"] or "", r["pc120_effect"] or "", r["pc120_evidence"] or "", r["evidence_doc"] or "", r["supersedes_param"] or "", r.get("page") or ""])
    psql(["-c", "TRUNCATE analytics.rules RESTART IDENTITY CASCADE"])
    psql(["-c", "DROP TABLE IF EXISTS analytics._r_stage; CREATE TABLE analytics._r_stage (council text, pv int, zone text, overlay text, topic text, parameter text, operator text, value_num text, value_text text, unit text, applies_if text, status_class text, standard_ref text, section_ref text, chunk_id text, quote text, rule_text text, url text, lv date, evaluable boolean, notes text, status text, plan_change_id text, pc120_effect text, pc120_evidence text, evidence_doc text, supersedes_param text, page text)"])
    psql(["-c", "\\copy analytics._r_stage FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue())
    psql(["-c", "INSERT INTO analytics.rules (council, plan_version_id, zone, overlay, activity, topic, parameter, operator, value_num, value_text, unit, applies_if, status_class, standard_ref, section_ref, chunk_id, quote, rule_text, source_url, last_verified, evaluable, notes, status, plan_change_id, pc120_effect, pc120_evidence, evidence_doc, quote_page) "
                "SELECT council, pv, zone, NULLIF(overlay,''), applies_if::jsonb->>'activity', topic, parameter, NULLIF(operator,''), NULLIF(value_num,'')::numeric, NULLIF(value_text,''), NULLIF(unit,''), applies_if::jsonb, NULLIF(status_class,''), NULLIF(standard_ref,''), section_ref, NULLIF(chunk_id,'')::int, NULLIF(quote,''), NULLIF(rule_text,''), url, lv, evaluable, NULLIF(notes,''), status, NULLIF(plan_change_id,''), NULLIF(pc120_effect,''), NULLIF(pc120_evidence,''), NULLIF(evidence_doc,''), NULLIF(page,'')::int FROM analytics._r_stage ORDER BY status DESC, 1; "
                "UPDATE analytics.rules p SET supersedes_rule_id = o.id FROM analytics._r_stage s, analytics.rules o WHERE s.supersedes_param <> '' AND p.status = 'proposed' AND p.parameter = s.parameter AND p.zone = s.zone AND p.standard_ref = s.standard_ref AND o.status = 'operative' AND o.zone = p.zone AND o.parameter = s.supersedes_param; "
                "DROP TABLE analytics._r_stage; GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ai_readonly;"])
    print(f"loaded {len(rows)} rules: operative {n_seed} numeric (quote-matched, NOT owner-verified) + {n_act} activity rows + {n_txt} text-only; proposed (PC120) {n_prop}")

if __name__ == "__main__":
    main()
