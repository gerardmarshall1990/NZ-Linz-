#!/usr/bin/env python3
"""Parse the AUP zone activity tables (Hx.4.1) into rows: id (A1..), activity, status, standards -> data/aup/activity_rows.jsonl.

Uses text-layer line positions (columns: ref, activity, status, standards) plus OCR lines that the layer lacks. Validates that row ids run
sequentially without gaps and that statuses are in {P,C,RD,D,NC,Pr}; gaps are reported (not silently dropped).
Run: python3 -I scripts/extract_activity_tables.py
"""
import json, re, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_rule_chunks import page_lines, ocr_pages, merge_ocr, ocr_replace_page, page_is_thin, FOOTER, PC_NOTE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AUP = ROOT / "data" / "aup"
STATUS = {"P", "C", "RD", "D", "NC", "Pr"}
VALID = STATUS | {"SAME", "DELETED"}
ROW = re.compile(r"^\((A\d+)\)$")

def parse_chapter(entry):
    code = re.match(r"^(H\d+)", entry["title"]).group(1)
    doc = pymupdf.open(ROOT / entry["pdf"]); ocr = ocr_pages(entry)
    pages = []
    for pn, pg in enumerate(doc, 1):
        pl = page_lines(pg)
        if pn in ocr:
            pl = ocr_replace_page(ocr[pn], pn) if page_is_thin(ocr[pn]) else sorted(pl + merge_ocr(pl, ocr[pn], pn), key=lambda r: (round(r["y"] / 3), r["x"]))
        for r in pl: r["page"] = pn
        pages.append(pl)
    # activity table section: from "Hx.4. Activity table" to "Hx.5. Notification"
    on, lines = False, []
    for pl in pages:
        for r in pl:
            t = r["text"]
            if re.match(rf"^{code}\.4\.?\s+Activity table", t): on = True; continue
            if on and re.match(rf"^{code}\.5\.?\s+Notification", t): on = False
            if on and not FOOTER.match(t) and not PC_NOTE.match(t): lines.append(r)
    rows, cur = [], None
    # column positions for this chapter: row-id column, status column (modal x of lone status tokens), standards column
    from collections import Counter
    refx = Counter(round(r["x"]) for r in lines if ROW.match(r["text"])).most_common(1)
    refx = refx[0][0] if refx else 99
    sx = Counter(round(r["x"]) for r in lines if r["text"] in STATUS and r["x"] > refx + 60).most_common(1)
    statx = sx[0][0] if sx else refx + 170
    hdr = [r["x"] for r in lines if r["text"].startswith("Standards to be complied with")]
    stdx = min(hdr) if hdr else statx + 60
    for r in lines:
        t = r["text"]
        m = ROW.match(t)
        if m and abs(r["x"] - refx) < 12:
            cur = {"id": m.group(1), "refx": r["x"], "page": r["page"], "desc": [], "status": [], "std": []}; rows.append(cur); continue
        if cur is None: continue
        if r["bold"] and r["x"] <= refx + 3 and t not in STATUS: continue  # group headings ("Use", "Residential")
        if abs(r["x"] - statx) <= 6 and t in STATUS: cur["status"].append(t)
        elif r["x"] >= stdx - 6: cur["std"].append(t)
        elif r["x"] > refx + 20: cur["desc"].append(t)
    out = []
    for c in rows:
        std = " ".join(c["std"])
        desc_txt = re.sub(r"\s+", " ", " ".join(c["desc"])).strip()
        status, note = (c["status"][0] if c["status"] else None), None
        if status is None:
            tail = desc_txt.split(" ")[-1] if desc_txt else ""
            if re.fullmatch(r"(P|C|RD|D|NC|Pr)\*?", tail): status = tail.rstrip("*"); desc_txt = desc_txt[: -len(tail)].strip()
            elif re.search(r"same activity status", desc_txt, re.I): status, note = "SAME", "activity status is the same as another activity (see text)"
            elif "[Deleted]" in desc_txt: status, note = "DELETED", "row deleted in the plan"
        elif re.search(r"\bRD\*", desc_txt): note = "status marked with * (see table notes)"
        out.append({"zone_code": code, "chapter": entry["title"], "url": entry["url"], "page": c["page"], "id": c["id"],
                    "activity": desc_txt, "status": status, "note": note,
                    "standards": sorted(set(re.findall(rf"{code}\.6\.\d+", std))), "standards_text": re.sub(r"\s+", " ", std).strip()})
    return out

def main():
    man = json.loads((AUP / "manifest.json").read_text())
    allrows, report = [], {}
    for e in man["files"]:
        if not re.match(r"^H\d+ ", e["title"]): continue
        rows = parse_chapter(e)
        if not rows: continue
        ids = [int(r["id"][1:]) for r in rows]
        gaps = sorted(set(range(1, max(ids) + 1)) - set(ids))
        bad = [r["id"] for r in rows if r["status"] not in VALID]
        report[e["title"]] = {"rows": len(rows), "max_id": max(ids), "gaps": gaps, "no_status": bad}
        allrows += rows
        print(f"{e['title'][:58]:58} rows={len(rows):3} max=A{max(ids):<3} gaps={gaps} no_status={bad}", flush=True)
    with open(AUP / "activity_rows.jsonl", "w") as f:
        for r in allrows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (AUP / "activity_check.json").write_text(json.dumps(report, indent=1))
    print(len(allrows), "activity rows")

if __name__ == "__main__":
    main()
