#!/usr/bin/env python3
"""Load files placed by hand in docs/sources_manual/ (used where a site blocks scripted access).

Folders:
  healthcert/       CSV/XLSX export of the HealthCERT certified providers list -> raw.manual_healthcert (all columns as text)
  tpk_maori_land/   CSV/XLSX/GeoJSON-as-CSV exports of Te Puni Kōkiri / Māori Land Court public data -> raw.manual_maori_land
  other/            any other CSV/XLSX -> raw.manual_other (one row per source row, JSON payload)
  standards/        PDFs (e.g. Ngā Paerewa NZS 8134:2021) -> raw.manual_doc_pages (page text via pdftotext)
  council_forms/    PDFs of council application forms/checklists -> raw.manual_doc_pages
Every row records source file, sha256 and load time. Re-running reloads each table from the files (idempotent). Files are never modified.
"""
import csv, hashlib, io, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "docs" / "sources_manual"
TABLE_FOLDERS = {"healthcert": "manual_healthcert", "tpk_maori_land": "manual_maori_land"}

def env():
    for l in (ROOT / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k, v)

def psql(args, **kw):
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    return subprocess.run(["psql", "-h", os.environ.get("PGHOST", "localhost"), "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"],
                           "-v", "ON_ERROR_STOP=1", "-q", *args], check=True, env=e, **kw)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def read_table(p):
    if p.suffix.lower() == ".csv":
        with open(p, newline="", encoding="utf-8-sig") as f:
            rdr = csv.reader(f); hdr = next(rdr); return hdr, list(rdr)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        ws = openpyxl.load_workbook(p, read_only=True, data_only=True).active
        it = ws.iter_rows(values_only=True)
        hdr = [str(c) if c is not None else "" for c in next(it)]
        return hdr, [["" if c is None else str(c) for c in r] for r in it]
    raise ValueError(p)

def norm(c, i): 
    c = "".join(ch.lower() if ch.isalnum() else "_" for ch in (c or f"col{i}")).strip("_")
    return c or f"col{i}"

def load_tables(folder, table):
    files = sorted(f for f in (MAN / folder).glob("*") if f.suffix.lower() in (".csv", ".xlsx", ".xlsm"))
    if not files:
        psql(["-c", f"DROP TABLE IF EXISTS raw.{table}"]); print(f"{folder}: no files (table cleared)"); return
    cols = {}
    data = []
    for f in files:
        hdr, rows = read_table(f); h = [norm(c, i) for i, c in enumerate(hdr)]
        for c in h: cols.setdefault(c, None)
        for n, r in enumerate(rows, 1):
            data.append((f.name, sha(f), n, dict(zip(h, r + [""] * (len(h) - len(r))))))
    names = list(cols)
    ddl = f"DROP TABLE IF EXISTS raw.{table}; CREATE TABLE raw.{table} (_source_file text, _sha256 text, _row int, _loaded_at timestamptz, " + \
          ", ".join(f'"{c}" text' for c in names) + ");"
    psql(["-c", ddl])
    buf = io.StringIO(); w = csv.writer(buf); now = datetime.now(timezone.utc).isoformat()
    for fn, h, n, d in data: w.writerow([fn, h, n, now] + [d.get(c, "") for c in names])
    psql(["-c", f"\\copy raw.{table} FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue(), text=True)
    print(f"{folder}: {len(data)} rows from {len(files)} file(s) -> raw.{table}")

def load_other():
    files = sorted(f for f in (MAN / "other").glob("*") if f.suffix.lower() in (".csv", ".xlsx", ".xlsm"))
    psql(["-c", "DROP TABLE IF EXISTS raw.manual_other; CREATE TABLE raw.manual_other (_source_file text, _sha256 text, _row int, _loaded_at timestamptz, payload jsonb);"])
    buf = io.StringIO(); w = csv.writer(buf); now = datetime.now(timezone.utc).isoformat(); n = 0
    for f in files:
        hdr, rows = read_table(f); h = [norm(c, i) for i, c in enumerate(hdr)]; s = sha(f)
        for i, r in enumerate(rows, 1): w.writerow([f.name, s, i, now, json.dumps(dict(zip(h, r)))]); n += 1
    psql(["-c", "\\copy raw.manual_other FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue(), text=True)
    print(f"other: {n} rows from {len(files)} file(s) -> raw.manual_other")

def load_pdfs():
    psql(["-c", "DROP TABLE IF EXISTS raw.manual_doc_pages; CREATE TABLE raw.manual_doc_pages (doc_kind text, filename text, sha256 text, page int, text text, loaded_at timestamptz);"])
    buf = io.StringIO(); w = csv.writer(buf); now = datetime.now(timezone.utc).isoformat(); n = 0; nf = 0
    for kind in ("standards", "council_forms"):
        for f in sorted((MAN / kind).glob("*.pdf")):
            txt = subprocess.run(["pdftotext", "-layout", str(f), "-"], capture_output=True, text=True, check=True).stdout
            s = sha(f); nf += 1
            for i, page in enumerate(txt.split("\f"), 1):
                if page.strip(): w.writerow([kind, f.name, s, i, page, now]); n += 1
    psql(["-c", "\\copy raw.manual_doc_pages FROM STDIN WITH (FORMAT csv)"], input=buf.getvalue(), text=True)
    print(f"pdfs: {n} pages from {nf} file(s) -> raw.manual_doc_pages")

if __name__ == "__main__":
    env()
    for folder, table in TABLE_FOLDERS.items(): load_tables(folder, table)
    load_other(); load_pdfs()
