#!/usr/bin/env python3
"""Split the downloaded AUP chapter PDFs into citable chunks (section ref + heading + text) -> data/aup/chunks.jsonl.

Headings: bold lines. Numbered headings ("H4.6. Standards", "E38.6.1. Site size and shape") are used as-is.
Zone standards (H1-H30 section X.6 "Standards") are printed WITHOUT numbers in the PDFs, so they are numbered by position
within the Standards section (H4.6.1, H4.6.2 ...). That derived numbering is validated against the chapter's own activity-table
cross-references ("Standard H4.6.4 Building height"); mismatches are reported in data/aup/numbering_check.json.
Run: python3 -I scripts/build_rule_chunks.py
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
AUP = ROOT / "data" / "aup"
REF = re.compile(r"^(?P<ref>[A-Z]{1,2}\d+(?:\.\d+)*)\.?\s+(?P<title>\S.*)$")
SKIP_TITLE = re.compile(r"^(Table|Figure|Purpose|Activity|Notes?)\b", re.I)  # unnumbered bold lines (table headers etc.)
SKIP_REF_TITLE = re.compile(r"^(Table|Figure|Purpose|Notes?)\b", re.I)  # titles of numbered headings
FOOTER = re.compile(r"^Auckland Unitary Plan\b|^\d+$")
PC_NOTE = re.compile(r"^\[(new text to be inserted|text to be deleted|text deleted|.*to be (inserted|deleted|replaced).*)\]$|^PC\s?\d+\s*\(see Modifications\)", re.I)

def page_lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            sp = l["spans"]
            txt = "".join(s["text"] for s in sp).strip()
            if not txt: continue
            bold = all((s["flags"] & 16) or "Bold" in s["font"] for s in sp if s["text"].strip())
            y = l["bbox"][1]
            if y < 60 or y > 780: continue  # running header/footer
            if l["bbox"][0] < 40: continue  # left-margin change annotations ("PC 120 (see Modifications)")
            out.append({"x": l["bbox"][0], "y": y, "bold": bold, "text": txt, "size": sp[0]["size"]})
    out.sort(key=lambda r: (round(r["y"] / 3), r["x"]))
    return out

OCR_REF = re.compile(r"^[A-Z]{1,2}\d+(?:\.\d+)+\.\s+[A-Z]")

def ocr_pages(entry):
    f = AUP / "ocr" / Path(entry["pdf"]).relative_to("data/aup/pdf").with_suffix(".json")
    if not f.exists(): return {}
    return {p["page"]: p for p in json.loads(f.read_text())}

def norm(t): return re.sub(r"[^a-z0-9]", "", t.lower())

def shingles(n, k=6): return {n[i:i + k] for i in range(max(1, len(n) - k + 1))}

def merge_ocr(layer, ocr_page, pn):
    """Conservative repair: add OCR lines (>= 8 alphanumerics) that the text layer lacks at the same height (missing numbered paragraphs)."""
    extra = []
    for o in ocr_page["lines"]:
        n = norm(o["text"])
        if len(n) < 8 or o["y"] < 60 or o["y"] > 780 or o["x"] < 40 or FOOTER.match(o["text"]) or PC_NOTE.match(o["text"]): continue
        local = "".join(norm(r["text"]) for r in layer if abs(r["y"] - o["y"]) < 16)
        sh = shingles(n)
        if sum(1 for g in sh if g in local) / len(sh) >= 0.6: continue
        extra.append({"x": o["x"], "y": o["y"], "bold": False, "text": o["text"], "size": 11.0, "ocr": True})
    return extra

def ocr_replace_page(ocr_page, pn):
    """Whole-page OCR lines for pages whose text layer is clearly incomplete (no font info: numbered headings recognised by pattern)."""
    out = []
    for o in ocr_page["lines"]:
        if o["y"] < 60 or o["y"] > 780 or o["x"] < 40 or FOOTER.match(o["text"]) or PC_NOTE.match(o["text"]): continue
        out.append({"x": o["x"], "y": o["y"], "bold": bool(OCR_REF.match(o["text"]) and o["x"] < 125 and len(o["text"]) < 110),
                    "text": o["text"], "size": 11.0, "ocr": True})
    return out

def page_is_thin(ocr_page): return ocr_page["ocr_alnum"] > 1.15 * ocr_page["layer_alnum"] + 60

def chunk_chapter(entry):
    doc = pymupdf.open(ROOT / entry["pdf"])
    ocr = ocr_pages(entry)
    layer_has_numbers = any(
        (l["bold"] and re.match(r"^[A-Z]{1,2}\d+\.6\.\d+\.\s", l["text"])) for pg in doc for l in page_lines(pg))
    chap_code = re.match(r"^([A-Z]{1,2}\d+)", entry["title"])
    chap_code = chap_code.group(1) if chap_code else None
    lines = []
    for pn, page in enumerate(doc, 1):
        pl = page_lines(page)
        if pn in ocr:
            if page_is_thin(ocr[pn]) and (layer_has_numbers or not re.match(r"^H\d+ ", entry["title"])):
                pl = ocr_replace_page(ocr[pn], pn)   # (zone chapters whose standards are unnumbered, e.g. H4, keep font info instead)
            else:
                pl = sorted(pl + merge_ocr(pl, ocr[pn], pn), key=lambda r: (round(r["y"] / 3), r["x"]))
        for r in pl:
            r["page"] = pn; lines.append(r)
    # merge wrapped bold heading lines
    chunks, cur, std_counter, std_parent = [], None, 0, None
    has_printed_numbers = layer_has_numbers
    def start(ref, title, derived, page):
        nonlocal cur
        if cur: chunks.append(cur)
        cur = {"ref": ref, "heading": title, "derived": derived, "page_start": page, "page_end": page, "lines": []}
    start(chap_code or entry["title"], entry["title"], False, 1)
    i = 0
    while i < len(lines):
        r = lines[i]
        t = r["text"]
        if PC_NOTE.match(t):
            if cur is not None: cur["pc_note"] = True
            i += 1; continue
        if (entry["title"].startswith("J1") and cur is not None and cur["ref"].startswith("J1.4") and r["bold"] and 100 < r["x"] < 125
                and 2 < len(t) < 90 and not REF.match(t) and not FOOTER.match(t)):
            start(f"J1.4 {t}", t, False, r["page"]); i += 1; continue   # one chunk per defined term
        if r["bold"] and not FOOTER.match(t):
            m = REF.match(t)
            if m and not SKIP_REF_TITLE.match(m.group("title")) and re.match(r"^[A-Z]{1,2}\d+", m.group("ref")) and (chap_code is None or m.group("ref").startswith(chap_code)):
                title = m.group("title"); j = i + 1
                while j < len(lines) and lines[j]["bold"] and abs(lines[j]["y"] - lines[j - 1]["y"]) < 20 and lines[j]["page"] == r["page"] \
                        and not REF.match(lines[j]["text"]) and not SKIP_TITLE.match(lines[j]["text"]) and lines[j]["x"] - r["x"] < 60:
                    if not PC_NOTE.match(lines[j]["text"]): title += " " + lines[j]["text"]
                    j += 1
                ref = m.group("ref")
                start(ref, title, False, r["page"])
                std_parent = ref if re.search(r"^[A-Z]{1,2}\d+\.6$", ref) and title.lower().startswith("standards") else (std_parent if ref.startswith((std_parent or "~") + ".") else None)
                if std_parent == ref: std_counter = 0
                i = j; continue
            # unnumbered bold heading inside a zone Standards section
            if std_parent and not has_printed_numbers and r["x"] > 120 and not SKIP_TITLE.match(t) and not t.startswith(("(", "•")) and len(t) < 110:
                title = t; j = i + 1
                while j < len(lines) and lines[j]["bold"] and lines[j]["page"] == r["page"] and 0 < lines[j]["y"] - lines[j - 1]["y"] < 20 \
                        and not SKIP_TITLE.match(lines[j]["text"]) and lines[j]["x"] > 100 and not PC_NOTE.match(lines[j]["text"]):
                    title += " " + lines[j]["text"]; j += 1
                # a real standard heading is followed by "Purpose:" (or is the leading "Activities listed in Table..." heading)
                k = j
                while k < len(lines) and (PC_NOTE.match(lines[k]["text"]) or lines[k].get("ocr")): k += 1
                nxt = lines[k]["text"] if k < len(lines) else ""
                if not (nxt.startswith("Purpose") or (std_counter == 0 and title.startswith("Activities listed"))):
                    if cur is not None: cur["lines"].append(t)
                    i += 1; continue
                std_counter += 1
                start(f"{std_parent}.{std_counter}", title, True, r["page"])
                i = j; continue
        if cur is not None:
            cur["lines"].append(t); cur["page_end"] = r["page"]
        i += 1
    if cur: chunks.append(cur)
    return chunks

def main():
    manifest = json.loads((AUP / "manifest.json").read_text())
    out, check = [], {}
    for e in manifest["files"]:
        chunks = chunk_chapter(e)
        text_all = "\n".join("\n".join(c["lines"]) for c in chunks)
        # validate derived standard numbers against cross-references in the same chapter
        xref = {}
        for m in re.finditer(r"Standard\s+([A-Z]{1,2}\d+\.6\.\d+)\s+([A-Z][^;:\n]{3,80}?)(?=[;:\n]|\s+Standard\s)", text_all.replace("\n", " ")):
            xref.setdefault(m.group(1), m.group(2).strip())
        derived = {c["ref"]: c["heading"] for c in chunks if c["derived"]}
        bad = {}
        for ref, name in xref.items():
            if ref in derived:
                a, b = re.sub(r"\W", "", derived[ref].lower()), re.sub(r"\W", "", name.lower())
                if not (a.startswith(b[:18]) or b.startswith(a[:18])): bad[ref] = {"derived": derived[ref], "xref": name}
        if derived: check[e["title"]] = {"derived": len(derived), "xrefs_checked": sum(1 for r in xref if r in derived), "mismatches": bad}
        validated = (not derived) or (check[e["title"]]["xrefs_checked"] >= 5 and not check[e["title"]]["mismatches"])
        for c in chunks:
            if c["derived"] and not validated:  # derived number could not be verified against the chapter's own cross-references
                c["ref"] = c["ref"] + "?"; c["unverified"] = True
            body = "\n".join(c["lines"]).strip()
            if not body and not c["derived"]: continue
            out.append({"chapter": e["chapter"], "chapter_title": e["title"], "source_url": e["url"], "sha256": e["sha256"],
                        "ref": c["ref"], "heading": re.sub(r"\s+", " ", c["heading"]).strip(), "derived_number": c["derived"],
                        "page_start": c["page_start"], "page_end": c["page_end"], "pc_note": bool(c.get("pc_note")), "ref_unverified": bool(c.get("unverified")), "text": body})
        print(f"{e['title'][:60]:60} chunks={len(chunks)}", flush=True)
    with open(AUP / "chunks.jsonl", "w") as f:
        for o in out: f.write(json.dumps(o, ensure_ascii=False) + "\n")
    (AUP / "numbering_check.json").write_text(json.dumps(check, indent=1, ensure_ascii=False))
    print(len(out), "chunks written")

if __name__ == "__main__":
    main()
