#!/usr/bin/env python3
"""Write one page image + caption per key standard (Single House zone, first 10 numeric standards) for sending to the owner one at a time.
Usage: python3 scripts/make_spotcheck_images.py <out_dir>   (needs the AUP files in data/aup and the database)"""
import base64, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_key_standards_check as b

def main(out):
    b.env(); out = Path(out); out.mkdir(parents=True, exist_ok=True)
    man = {f["url"]: f for f in json.loads((b.AUP / "manifest.json").read_text())["files"]}
    zone = b.ZONES[0][0]; n = 0; items = []
    for lab, topic, param in b.KEY:
        if topic == "subdivision": continue
        rows = b.q(f"""SELECT r.id, r.value_num, r.unit, r.standard_ref, r.quote, r.extraction_method, r.ocr_confidence, r.quote_page, c.source_url FROM analytics.rules r
                       JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id WHERE r.status='operative' AND r.zone='{zone}' AND r.parameter='{param}'""")
        if not rows: continue
        rid, v, u, ref, quote, meth, conf, pg, url = rows[0]
        f = man[url]; pdf = b.ROOT / f["pdf"]
        ocr = {p["page"]: p for p in json.loads((b.AUP / "ocr" / Path(f["pdf"]).relative_to("data/aup/pdf").with_suffix(".json")).read_text())}
        img, how, nh = b.crop(pdf, int(pg), quote, ocr)
        n += 1; (out / f"check_{n:02d}.jpg").write_bytes(base64.b64decode(img))
        items.append({"n": n, "label": lab, "value": f"{float(v):g} {u}", "ref": ref, "page": pg, "rule_id": rid, "how": how, "file": f"check_{n:02d}.jpg"})
        if n == 10: break
    (out / "checks.json").write_text(json.dumps(items, indent=1)); print(json.dumps(items, indent=1))

if __name__ == "__main__": main(sys.argv[1])
