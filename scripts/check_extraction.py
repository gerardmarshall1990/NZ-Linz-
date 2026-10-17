#!/usr/bin/env python3
"""Cross-check every numeric operative rule against BOTH the PDF text layer and OCR, and record how it was extracted (decision 17).

For each rule's quote and the pages of its section we record:
  text_layer_match  quote found in the PDF text layer of those pages
  ocr_match         quote found in the Tesseract OCR text of those pages
  ocr_confidence    mean Tesseract word confidence (0-100) of the OCR lines that match the quote (re-OCR of just those pages at 300 dpi), NULL if no OCR line matched
  extraction_method 'text_layer+ocr' (both agree), 'text_layer' (layer only), 'ocr_only' (layer lacks it: needs owner eyes), 'none'
  quote_page        first page (in the chapter PDF) where the quote was found
It never sets owner_verified. Run after load_rules.py: python3 scripts/check_extraction.py
"""
import json, os, re, subprocess, tempfile
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
AUP = ROOT / "data" / "aup"
DPI = 300

def env():
    for l in (ROOT / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k, v)

def psql(args, **kw):
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    return subprocess.run(["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-v", "ON_ERROR_STOP=1", "-q", "-At", *args],
                          check=True, env=e, capture_output=kw.pop("capture", False), text=True, **kw)

def norm(t):
    t = t.lower().replace("²", "2").replace("?", "2").replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()

def page_ocr_conf(pdf_path, page_no):
    """Tesseract TSV at 300 dpi for one page -> list of (norm line text, mean conf). Cached."""
    cache = AUP / "ocr_conf" / f"{pdf_path.stem}_p{page_no}.json"
    if cache.exists(): return json.loads(cache.read_text())
    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "p.png"; pymupdf.open(pdf_path)[page_no - 1].get_pixmap(dpi=DPI).save(png)
        tsv = subprocess.run(["tesseract", str(png), "-", "--psm", "4", "-l", "eng", "tsv"], capture_output=True, text=True, env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout
    lines = {}
    for row in tsv.splitlines()[1:]:
        f = row.split("\t")
        if len(f) < 12 or not f[11].strip() or float(f[10]) < 0: continue
        e = lines.setdefault((f[2], f[3], f[4]), {"w": [], "c": []}); e["w"].append((int(f[6]), f[11])); e["c"].append(float(f[10]))
    out = [(" ".join(w for _, w in sorted(v["w"])), sum(v["c"]) / len(v["c"])) for v in lines.values()]
    cache.write_text(json.dumps(out)); return out

def main():
    env()
    man = {f["url"]: f for f in json.loads((AUP / "manifest.json").read_text())["files"]}
    rows = psql(["-F", "\x1f", "-c", """SELECT r.id, r.quote, c.page_start, c.page_end, c.source_url FROM analytics.rules r JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id
                 WHERE r.status = 'operative' AND r.topic NOT IN ('activity_status','standard_text') AND r.quote IS NOT NULL ORDER BY r.id"""], capture=True).stdout.splitlines()
    docs, ocr_cache, updates = {}, {}, []
    stats = {"text_layer+ocr": 0, "text_layer": 0, "ocr_only": 0, "none": 0}
    for line in rows:
        rid, quote, p1, p2, url = line.split("\x1f"); p1, p2 = int(p1), int(p2); q = norm(quote)
        f = man[url]; pdf = ROOT / f["pdf"]
        d = docs.setdefault(pdf, pymupdf.open(pdf))
        ocr = ocr_cache.setdefault(pdf, {p["page"]: p for p in json.loads((AUP / "ocr" / Path(f["pdf"]).relative_to("data/aup/pdf").with_suffix(".json")).read_text())})
        pages = list(range(p1, min(p2, len(d)) + 1)) + ([p2 + 1] if p2 < len(d) else [])
        layer = {n: norm(d[n - 1].get_text("text")) for n in pages}
        ocrt = {n: norm(" ".join(l["text"] for l in ocr[n]["lines"])) for n in pages}
        # also allow quotes that span a page break
        lay_join = " ".join(layer[n] for n in pages); ocr_join = " ".join(ocrt[n] for n in pages)
        lm, om = q in lay_join, q in ocr_join
        page = next((n for n in pages if q in layer[n]), None) or next((n for n in pages if q in ocrt[n]), None) or p1
        conf = None
        if om:
            qw = set(q.split()); best = []
            for n in pages:
                for t, c in page_ocr_conf(pdf, n):
                    tw = set(norm(t).split())
                    if len(qw & tw) >= max(2, len(qw) // 2) or norm(t) in q: best.append(c)
            conf = round(sum(best) / len(best), 1) if best else None
        m = "text_layer+ocr" if lm and om else "text_layer" if lm else "ocr_only" if om else "none"; stats[m] += 1
        updates.append(f"UPDATE analytics.rules SET text_layer_match = {str(lm).lower()}, ocr_match = {str(om).lower()}, ocr_confidence = {conf if conf is not None else 'NULL'}, "
                       f"extraction_method = '{m}', quote_page = {page} WHERE id = {rid};")
    # proposed rows: evidence is Council's PC120 PDFs/info sheets read from the text layer (tracked changes from drawing geometry)
    updates.append("UPDATE analytics.rules SET extraction_method = CASE WHEN evidence_doc LIKE 'info_sheet%' THEN 'info_sheet_text_layer' ELSE 'pc120_text_layer_tracked_changes' END, text_layer_match = true WHERE status = 'proposed';")
    psql(["-c", "\n".join(updates)])
    print("extraction methods:", stats, "of", len(rows), "operative numeric rules")

if __name__ == "__main__":
    main()
