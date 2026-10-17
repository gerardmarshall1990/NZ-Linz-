#!/usr/bin/env python3
"""Download the operative Auckland Unitary Plan chapter PDFs (official, from unitaryplan.aucklandcouncil.govt.nz) and extract text.

Index: https://unitaryplan.aucklandcouncil.govt.nz/data/operative/data.xml (machine-readable list of PDFs, with date.txt).
Output: data/aup/pdf/<chapter>/<file>.pdf and data/aup/txt/<same>.txt (pdftotext -layout). Records sha256 in data/aup/manifest.json.
Chapters fetched: C General rules, D Overlays, E Auckland-wide, H Zones, J Definitions (precincts, schedules, designations are not fetched).
Idempotent: files are re-downloaded only if missing; pass --force to refresh. PDFs are untrusted input: only passed to pdftotext.
"""
import hashlib, json, subprocess, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://unitaryplan.aucklandcouncil.govt.nz/"
WANT = ("Chapter C General rules", "Chapter D Overlays", "Chapter E Auckland-wide", "Chapter H Zones", "Chapter J Definitions")
UA = {"User-Agent": "Mozilla/5.0 nz-property-research/0.1"}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()

def main(force=False):
    out = ROOT / "data" / "aup"; (out / "pdf").mkdir(parents=True, exist_ok=True); (out / "txt").mkdir(exist_ok=True)
    date = get(BASE + "data/operative/date.txt").decode().strip()
    root = ET.fromstring(get(BASE + "data/operative/data.xml"))
    manifest = {"index_date": date, "source": BASE + "data/operative/data.xml", "files": []}
    for cat in root.findall("category"):
        if cat.get("title") not in WANT: continue
        items = [(None, i) for i in cat.findall("item")] + [(s.get("title"), i) for s in cat.findall("subcategory") for i in s.findall("item")]
        for sub, it in items:
            rel, title = (it.findtext("pdf") or "").strip(), (it.findtext("title") or "").strip()
            if not rel.lower().endswith(".pdf"): continue
            p = out / "pdf" / Path(rel).relative_to("images/Auckland Unitary Plan Operative")
            t = out / "txt" / p.relative_to(out / "pdf").with_suffix(".txt")
            p.parent.mkdir(parents=True, exist_ok=True); t.parent.mkdir(parents=True, exist_ok=True)
            url = BASE + urllib.parse.quote(rel)
            if force or not p.exists():
                p.write_bytes(get(url))
            if force or not t.exists():
                subprocess.run(["pdftotext", "-layout", str(p), str(t)], check=True)
            manifest["files"].append({"chapter": cat.get("title"), "subcategory": sub, "title": title, "url": url,
                                      "pdf": str(p.relative_to(ROOT)), "txt": str(t.relative_to(ROOT)),
                                      "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size})
            print(f"{cat.get('title')[:22]:22} {title[:70]}", flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(len(manifest["files"]), "files; plan index date", date)

if __name__ == "__main__":
    main("--force" in sys.argv)
