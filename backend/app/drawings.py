"""Demolition / new-work drawings of a layout option as DXF and PDF, stamped DRAFT. Needs a scaled level (no scale, no drawing).
Colour code: grey = existing and unchanged, orange = existing room changes use (demolition/strip-out of the old use), blue = new work item. Room level only: wall changes are the designer's."""
import io
import ezdxf
from shapely.geometry import Polygon
from fastapi import HTTPException
from .layout import get_option
from .model_view import confirmed_levels
from .stamp import STAMP

def _geom(oid: int, level_idx: int):
    opt = get_option(oid)
    if not 0 <= level_idx < len(opt["levels"]): raise HTTPException(404, "no such level in this option")
    lv = opt["levels"][level_idx]
    src = {l["extraction_id"]: l for l in confirmed_levels(opt["parcel_id"])}.get(lv["extraction_id"])
    if not src or not src["calibrated"]: raise HTTPException(422, f"level '{lv['level_name']}' has no scale: no drawing can be produced (calibrate the plan first)")
    polys = {r["id"]: r["polygon_m"] for r in src["rooms"]}
    return opt, lv, polys

def _kind(a): return "new" if (a["items"] and a["action"] == "keep") else ("change" if a["action"] == "convert" else "existing")

def _tb_lines(tb: dict) -> list[str]:
    return [f"Address: {tb['address']}  |  Legal description: {tb['legal']}", f"Drawing {tb['number']}: {tb['title']}  |  Designer: {tb['designer']}  |  Owner: {tb['owner']}  |  Dated: {tb['date']}"]

def dxf(oid: int, level_idx: int = 0, titleblock: dict | None = None) -> bytes:
    opt, lv, polys = _geom(oid, level_idx)
    d = ezdxf.new("R2010"); d.header["$INSUNITS"] = 6
    for name, col in (("EXISTING", 8), ("CHANGE_OF_USE_DEMOLITION", 30), ("NEW_WORK", 5), ("TEXT", 7), ("STAMP", 1)): d.layers.add(name, color=col)
    m = d.modelspace(); xs = [p[0] for pl in polys.values() for p in pl]; ys = [p[1] for pl in polys.values() for p in pl]
    for a in lv["rooms"]:
        pl = polys.get(a["room_id"]);
        if not pl: continue
        k = _kind(a); layer = {"existing": "EXISTING", "change": "CHANGE_OF_USE_DEMOLITION", "new": "NEW_WORK"}[k]
        m.add_lwpolyline(pl, close=True, dxfattribs={"layer": "EXISTING" if k != "change" else layer})
        if k == "change": m.add_lwpolyline(pl, close=True, dxfattribs={"layer": layer})
        c = Polygon(pl).representative_point(); txt = (a["label"] or a["type"]) + (f" -> {a['becomes']}" if a["action"] == "convert" else "")
        m.add_text(txt, dxfattribs={"layer": "TEXT", "height": 0.18, "insert": (c.x - 0.8, c.y)})
        if a["items"]:
            m.add_circle((c.x, c.y - 0.35), 0.12, dxfattribs={"layer": "NEW_WORK"})
            m.add_text("; ".join(a["items"])[:90], dxfattribs={"layer": "NEW_WORK", "height": 0.12, "insert": (c.x - 0.8, c.y - 0.6)})
    y0 = min(ys) - 1.5
    m.add_text(STAMP, dxfattribs={"layer": "STAMP", "height": 0.3, "insert": (min(xs), y0)})
    m.add_text(f"Layout option: {opt['scenario']} | level: {lv['level_name']} | beds in option: {opt['beds']} | screening drawing, room level only", dxfattribs={"layer": "TEXT", "height": 0.2, "insert": (min(xs), y0 - 0.5)})
    for j, ln in enumerate(_tb_lines(titleblock) if titleblock else []): m.add_text(ln, dxfattribs={"layer": "TEXT", "height": 0.18, "insert": (min(xs), y0 - 1.0 - j * 0.35)})
    s = io.StringIO(); d.write(s); return s.getvalue().encode()

def pdf(oid: int, level_idx: int = 0, titleblock: dict | None = None) -> bytes:
    import pymupdf
    opt, lv, polys = _geom(oid, level_idx)
    W, H = 1190, 842   # A3 landscape in points
    doc = pymupdf.open(); pg = doc.new_page(width=W, height=H)
    xs = [p[0] for pl in polys.values() for p in pl]; ys = [p[1] for pl in polys.values() for p in pl]
    margin, top, bottom = 50, 70, 90
    k = min((W - 2 * margin) / (max(xs) - min(xs) or 1), (H - top - bottom) / (max(ys) - min(ys) or 1))      # points per metre
    tx = lambda x, y: (margin + (x - min(xs)) * k, H - bottom - (y - min(ys)) * k)
    col = {"existing": (0.55, 0.55, 0.55), "change": (0.95, 0.5, 0.1), "new": (0.1, 0.3, 0.85)}
    for a in lv["rooms"]:
        pl = polys.get(a["room_id"])
        if not pl: continue
        kind = _kind(a); pts = [tx(*p) for p in pl]
        sh = pg.new_shape(); sh.draw_polyline(pts + [pts[0]]); sh.finish(color=col[kind], fill=(1, 0.93, 0.85) if kind == "change" else None, width=1.2); sh.commit()
        c = tx(*Polygon(pl).representative_point().coords[0]); txt = (a["label"] or a["type"]) + (f" > {a['becomes']}" if a["action"] == "convert" else "")
        pg.insert_text((c[0] - 30, c[1]), txt[:40], fontsize=7, color=(0, 0, 0))
        if a["items"]: pg.insert_text((c[0] - 30, c[1] + 10), "NEW: " + "; ".join(a["items"])[:48], fontsize=5.5, color=col["new"])
    pg.insert_text((margin, 30), STAMP, fontsize=14, color=(0.8, 0, 0))
    pg.insert_text((margin, 50), f"Option: {opt['scenario']} | Level: {lv['level_name']} | Beds in option: {opt['beds']} | Scaled to fit A3: not a stated drawing scale", fontsize=8)
    pg.insert_text((margin, H - 55), "Legend: grey = existing, unchanged | orange = change of use / strip-out | blue = new work. Room level only; wall changes, structure, fire and services are for the designer and engineers.", fontsize=7)
    pg.insert_text((margin, H - 40), STAMP + ". Screening drawing from a human-confirmed plan reading.", fontsize=7, color=(0.8, 0, 0))
    for j, ln in enumerate(_tb_lines(titleblock) if titleblock else []): pg.insert_text((margin, H - 26 + j * 11), ln, fontsize=7)
    return doc.tobytes()
