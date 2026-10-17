#!/usr/bin/env python3
"""Load data/aup/manifest.json + chunks.jsonl into analytics.source_documents and analytics.rule_text_chunks (idempotent: schema re-created)."""
import csv, io, json, os, subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUP = ROOT / "data" / "aup"

def env():
    for l in (ROOT / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k, v)

def psql(args, **kw):
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    return subprocess.run(["psql", "-h", os.environ.get("PGHOST", "localhost"), "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"],
                           "-v", "ON_ERROR_STOP=1", "-q", *args], check=True, env=e, **kw)

def main():
    env()
    psql(["-f", str(ROOT / "db/sql/60_rules_schema.sql")])
    man = json.loads((AUP / "manifest.json").read_text())
    today = date.today().isoformat()
    buf = io.StringIO(); w = csv.writer(buf)
    for i, f in enumerate(man["files"], 1):
        w.writerow([i, "Auckland Council", "plan_chapter", f["chapter"], f["title"], f["url"], f["sha256"], f["bytes"], man["index_date"], today])
    psql(["-c", "DROP TABLE IF EXISTS analytics._sd_stage; CREATE TABLE analytics._sd_stage (id int, council text, doc_kind text, chapter text, title text, url text, sha256 text, bytes bigint, index_date text, retrieved date)"])
    psql(["-c", "\\copy analytics._sd_stage FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue(), text=True)
    psql(["-c", "INSERT INTO analytics.source_documents (id, council, doc_kind, chapter, title, url, sha256, bytes, plan_version_id, index_date, retrieved_at) "
                "SELECT id, council, doc_kind, chapter, title, url, sha256, bytes, (SELECT id FROM analytics.plan_versions WHERE plan_name='Auckland Unitary Plan'), index_date, retrieved FROM analytics._sd_stage; "
                "DROP TABLE analytics._sd_stage; SELECT setval('analytics.source_documents_id_seq', (SELECT max(id) FROM analytics.source_documents));"])
    url_to_id = {f["url"]: i for i, f in enumerate(man["files"], 1)}
    buf = io.StringIO(); w = csv.writer(buf); n = 0
    for line in open(AUP / "chunks.jsonl"):
        c = json.loads(line)
        if not c["text"].strip(): continue
        n += 1
        w.writerow([url_to_id[c["source_url"]], "Auckland Council", c["chapter_title"], c["ref"], "t" if c["ref_unverified"] else "f", c["heading"],
                    c["page_start"], c["page_end"], "t" if c["pc_note"] else "f", c["text"], c["source_url"], today])
    psql(["-c", "DROP TABLE IF EXISTS analytics._ch_stage; CREATE TABLE analytics._ch_stage (sd int, council text, chapter text, ref text, unver boolean, heading text, p1 int, p2 int, pc boolean, text text, url text, lv date)"])
    psql(["-c", "\\copy analytics._ch_stage FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue(), text=True)
    psql(["-c", "INSERT INTO analytics.rule_text_chunks (source_document_id, council, chapter, section_ref, ref_unverified, heading, page_start, page_end, pc120_flagged, text, tsv, plan_version_id, source_url, last_verified) "
                "SELECT sd, council, chapter, ref, unver, heading, p1, p2, pc, text, setweight(to_tsvector('english', coalesce(heading,'')), 'A') || setweight(to_tsvector('english', text), 'B'), "
                "(SELECT id FROM analytics.plan_versions WHERE plan_name='Auckland Unitary Plan'), url, lv FROM analytics._ch_stage; DROP TABLE analytics._ch_stage; ANALYZE analytics.rule_text_chunks;"])
    print(f"loaded {len(man['files'])} source documents and {n} chunks")

if __name__ == "__main__":
    main()
