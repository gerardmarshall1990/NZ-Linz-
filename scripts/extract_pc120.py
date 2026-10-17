#!/usr/bin/env python3
"""Split Council's PC120 plan-text PDFs into sections with separate operative and proposed readings (tracked changes drawn as lines).

Inputs (downloaded to data/pc120/pdf by scripts/ingest_pc120.py):
  notified    55-pc120-chapter-h-residential.pdf   (notified 3 Nov 2025; chapters H1-H6)
  amended     05-chapter-h-...-Mixed-Housing-Urban-Zone.pdf, 06-chapter-h-...-Terrace-Housing-...pdf   (proposed amendments, Aug 2026; these supersede the
              notified text for H5 and H6)
Output: data/pc120/sections.jsonl with {doc, chapter, ref, heading, operative_text, proposed_text, changed, page_start}.
Operative text here is only used to detect change; the operative rules in analytics.rules come from the operative chapter PDFs.
"""
import json, re, sys
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "pc120" / "pdf"
sys.path.insert(0, str(Path(__file__).resolve().parent))
REF = re.compile(r"^(?P<ref>[A-Z]{1,2}\d+(?:\.\d+)+)\.?\s+(?P<title>\S.*)$")
SKIP = re.compile(r"^(Table|Figure|Purpose|Notes?)\b", re.I)
DOCS = [("notified", "55-pc120-chapter-h-residential.pdf", "notified 3 November 2025"),
        ("amended_mhu", "05-chapter-h-Residential-Mixed-Housing-Urban-Zone.pdf", "proposed amendments August 2026"),
        ("amended_thab", "06-chapter-h-residential-terrace-housing-and-apartment-buildings-zone.pdf", "proposed amendments August 2026")]

def thin_rects(page):
    out = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if dr.get("fill") == (0.0, 0.0, 0.0) and r.height < 1.6 and r.width > 2 and r.width < 330:
            out.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
    return out

def state(c, rects):
    x0, y0, x1, y1 = c["bbox"]; h = y1 - y0; cx = (x0 + x1) / 2; st = "keep"
    for rx0, rx1, ry in rects:
        if rx0 - 0.5 <= cx <= rx1 + 0.5:
            if y0 + 0.38 * h <= ry <= y0 + 0.68 * h: return "del"
            if y1 - 0.12 * h <= ry <= y1 + 0.28 * h: st = "ins"
    return st

def lines_of(page):
    rects = thin_rects(page); out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            if l["bbox"][0] < 40 or l["bbox"][1] < 60 or l["bbox"][1] > 780: continue
            ops, prs, bold = [], [], True
            for s in l["spans"]:
                isb = bool(s["flags"] & 16) or "Bold" in s["font"]
                for c in s["chars"]:
                    st = "keep" if c["c"] == " " else state(c, rects)
                    if c["c"] != " " and not isb: bold = False
                    if st != "ins": ops.append(c["c"])
                    if st != "del": prs.append(c["c"])
            op, pr = "".join(ops).strip(), "".join(prs).strip()
            if op or pr: out.append({"x": l["bbox"][0], "y": l["bbox"][1], "op": op, "pr": pr, "bold": bold})
    out.sort(key=lambda r: (round(r["y"] / 3), r["x"])); return out

def run(doc_key, fname, label):
    d = pymupdf.open(PDF / fname); chunks = []; cur = None
    def start(ref, title, page):
        nonlocal cur
        if cur: chunks.append(cur)
        cur = {"doc": doc_key, "doc_label": label, "file": fname, "ref": ref, "heading": title, "page_start": page, "op": [], "pr": []}
    start("front", fname, 1)
    for pn, pg in enumerate(d, 1):
        for r in lines_of(pg):
            if re.match(r"^Plan Change 120|^H\d Residential|^\d+$", r["pr"] or r["op"]): continue
            m = REF.match(r["pr"]) if r["bold"] and r["pr"] else None
            if m and not SKIP.match(m.group("title")) and re.match(r"^H\d", m.group("ref")): start(m.group("ref"), m.group("title"), pn); continue
            if cur is not None:
                if r["op"]: cur["op"].append(r["op"])
                if r["pr"]: cur["pr"].append(r["pr"])
    if cur: chunks.append(cur)
    out = []
    for c in chunks:
        op, pr = re.sub(r"\s+", " ", " ".join(c["op"])).strip(), re.sub(r"\s+", " ", " ".join(c["pr"])).strip()
        out.append({"doc": c["doc"], "doc_label": c["doc_label"], "file": c["file"], "ref": c["ref"], "heading": c["heading"], "page_start": c["page_start"],
                    "operative_text": op, "proposed_text": pr, "changed": op != pr})
    return out

def main():
    allc = []
    for k, f, lab in DOCS:
        c = run(k, f, lab); allc += c; print(f"{k}: {len(c)} sections, {sum(x['changed'] for x in c)} changed", flush=True)
    with open(ROOT / "data/pc120/sections.jsonl", "w") as fh:
        for c in allc: fh.write(json.dumps(c, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
