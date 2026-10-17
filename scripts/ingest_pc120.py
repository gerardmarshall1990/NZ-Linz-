#!/usr/bin/env python3
"""Download Council's Plan Change 120 documents used for `proposed` rules and record status (idempotent).

Source pages (read 2026-10-17):
  https://www.aucklandcouncil.govt.nz/en/plans-policies-bylaws-reports-projects/our-plans-strategies/unitary-plan/auckland-unitary-plan-modifications/proposed-plan-changes/pc-120-housing-intensification-resilience.html
Status per Council: notified 3 Nov 2025; submissions closed 19 Dec 2025; partially withdrawn and proposed amendments notified 27 Aug 2026; second submission period closed 24 Sep 2026 5pm; hearings to follow.
Writes data/pc120/pdf/*.pdf, data/pc120/txt/*.txt (info sheets, pdftotext -layout) and data/pc120/manifest.json (url, sha256, bytes).
"""
import hashlib, json, subprocess, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.aucklandcouncil.govt.nz/content/dam/ac/docs/plans/unitary/pc-120/"
FILES = {  # file -> (role, stage)
    "55-pc120-chapter-h-residential.pdf": ("plan_text", "notified 2025-11-03"),
    "05-chapter-h-Residential-Mixed-Housing-Urban-Zone.pdf": ("plan_text", "proposed amendments 2026-08"),
    "06-chapter-h-residential-terrace-housing-and-apartment-buildings-zone.pdf": ("plan_text", "proposed amendments 2026-08"),
    "10-info-Sheet-09-updates-to-terrace-housing-and-apartment-buildings-zone-aug-2026.pdf": ("info_sheet_09_THAB", "2026-08"),
    "11-info-sheet-10-updates-to-mixed-housing-urban-zone-aug-2026.pdf": ("info_sheet_10_MHU", "2026-08"),
    "12-info-sheet-11-updates-to-mixed-housing-suburbanz-zone-aug-2026.pdf": ("info_sheet_11_MHS", "2026-08"),
    "13-info-sheet-12-update-%20to-single-house-zone-aug-2026.pdf": ("info_sheet_12_SHZ", "2026-08"),
    "27-info-sheet-26-what-is-partial-withdrawal-aug-2026.pdf": ("info_sheet_26", "2026-08"),
    "00-explanatory-note-aug-2026.pdf": ("explanatory_note", "2026-08"),
    "53-pc120-chapter-e-subdivision.pdf": ("plan_text", "notified 2025-11-03"),
    "52-pc120-chapter-e-natural-hazards-and-flooding.pdf": ("plan_text", "notified 2025-11-03"),
}

def main():
    pdf = ROOT / "data/pc120/pdf"; txt = ROOT / "data/pc120/txt"; pdf.mkdir(parents=True, exist_ok=True); txt.mkdir(parents=True, exist_ok=True)
    man = {"source_page": "pc-120-housing-intensification-resilience.html", "status_read": "2026-10-17", "files": []}
    for f, (role, stage) in FILES.items():
        local = pdf / f.replace("%20", "_")
        if not local.exists():
            req = urllib.request.Request(BASE + f, headers={"User-Agent": "Mozilla/5.0 nz-property-research/0.1"})
            local.write_bytes(urllib.request.urlopen(req, timeout=300).read())
        t = txt / (local.stem + ".txt")
        if not t.exists(): subprocess.run(["pdftotext", "-layout", str(local), str(t)], check=True)
        man["files"].append({"file": local.name, "url": BASE + f, "role": role, "stage": stage, "sha256": hashlib.sha256(local.read_bytes()).hexdigest(), "bytes": local.stat().st_size})
    (ROOT / "data/pc120/manifest.json").write_text(json.dumps(man, indent=1)); print(len(man["files"]), "PC120 documents")

if __name__ == "__main__":
    main()
