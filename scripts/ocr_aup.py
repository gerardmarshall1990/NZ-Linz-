#!/usr/bin/env python3
"""OCR every page of the downloaded AUP chapter PDFs (tesseract TSV) so incomplete text layers can be repaired.

Some AUP PDFs render parts of pages (e.g. tables, numbered lists under tracked changes) without putting the text in the PDF text layer.
For each page we store: text-layer alnum char count, OCR alnum char count, and OCR lines with positions (PDF points).
Output: data/aup/ocr/<chapter>/<file>.json  (idempotent; skips files already done). Run: python3 -I scripts/ocr_aup.py
"""
import os, json, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
AUP = ROOT / "data" / "aup"
DPI = 200

def ocr_pdf(pdf_rel):
    pdf = ROOT / pdf_rel
    out = AUP / "ocr" / Path(pdf_rel).relative_to("data/aup/pdf").with_suffix(".json")
    if out.exists(): return pdf_rel, 0
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf); pages = []
    with tempfile.TemporaryDirectory() as td:
        for n, page in enumerate(doc, 1):
            layer = sum(ch.isalnum() for ch in page.get_text("text"))
            png = Path(td) / f"p{n}.png"
            page.get_pixmap(dpi=DPI).save(png)
            tsv = subprocess.run(["tesseract", str(png), "-", "--psm", "4", "-l", "eng", "tsv"], capture_output=True, text=True, env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout
            lines = {}
            for row in tsv.splitlines()[1:]:
                f = row.split("\t")
                if len(f) < 12 or not f[11].strip() or float(f[10]) < 0: continue
                key = (f[2], f[3], f[4])
                l, t, w, h = (int(f[6]), int(f[7]), int(f[8]), int(f[9]))
                e = lines.setdefault(key, {"x0": l, "y0": t, "words": []})
                e["x0"] = min(e["x0"], l); e["y0"] = min(e["y0"], t); e["words"].append((l, f[11]))
            ol = [{"x": round(v["x0"] * 72 / DPI, 1), "y": round(v["y0"] * 72 / DPI, 1),
                   "text": " ".join(w for _, w in sorted(v["words"]))} for v in lines.values()]
            ol.sort(key=lambda r: (round(r["y"] / 3), r["x"]))
            pages.append({"page": n, "layer_alnum": layer, "ocr_alnum": sum(ch.isalnum() for r in ol for ch in r["text"]), "lines": ol})
    out.write_text(json.dumps(pages))
    return pdf_rel, len(pages)

def main():
    files = [f["pdf"] for f in json.loads((AUP / "manifest.json").read_text())["files"]]
    total = 0
    with ProcessPoolExecutor(max_workers=4) as ex:
        for name, n in ex.map(ocr_pdf, files):
            total += n; print(f"{n:4} pages  {name}", flush=True)
    print("pages OCRed this run:", total)

if __name__ == "__main__":
    main()
