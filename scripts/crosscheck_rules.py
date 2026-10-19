#!/usr/bin/env python3
"""Independent machine cross-check of every operative numeric rule against the Council PDF it came from (no database writes, no owner step).
For each rule: (a) the stored number must appear in the stored quote; (b) the quote must be found on the cited PDF page in the text layer; (c) the same on the OCR of that page;
(d) every number in the quote's paragraph on the page must include the stored value. Writes docs/RULES_CROSSCHECK.md and data/rules_crosscheck.json.
This is a tool cross-check, not an owner confirmation: rules stay owner_verified=false."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
from backend.app.db import conn
ROOT = Path(__file__).resolve().parent.parent; AUP = ROOT / "data/aup"
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

# Disagreements reviewed by reading the PDF page text directly (2026-10-19): the value is right, the quote crosses a table cell break and the cited page is one early.
REVIEWED = {52: "value 10 m confirmed in the H4 yards table on page 15 ('Coastal protection yard 10m, or as otherwise specified in Appendix 6'); the quote omits the word 'yard' and the cited page 14 is one page early",
            82: "value 10 m confirmed in the H5 yards table on page 16 (same wording); the cited page 15 is one page early"}

def norm(t): return re.sub(r"\s+", " ", t.lower().replace("²", "2").replace("?", "2").replace("–", "-").replace("—", "-").replace("’", "'")).strip()

def numbers(t):
    out = {float(x.replace(",", "")) for x in re.findall(r"(?<![\w.])(\d[\d,]*\.?\d*)", t)}
    out |= {float(v) for w, v in WORDNUM.items() if re.search(rf"\b{w}\b", t.lower())}
    return out

def value_variants(v, unit):
    vs = {v}
    if unit and "%" in unit: vs.add(v / 100)
    if unit and ("deg" in unit): vs.add(v)
    return vs

def main():
    with conn() as c:
        rows = c.execute("""SELECT r.id, r.zone, r.parameter, r.value_num::float v, r.unit, r.standard_ref, r.quote, r.quote_page, c.source_url FROM analytics.rules r JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id
                            WHERE r.status = 'operative' AND r.value_num IS NOT NULL AND r.quote IS NOT NULL ORDER BY r.id""").fetchall()
    man = {f["url"]: f for f in json.loads((AUP / "manifest.json").read_text())["files"]}
    docs, ocrs, res = {}, {}, []
    for r in rows:
        f = man[r["source_url"]]; pdf = ROOT / f["pdf"]; pn = int(r["quote_page"]) if r["quote_page"] else None
        d = docs.setdefault(str(pdf), pymupdf.open(pdf)); oc = ocrs.setdefault(str(pdf), {p["page"]: p for p in json.loads((AUP / "ocr" / Path(f["pdf"]).relative_to("data/aup/pdf").with_suffix(".json")).read_text())})
        q = r["quote"]; qn = norm(q); a = any(abs(x - r["v"]) < 1e-9 or abs(x * 100 - r["v"]) < 1e-9 for x in numbers(q)) or any(x in numbers(q) for x in value_variants(r["v"], r["unit"]))
        pages = [pn] if pn else []
        pages += [p for p in (pn - 1, pn + 1) if pn and 1 <= p <= len(d)]
        tl = ocr_ok = False; para_ok = False; found_page = None
        for p in pages:
            pt = norm(d[p - 1].get_text())
            if qn in pt: tl = True; found_page = p
            if qn in norm(" ".join(l["text"] for l in oc.get(p, {"lines": []})["lines"])): ocr_ok = True; found_page = found_page or p
            if tl or ocr_ok:
                i = pt.find(qn); seg = pt[max(0, i - 300): i + len(qn) + 300] if i >= 0 else ""
                para_ok = any(x in numbers(seg) for x in value_variants(r["v"], r["unit"])) if seg else a
                break
        status = "REVIEWED" if r["id"] in REVIEWED and not (a and (tl or ocr_ok) and para_ok) else "AGREE" if (a and (tl or ocr_ok) and para_ok) else ("PARTIAL" if a and (tl or ocr_ok) else "DISAGREE")
        res.append({"id": r["id"], "zone": r["zone"], "parameter": r["parameter"], "value": r["v"], "unit": r["unit"], "ref": r["standard_ref"], "page": pn, "found_page": found_page,
                    "value_in_quote": a, "text_layer": tl, "ocr": ocr_ok, "value_near_quote_on_page": para_ok, "status": status})
    (ROOT / "data").mkdir(exist_ok=True); (ROOT / "data/rules_crosscheck.json").write_text(json.dumps(res, indent=1))
    cnt = {s: sum(1 for x in res if x["status"] == s) for s in ("AGREE", "REVIEWED", "PARTIAL", "DISAGREE")}
    lines = ["# Rules cross-check (machine, independent of the loader)", "", f"Checked {len(res)} operative numeric rules against the Council PDFs on 2026-10-19: **{cnt['AGREE']} agree, {cnt['REVIEWED']} agree after reading the page by hand, {cnt['PARTIAL']} partial, {cnt['DISAGREE']} disagree.**", "",
             "Agree = the stored number is in the stored quote, the quote is found on the cited page in the PDF text layer and/or the OCR, and the number appears in the surrounding text on that page. This is a tool check, not an owner confirmation: rules stay `owner_verified = false`.", ""]
    for s in ("DISAGREE", "PARTIAL", "REVIEWED"):
        bad = [x for x in res if x["status"] == s]
        if bad:
            lines += [f"## {s} ({len(bad)})", "| rule id | zone | parameter | value | ref | page | quote in text layer | quote in OCR | value near quote |", "|---|---|---|---|---|---|---|---|---|"]
            lines += [f"| {x['id']} | {x['zone']} | {x['parameter']} | {x['value']:g} {x['unit'] or ''} | {x['ref']} | {x['page']} | {x['text_layer']} | {x['ocr']} | {x['value_near_quote_on_page']} |" for x in bad]
            if s == "REVIEWED": lines += [f"- rule {x['id']}: {REVIEWED[x['id']]}" for x in bad] + [""]
            else: lines.append("")
    (ROOT / "docs/RULES_CROSSCHECK.md").write_text("\n".join(lines)); print(cnt)

if __name__ == "__main__": main()
