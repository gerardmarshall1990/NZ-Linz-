#!/usr/bin/env python3
"""Read Council plan-change PDFs where tracked changes are drawn as thin black rectangles (strike-through = deletion, underline = insertion).

page_text(page) -> list of lines, each line a list of (text, state) runs, state in {'keep','ins','del'}.
proposed(line) = keep+ins text; operative(line) = keep+del text. Text colour is black for all, so geometry is the only signal.
"""
import re
import pymupdf

def thin_rects(page):
    out = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if dr.get("fill") == (0.0, 0.0, 0.0) and r.height < 1.6 and r.width > 2:
            out.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
    return out

def classify_char(c, rects):
    x0, y0, x1, y1 = c["bbox"]; h = y1 - y0; cx = (x0 + x1) / 2
    st = "keep"
    for rx0, rx1, ry in rects:
        if rx0 - 0.5 <= cx <= rx1 + 0.5:
            if y0 + 0.38 * h <= ry <= y0 + 0.68 * h: return "del"
            if y1 - 0.12 * h <= ry <= y1 + 0.28 * h: st = "ins"
    return st

def page_lines(page):
    rects = thin_rects(page)
    # drop long rules (table borders / header rules): keep only short runs likely to be text-decoration
    rects = [r for r in rects if (r[1] - r[0]) < 330]
    lines = []
    raw = page.get_text("rawdict")
    for b in raw["blocks"]:
        for l in b.get("lines", []):
            runs = []
            for s in l["spans"]:
                for c in s["chars"]:
                    ch = c["c"]
                    if ch == " ": st = runs[-1][1] if runs else "keep"
                    else: st = classify_char(c, rects)
                    if runs and runs[-1][1] == st: runs[-1][0] += ch
                    else: runs.append([ch, st])
            if runs: lines.append({"x": l["bbox"][0], "y": l["bbox"][1], "runs": runs})
    return lines

def proposed(line): return "".join(t for t, s in line["runs"] if s != "del")
def operative(line): return "".join(t for t, s in line["runs"] if s != "ins")
