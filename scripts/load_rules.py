#!/usr/bin/env python3
"""Load structured rules into analytics.rules.

Sources:
  1. config/rules_seed/*.yaml   numeric standards. Each `quote` must occur verbatim (normalised) in the chunk text for `standard_ref`,
                                otherwise the load FAILS and lists every bad entry (no unverified numbers reach the database).
  2. data/aup/activity_rows.jsonl   zone activity tables (P/C/RD/D/NC/Pr) parsed from the plan PDFs.
  3. every other zone standard section (X.6.n) without a seed becomes a text-only rule (evaluable=false -> NEEDS_PROFESSIONAL).
Requires analytics.rule_text_chunks (scripts/load_rule_chunks.py). Run: python3 scripts/load_rules.py
"""
import csv, io, json, os, re, subprocess, sys
from datetime import date
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
STATUS_CLASS = {"P": "permitted", "C": "controlled", "RD": "restricted_discretionary", "D": "discretionary", "NC": "non_complying", "Pr": "prohibited"}
ZONE_CODE = {"H1": 23, "H2": 20, "H3": 19, "H4": 18, "H5": 60, "H6": 8, "H8": 35, "H9": 10, "H10": 22, "H11": 7, "H12": 44, "H13": 12, "H14": 49,
             "H15": 1, "H16": 5, "H17": 17, "H18": 4, "H20": 68, "H21": 69, "H22": 26, "H24": 53, "H25": 55, "H27": 52, "H28": 51, "H29": 63, "H30": 64}

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

def main():
    env()
    chunks = {}
    out = psql(["-F", "\x1f", "-c", "SELECT section_ref, id, pc120_flagged, replace(text, E'\\n', ' '), source_url, ref_unverified FROM analytics.rule_text_chunks ORDER BY id"], capture=True).stdout
    for line in out.splitlines():
        ref, cid, pc, text, url, unv = line.split("\x1f", 5)
        chunks.setdefault(ref, dict(id=int(cid), pc=pc == "t", text=norm(text), url=url, unverified=unv == "t"))
    zones = dict(l.split("|") for l in psql(["-c", "SELECT code || '|' || zone_name FROM core.zone_lookup"], capture=True).stdout.splitlines())
    pv = int(psql(["-c", "SELECT id FROM analytics.plan_versions WHERE plan_name = 'Auckland Unitary Plan'"], capture=True).stdout.strip())
    today = date.today().isoformat()
    rows, bad = [], []
    seeded = set()
    for f in sorted((ROOT / "config/rules_seed").glob("*.yaml")):
        for r in yaml.safe_load(f.read_text()):
            c = chunks.get(r["standard_ref"])
            if c is None: bad.append((r["standard_ref"], r["parameter"], "no such section in extracted plan text")); continue
            if norm(r["quote"]) not in c["text"]: bad.append((r["standard_ref"], r["parameter"], f"quote not found: {r['quote']!r}")); continue
            seeded.add(r["standard_ref"])
            is_act = r["topic"] == "activity_status"
            zname = zones[str(r["zone_code"])] if r["zone_code"] is not None else ("Māori land (Auckland-wide, E20)" if r["chapter"] == "E20" else "Residential (all residential zones)")
            rows.append(dict(zone=zname, topic=r["topic"], parameter=r["parameter"], operator=r["operator"], value_num=r["value"] if isinstance(r["value"], (int, float)) else None, value_text=None if isinstance(r["value"], (int, float)) else str(r["value"]),
                             unit=r["unit"], applies_if={**({"zone_code": r["zone_code"]} if r["zone_code"] is not None else {}), **({"activity": r["activity"]} if r.get("activity") else {}), **(r.get("applies_if") or {})},
                             status_class=STATUS_CLASS.get(str(r["value"])) if is_act else "standard", standard_ref=r["standard_ref"],
                             section_ref=r["standard_ref"], chunk_id=c["id"], quote=r["quote"], rule_text=None, url=c["url"], evaluable=r["evaluable"],
                             notes="; ".join(x for x in [r.get("note"), "PC 120 annotation on this section (operative text shown; confirm legal effect)" if c["pc"] else None] if x)))
    if bad:
        print(f"{len(bad)} seed entries failed verification:"); [print("  ", b) for b in bad]; sys.exit(1)
    n_seed = len(rows)
    # activity tables
    n_act = 0
    for line in open(ROOT / "data/aup/activity_rows.jsonl"):
        a = json.loads(line); code = a["zone_code"]
        c = chunks.get(f"{code}.4")
        note = "; ".join(x for x in [a.get("note"), None if a["status"] else "status not parsed from table: read the plan text", "PC 120 annotation on this section (operative text shown; confirm legal effect)" if c and c["pc"] else None] if x)
        rows.append(dict(zone=zones[str(ZONE_CODE[code])], topic="activity_status", parameter=a["id"], operator=None, value_num=None, value_text=a["status"], unit=None,
                         applies_if={"zone_code": ZONE_CODE[code], "activity": a["activity"]}, status_class=STATUS_CLASS.get(a["status"]), standard_ref="; ".join(a["standards"]) or None,
                         section_ref=f"{code}.4.1 ({a['id']})", chunk_id=c["id"] if c else None, quote=a["activity"], rule_text=a["standards_text"] or None, url=a["url"],
                         evaluable=a["status"] in STATUS_CLASS, notes=note or None)); n_act += 1
    # text-only standards
    n_txt = 0
    for ref, c in chunks.items():
        m = re.match(r"^(H\d+)\.6\.\d+$", ref)
        if m and m.group(1) in ZONE_CODE and ref not in seeded and not c["unverified"]:
            heading = psql(["-c", f"SELECT heading FROM analytics.rule_text_chunks WHERE id = {c['id']}"], capture=True).stdout.strip()
            rows.append(dict(zone=zones[str(ZONE_CODE[m.group(1)])], topic="standard_text", parameter=heading[:120], operator=None, value_num=None, value_text=None, unit=None,
                             applies_if={"zone_code": ZONE_CODE[m.group(1)]}, status_class="standard", standard_ref=ref, section_ref=ref, chunk_id=c["id"], quote=None, rule_text=None,
                             url=c["url"], evaluable=False, notes="no numeric extraction: NEEDS_PROFESSIONAL unless a seed rule exists" + ("; PC 120 annotation (confirm legal effect)" if c["pc"] else ""))); n_txt += 1
    buf = io.StringIO(); w = csv.writer(buf)
    for r in rows:
        w.writerow(["Auckland Council", pv, r["zone"], "", r["topic"], r["parameter"], r["operator"] or "", "" if r["value_num"] is None else r["value_num"], r["value_text"] or "", r["unit"] or "",
                    json.dumps(r["applies_if"], ensure_ascii=False), r["status_class"] or "", r["standard_ref"] or "", r["section_ref"], r["chunk_id"] or "", r["quote"] or "", r["rule_text"] or "",
                    r["url"], today, "t" if r["evaluable"] else "f", r["notes"] or ""])
    psql(["-c", "TRUNCATE analytics.rules RESTART IDENTITY"]); 
    psql(["-c", "DROP TABLE IF EXISTS analytics._r_stage; CREATE TABLE analytics._r_stage (council text, pv int, zone text, overlay text, topic text, parameter text, operator text, value_num text, value_text text, unit text, applies_if text, status_class text, standard_ref text, section_ref text, chunk_id text, quote text, rule_text text, url text, lv date, evaluable boolean, notes text)"])
    psql(["-c", "\\copy analytics._r_stage FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue())
    psql(["-c", "INSERT INTO analytics.rules (council, plan_version_id, zone, overlay, activity, topic, parameter, operator, value_num, value_text, unit, applies_if, status_class, standard_ref, section_ref, chunk_id, quote, rule_text, source_url, last_verified, evaluable, notes) "
                "SELECT council, pv, zone, NULLIF(overlay,''), applies_if::jsonb->>'activity', topic, parameter, NULLIF(operator,''), NULLIF(value_num,'')::numeric, NULLIF(value_text,''), NULLIF(unit,''), applies_if::jsonb, NULLIF(status_class,''), NULLIF(standard_ref,''), section_ref, NULLIF(chunk_id,'')::int, NULLIF(quote,''), NULLIF(rule_text,''), url, lv, evaluable, NULLIF(notes,'') FROM analytics._r_stage; DROP TABLE analytics._r_stage; "
                "GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ai_readonly;"])
    print(f"loaded {len(rows)} rules: {n_seed} verified numeric standards, {n_act} activity-table rows, {n_txt} text-only standards")

if __name__ == "__main__":
    main()
