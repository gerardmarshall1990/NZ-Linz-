#!/usr/bin/env python3
"""Build docs/key_standards_check.html: one card per key standard for the four main residential zones, with a cropped image of the plan page
(the quoted text highlighted) beside the extracted value, for checking on a phone. Self-contained (images embedded). Nothing here marks a rule verified:
the page lets the owner tick Correct / Wrong / Unsure and copy the answers back; scripts/apply_owner_review.py records them (decision 17).
"""
import base64, html, io, json, os, re, subprocess
from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
AUP = ROOT / "data/aup"
ZONES = [("Residential - Single House Zone", "Single House (H3)"), ("Residential - Mixed Housing Suburban Zone", "Mixed Housing Suburban (H4)"),
         ("Residential - Mixed Housing Urban Zone", "Mixed Housing Urban (H5)"), ("Residential - Terrace Housing and Apartment Building Zone", "Terrace Housing and Apartments (H6)")]
KEY = [("Building height (max)", "height", "building_height_max"), ("Height in relation to boundary: angle", "height_in_relation_to_boundary", "hirb_angle"),
       ("Height in relation to boundary: start height", "height_in_relation_to_boundary", "hirb_start_height"), ("Front yard (min)", "yards", "yard_front_min"),
       ("Side yard (min)", "yards", "yard_side_min"), ("Rear yard (min)", "yards", "yard_rear_min"), ("Maximum impervious area", "stormwater", "impervious_max_pct"),
       ("Maximum building coverage", "coverage", "building_coverage_max_pct"), ("Minimum landscaped area", "landscaping", "landscaped_min_pct"),
       ("Outlook space: principal living room depth", "outlook", "outlook_living_depth_min"), ("Outdoor living space, ground floor (min area)", "outdoor_living", "ols_ground_floor_min_area"),
       ("Minimum dwelling size, 1+ bedrooms", "dwelling_size", "dwelling_min_net_floor_area_1br_plus"), ("Fence height in front yard (max)", "fences", "fence_front_yard_max"),
       ("Subdivision: min net site area, vacant site, parent under 1 ha", "subdivision", "min_net_site_area_vacant_site_parent_lt_1ha")]

def env():
    for l in (ROOT / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k, v)

def q(sql):
    e = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    out = subprocess.run(["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-At", "-F", "\x1f", "-c", sql], check=True, env=e, capture_output=True, text=True).stdout
    return [l.split("\x1f") for l in out.splitlines()]

def norm(t): return re.sub(r"\s+", " ", t.lower().replace("²", "2").replace("?", "2")).strip()

def find_rects(page, quote):
    """Rectangles on the page for the quote: try the whole quote, then its parts."""
    words = quote.split()
    for cand in (quote, " ".join(words[-6:]), " ".join(words[:6]), " ".join(words[-4:]), " ".join(words[:4])):
        r = page.search_for(cand)
        if r: return r, "text layer"
    return [], None

def ocr_rect(ocr_page, quote):
    qn = set(norm(quote).split()); best = None
    for l in ocr_page["lines"]:
        tw = set(norm(l["text"]).split())
        if tw and len(qn & tw) >= max(2, min(len(qn), len(tw)) // 2):
            best = l; break
    if best: return pymupdf.Rect(best["x"] - 4, best["y"] - 2, best["x"] + 460, best["y"] + 16)
    return None

def find_activity_page(pdf_path, par, activity, start, ocr):
    """Page of the activity table containing the row '(A3) ...': search from the section start onwards in text layer, then OCR."""
    d = pymupdf.open(pdf_path); tag = f"({par})"
    for n in range(start, min(len(d), start + 8) + 1):
        if d[n - 1].search_for(tag): return n
    for n in range(start, min(len(d), start + 8) + 1):
        if any(l["text"].strip().startswith(tag) for l in ocr.get(n, {"lines": []})["lines"]): return n
    return start

def crop(pdf_path, page_no, quote, ocr, anchor=None):
    d = pymupdf.open(pdf_path); page = d[page_no - 1]; how = None
    rects, how = ([], None)
    if anchor:
        rects = page.search_for(f"({anchor})"); how = "row id" if rects else None
        if rects: rects = [pymupdf.Rect(rects[0].x0, rects[0].y0, page.rect.width - 60, rects[0].y1 + 14)]
    if not rects: rects, how = find_rects(page, quote)
    if not rects:
        r = ocr_rect(ocr.get(page_no, {"lines": []}), quote); rects, how = ([r], "OCR position") if r else ([], None)
    pw, ph = page.rect.width, page.rect.height
    if rects:
        y0 = min(r.y0 for r in rects); y1 = max(r.y1 for r in rects)
        clip = pymupdf.Rect(40, max(60, y0 - 90), pw - 40, min(ph - 30, y1 + 90))
    else: clip = pymupdf.Rect(40, 60, pw - 40, 360)
    s = 130 / 72
    pix = page.get_pixmap(clip=clip, dpi=130); img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    for r in rects[:8]:
        b = ((r.x0 - clip.x0) * s - 3, (r.y0 - clip.y0) * s - 2, (r.x1 - clip.x0) * s + 3, (r.y1 - clip.y0) * s + 2)
        dr.rectangle(b, fill=(255, 235, 0, 90), outline=(220, 30, 30, 255), width=2)
    img = Image.alpha_composite(img, ov).convert("RGB"); buf = io.BytesIO(); img.save(buf, "JPEG", quality=68)
    return base64.b64encode(buf.getvalue()).decode(), how, len(rects)

def main():
    env()
    man = {f["url"]: f for f in json.loads((AUP / "manifest.json").read_text())["files"]}
    cards, nav = [], []
    for zone, label in ZONES:
        nav.append(f'<a href="#{label.split()[0]}{label.split()[-1]}">{html.escape(label)}</a>')
        items = []
        for lab, topic, param in KEY:
            if topic == "subdivision":
                rows = q(f"""SELECT r.id, r.value_num, r.unit, r.standard_ref, r.quote, r.extraction_method, r.ocr_confidence, r.quote_page, r.pc120_effect, r.pc120_evidence, c.source_url, r.zone FROM analytics.rules r
                             JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id WHERE r.status='operative' AND r.topic='subdivision' AND r.parameter='{param}' AND r.applies_if->>'zone_code' =
                             (SELECT code::text FROM core.zone_lookup WHERE zone_name='{zone}' OR zone_name=replace('{zone}','Buildings','Building') LIMIT 1)""")
            else:
                rows = q(f"""SELECT r.id, r.value_num, r.unit, r.standard_ref, r.quote, r.extraction_method, r.ocr_confidence, r.quote_page, r.pc120_effect, r.pc120_evidence, c.source_url, r.zone FROM analytics.rules r
                             JOIN analytics.rule_text_chunks c ON c.id = r.chunk_id WHERE r.status='operative' AND r.zone='{zone}' AND r.parameter='{param}'""")
            if not rows: items.append((lab, None)); continue
            items.append((lab, rows[0]))
        # dwelling activity rows
        act = q(f"SELECT r.parameter, r.activity, r.value_text, r.section_ref, c.page_start, c.source_url, r.id FROM analytics.rules r JOIN analytics.rule_text_chunks c ON c.id=r.chunk_id "
                f"WHERE r.status='operative' AND r.topic='activity_status' AND r.zone='{zone}' AND (r.activity ILIKE '%dwelling%per site%' OR r.activity ILIKE 'Dwellings%') ORDER BY r.id")
        cards.append(f'<h2 id="{label.split()[0]}{label.split()[-1]}">{html.escape(label)}</h2>')
        n = 0
        for par, activity, st, sec, pg, url, rid in act:
            n += 1
            f = man[url]; pdf = ROOT / f["pdf"]; ocr = {p["page"]: p for p in json.loads((AUP / "ocr" / Path(f["pdf"]).relative_to("data/aup/pdf").with_suffix(".json")).read_text())}
            pg = find_activity_page(pdf, par, activity, int(pg), ocr)
            img, how, nh = crop(pdf, pg, activity[:45], ocr, anchor=par)
            key = f"{sec}|{par}"
            cards.append(card(key, f"Dwellings: {activity[:70]}", f"<b>{html.escape(st)}</b>", sec, pg, "activity table", None, None, img, how, activity, None))
        for lab, row in items:
            n += 1
            if row is None: cards.append(f'<div class="card na"><b>{html.escape(lab)}</b><br>not a standard in this zone</div>'); continue
            rid, v, u, ref, quote, meth, conf, pg, eff, evid, url, zname = row
            f = man[url]; pdf = ROOT / f["pdf"]; ocr = {p["page"]: p for p in json.loads((AUP / "ocr" / Path(f["pdf"]).relative_to("data/aup/pdf").with_suffix(".json")).read_text())}
            img, how, nh = crop(pdf, int(pg), quote, ocr)
            val = f"{float(v):g} {u}"
            cards.append(card(f"{ref}|{lab}|{rid}", lab, f"<b>{html.escape(val)}</b>", ref, pg, meth, conf, eff, img, how, quote, evid))
    page = HEAD + "<nav>" + " ".join(nav) + "</nav>" + "\n".join(cards) + TAIL
    (ROOT / "docs/key_standards_check.html").write_text(page); print("wrote docs/key_standards_check.html", round(len(page) / 1e6, 2), "MB")

BADGE = {"text_layer+ocr": ("ok", "text layer + OCR agree"), "text_layer": ("ok", "text layer only"), "ocr_only": ("warn", "OCR only: check carefully"), "none": ("bad", "not matched cleanly: check carefully"), "activity table": ("ok", "activity table")}

def card(key, label, value_html, ref, page, meth, conf, eff, img, how, quote, evid):
    cls, txt = BADGE.get(meth or "none", ("bad", meth))
    pc = f'<span class="chip pc">PC120: {html.escape(eff)}</span>' if eff else ""
    cf = f" (OCR confidence {float(conf):.0f})" if conf not in (None, "") else ""
    return f'''<div class="card" data-key="{html.escape(key)}"><div class="top"><div><div class="lab">{html.escape(label)}</div><div class="val">{value_html}</div></div>
<div class="meta">{html.escape(ref)} · page {page}<br><span class="chip {cls}">{html.escape(txt)}{cf}</span> {pc}</div></div>
<img loading="lazy" alt="plan page crop" src="data:image/jpeg;base64,{img}">
<div class="q">Quoted text: “{html.escape(quote or "")}”</div>
<div class="btns"><button data-a="correct">✓ Correct</button><button data-a="wrong">✗ Wrong</button><button data-a="unsure">? Unsure</button></div></div>'''

HEAD = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Key standards check</title>
<style>*{box-sizing:border-box}:root{--bg:#fff;--fg:#14202b;--mut:#5b6b7a;--card:#f4f7fa;--bd:#d5dde5;--ok:#1b7f3b;--warn:#b45309;--bad:#b91c1c}
@media(prefers-color-scheme:dark){:root{--bg:#0f1720;--fg:#e8eef4;--mut:#9fb0c0;--card:#17222d;--bd:#2a3a49;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171}}
html,body{overflow-x:hidden}body{margin:0;padding:0 16px 90px;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;max-width:760px;margin:auto}
h1{font-size:1.35rem;margin:18px 0 4px}h2{font-size:1.15rem;margin:28px 0 8px;scroll-margin-top:60px}nav{position:sticky;top:0;background:var(--bg);padding:8px 0;display:flex;gap:10px;flex-wrap:wrap;border-bottom:1px solid var(--bd);z-index:5}
nav a{font-size:.85rem;color:var(--fg)}.intro{color:var(--mut);font-size:.92rem}.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:12px;margin:12px 0}
.card.na{color:var(--mut)}.top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.top>div{min-width:0}.lab{font-size:.9rem;color:var(--mut)}.val{font-size:1.5rem}.meta{font-size:.8rem;color:var(--mut);text-align:left;max-width:100%}
.chip{display:inline-block;white-space:normal;max-width:100%;padding:1px 8px;border-radius:10px;border:1px solid var(--bd);font-size:.75rem;margin-top:3px}.chip.ok{color:var(--ok);border-color:var(--ok)}.chip.warn{color:var(--warn);border-color:var(--warn)}.chip.bad{color:var(--bad);border-color:var(--bad)}.chip.pc{color:var(--mut)}
img{width:100%;border-radius:8px;margin:8px 0;border:1px solid var(--bd)}.q{font-size:.85rem;color:var(--mut)}.btns{display:flex;gap:8px;margin-top:8px}
button{flex:1;padding:12px 6px;border-radius:10px;border:1px solid var(--bd);background:var(--bg);color:var(--fg);font-size:1rem}button.sel[data-a=correct]{background:var(--ok);color:#fff}button.sel[data-a=wrong]{background:var(--bad);color:#fff}button.sel[data-a=unsure]{background:var(--warn);color:#fff}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--bg);border-top:1px solid var(--bd);padding:10px 16px;display:flex;gap:10px;align-items:center;justify-content:space-between}.bar button{flex:none;padding:10px 14px;background:var(--fg);color:var(--bg)}</style></head><body>
<h1>Key standards check</h1>
<p class="intro">For each standard: the value the tool extracted, and a crop of the Council plan page with the matching text highlighted in yellow/red. Tick <b>Correct</b>, <b>Wrong</b> or <b>Unsure</b>. Orange “OCR only” and red “not matched” badges need the closest look. Plan: Auckland Unitary Plan operative July 2026. PC120 is proposed and not in force; its effect on each value is shown as a grey chip. At the bottom, tap <b>Copy answers</b> and paste them into the chat. Nothing is marked verified until you send them.</p>'''
TAIL = '''<div class="bar"><span id="cnt">0 answered</span><span><button id="copy">Copy answers</button></span></div>
<script>
const KEY="ksc_answers_v1";let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
function paint(){document.querySelectorAll(".card[data-key]").forEach(c=>{const k=c.dataset.key;c.querySelectorAll("button").forEach(b=>b.classList.toggle("sel",st[k]===b.dataset.a))});document.getElementById("cnt").textContent=Object.keys(st).length+" answered"}
document.addEventListener("click",e=>{const b=e.target.closest(".card button");if(!b)return;const k=b.closest(".card").dataset.key;st[k]=b.dataset.a;try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}paint()});
document.getElementById("copy").onclick=async()=>{const t=Object.entries(st).map(([k,v])=>k+" => "+v).join("\\n");try{await navigator.clipboard.writeText(t);alert("Copied "+Object.keys(st).length+" answers")}catch(e){prompt("Copy these answers:",t)}};paint();
</script></body></html>'''

if __name__ == "__main__":
    main()
