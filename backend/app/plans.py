"""Plan extraction lifecycle: upload -> extract (DXF | vision | manual) -> calibrate -> human edits -> CONFIRM -> Property Record facts at CONFIRMED."""
import io, json, math
from fastapi import HTTPException
from shapely.geometry import Polygon
from .config import upload_dir
from .db import conn
from .dxf_reader import parse_dxf, classify
from .facts import set_fact
from . import vision_reader
from .calibration import PDF_PREVIEW_DPI

TYPES = ["bedroom", "ensuite", "bathroom", "lounge", "dining", "kitchen", "laundry", "office", "store", "corridor", "stairs", "lift", "other", "unknown"]
EVIDENCE = ["PLANS_ON_FILE", "REMOTE_SCAN", "SCAN_VISIT", "ENGINEER_VISIT"]

def _upload(c, upload_id):
    u = c.execute("SELECT * FROM core.rh_upload WHERE id = %s", (upload_id,)).fetchone()
    if not u: raise HTTPException(404, "no such upload")
    return u

def file_bytes(u) -> bytes:
    p = upload_dir() / str(u["parcel_id"]) / u["stored_name"]
    if not p.resolve().is_relative_to(upload_dir().resolve()) or not p.exists(): raise HTTPException(404, "stored file missing")
    return p.read_bytes()

def preview_png(upload_id: int, page: int = 1) -> tuple[bytes, int, int]:
    with conn() as c: u = _upload(c, upload_id)
    data = file_bytes(u)
    if u["detected_type"] == "pdf":
        import pymupdf
        d = pymupdf.open(stream=data, filetype="pdf")
        if not 1 <= page <= len(d): raise HTTPException(404, "no such page")
        pix = d[page - 1].get_pixmap(dpi=PDF_PREVIEW_DPI); return pix.tobytes("png"), pix.width, pix.height
    if u["detected_type"] in ("png", "jpg"):
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB"); im.thumbnail((3000, 3000)); b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue(), im.width, im.height
    raise HTTPException(422, "no image preview for this file type (DXF is drawn from the extracted model)")

def latest_calibration(c, upload_id, page):
    return c.execute("SELECT * FROM core.rh_plan_calibration WHERE upload_id = %s AND page = %s ORDER BY id DESC LIMIT 1", (upload_id, page)).fetchone()

def _area_px(poly, mpp): return round(Polygon(poly).area * mpp * mpp, 3) if len(poly) >= 3 else None

def recompute(model: dict, cal) -> dict:
    """Apply calibration to a px-space model: areas and door widths exist only when calibrated."""
    if model.get("coord_space") == "preview_px":
        mpp = float(cal["metres_per_unit"]) if cal else None
        model["calibrated"] = mpp is not None; model["unscaled"] = mpp is None
        model["units"] = {"drawing_unit": "preview_px", "metres_per_unit": mpp} if mpp else None
        for r in model["rooms"]: r["area_m2"] = _area_px(r["polygon"], mpp) if mpp else None
        corr = []
        if mpp:
            for r in model["rooms"]:
                if r["type"] == "corridor" and len(r["polygon"]) >= 3:
                    xs = list(Polygon(r["polygon"]).minimum_rotated_rectangle.exterior.coords); e = sorted(math.dist(xs[i], xs[i + 1]) for i in range(4))
                    corr.append({"room_id": r["id"], "min_width_m": round(e[0] * mpp, 3), "method": "short side of minimum rotated rectangle (approximate)"})
        model["corridors"] = corr
        for d in model.get("doors", []):
            if d.get("width_px"): d["width_m"] = round(d["width_px"] * mpp, 3) if mpp else None
    return model

def extract(upload_id: int, mode: str, page: int = 1, units_override: str | None = None, by: str = "owner") -> dict:
    with conn() as c:
        u = _upload(c, upload_id); t = u["detected_type"]; cal_id = None
        if t == "dxf":
            try: model = parse_dxf(file_bytes(u).decode("utf-8", errors="replace").encode(), units_override)
            except ValueError as e: raise HTTPException(422, str(e))
            if model["units"]:
                cal = c.execute("""INSERT INTO core.rh_plan_calibration (upload_id, page, method, metres_per_unit, unit, detail, created_by) VALUES (%s,1,'dxf_units',%s,%s,%s::jsonb,%s) RETURNING id""",
                                (upload_id, model["units"]["metres_per_unit"], model["units"]["drawing_unit"], json.dumps({"override": bool(units_override)}), by)).fetchone(); cal_id = cal["id"]
            source = "dxf"
        elif t in ("pdf", "png", "jpg"):
            png, w, h = preview_png(upload_id, page)
            if mode == "vision":
                try: model = vision_reader.extract(png)
                except vision_reader.Blocked as e: raise HTTPException(503, str(e))
                except Exception as e: raise HTTPException(502, f"vision extraction failed: {e}")
                source = "vision"
            else:
                model = {"schema": 1, "source": "manual", "level_name": None, "coord_space": "preview_px", "rooms": [], "doors": [], "stairs": [], "lifts": [], "exits": [], "corridors": [], "dimensions": [],
                         "warnings": ["Manual tracing: draw each room on the plan, set its type, then confirm."]}
                source = "manual"
            model["preview"] = {"width": w, "height": h, "dpi": PDF_PREVIEW_DPI if t == "pdf" else None}
            cal = latest_calibration(c, upload_id, page)
            if cal: cal_id = cal["id"]
            model = recompute(model, cal)
        elif t == "ifc": raise HTTPException(422, "IFC parsing is not implemented yet (DXF is supported; export a DXF or use PDF/manual tracing)")
        else: raise HTTPException(422, f"nothing to read in a {t} file (stored as reference)")
        row = c.execute("""INSERT INTO core.rh_plan_extraction (upload_id, page, source, calibrated, calibration_id, model, created_by) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id""",
                        (upload_id, page, source, bool(model.get("calibrated")), cal_id, json.dumps(model), by)).fetchone()
        c.commit()
    return get_extraction(row["id"])

def get_extraction(eid: int) -> dict:
    with conn() as c:
        e = c.execute("SELECT * FROM core.rh_plan_extraction WHERE id = %s", (eid,)).fetchone()
        if not e: raise HTTPException(404, "no such extraction")
        return {**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in e.items()}, "types": TYPES}

def calibrate(upload_id: int, page: int, cal: dict, by: str = "owner") -> dict:
    with conn() as c:
        _upload(c, upload_id)
        row = c.execute("""INSERT INTO core.rh_plan_calibration (upload_id, page, method, metres_per_unit, unit, residual_m, detail, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                        (upload_id, page, cal["method"], cal["metres_per_unit"], cal["unit"], cal.get("residual_m"), json.dumps(cal.get("detail") or {}), by)).fetchone()
        # re-apply to the unconfirmed extractions for this page
        for e in c.execute("SELECT id, model FROM core.rh_plan_extraction WHERE upload_id = %s AND page = %s AND status = 'extracted' AND source <> 'dxf'", (upload_id, page)).fetchall():
            m = recompute(e["model"], row)
            c.execute("UPDATE core.rh_plan_extraction SET model = %s::jsonb, calibrated = true, calibration_id = %s WHERE id = %s", (json.dumps(m), row["id"], e["id"]))
        c.commit()
    return {"id": row["id"], "method": row["method"], "metres_per_unit": float(row["metres_per_unit"]), "residual_m": float(row["residual_m"]) if row["residual_m"] is not None else None}

def edit(eid: int, ops: list[dict], by: str = "owner") -> dict:
    with conn() as c:
        e = c.execute("SELECT * FROM core.rh_plan_extraction WHERE id = %s", (eid,)).fetchone()
        if not e: raise HTTPException(404, "no such extraction")
        if e["status"] == "human_confirmed": raise HTTPException(409, "confirmed extractions are read-only: re-open to edit (creates a new version)")
        m = e["model"]; rooms = {r["id"]: r for r in m["rooms"]}
        for op in ops:
            o = op.get("op")
            if o == "set_room":
                r = rooms.get(op["id"]);
                if not r: raise HTTPException(404, f"no room {op['id']}")
                if "label" in op: r["label"] = op["label"]; r["type"] = op.get("type") or classify(op["label"] or "")
                if "type" in op:
                    if op["type"] not in TYPES: raise HTTPException(422, f"type must be one of {TYPES}")
                    r["type"] = op["type"]
                if "polygon" in op: r["polygon"] = op["polygon"]
                r["confidence"] = "human_confirmed"
            elif o == "add_room":
                if len(op.get("polygon", [])) < 3: raise HTTPException(422, "a room needs at least 3 points")
                n = max([int(k[1:]) for k in rooms if k[1:].isdigit()] + [0]) + 1
                r = {"id": f"r{n}", "label": op.get("label"), "type": op.get("type") or classify(op.get("label") or ""), "polygon": op["polygon"], "area_m2": None, "confidence": "human_confirmed"}
                m["rooms"].append(r); rooms[r["id"]] = r
            elif o == "delete_room": m["rooms"] = [r for r in m["rooms"] if r["id"] != op["id"]]; rooms.pop(op["id"], None)
            elif o == "set_level_name": m["level_name"] = op.get("level_name")
            elif o == "set_door_width":
                d = next((d for d in m["doors"] if d["id"] == op["id"]), None)
                if not d: raise HTTPException(404, "no such door")
                d["width_m"] = float(op["width_m"]) if m.get("calibrated") else None; d["confidence"] = "human_confirmed"
            else: raise HTTPException(422, f"unknown op {o!r}")
            c.execute("INSERT INTO core.rh_plan_edit (extraction_id, edit, edited_by) VALUES (%s,%s::jsonb,%s)", (eid, json.dumps(op), by))
        if m.get("coord_space") == "preview_px":
            cal = c.execute("SELECT * FROM core.rh_plan_calibration WHERE id = %s", (e["calibration_id"],)).fetchone() if e["calibration_id"] else None
            m = recompute(m, cal)
        c.execute("UPDATE core.rh_plan_extraction SET model = %s::jsonb WHERE id = %s", (json.dumps(m), eid)); c.commit()
    return get_extraction(eid)

def reopen(eid: int, by: str = "owner") -> dict:
    with conn() as c:
        e = c.execute("SELECT * FROM core.rh_plan_extraction WHERE id = %s", (eid,)).fetchone()
        if not e or e["status"] != "human_confirmed": raise HTTPException(409, "only confirmed extractions can be re-opened")
        new = c.execute("""INSERT INTO core.rh_plan_extraction (upload_id, page, level_name, source, calibrated, calibration_id, model, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id""",
                        (e["upload_id"], e["page"], e["level_name"], e["source"], e["calibrated"], e["calibration_id"], json.dumps(e["model"]), by)).fetchone()
        c.commit()
    return get_extraction(new["id"])

def confirm(eid: int, evidence_level: str, level_name: str | None, by: str = "owner") -> dict:
    if evidence_level not in EVIDENCE: raise HTTPException(422, f"evidence_level must be one of {EVIDENCE} (where did this plan come from?)")
    with conn() as c:
        e = c.execute("SELECT * FROM core.rh_plan_extraction WHERE id = %s", (eid,)).fetchone()
        if not e: raise HTTPException(404, "no such extraction")
        if e["status"] == "human_confirmed": raise HTTPException(409, "already confirmed")
        if not e["model"]["rooms"]: raise HTTPException(422, "nothing to confirm: no rooms")
        unknown = [r["id"] for r in e["model"]["rooms"] if r["type"] == "unknown"]
        if unknown: raise HTTPException(422, f"set a type for every room before confirming (unknown: {unknown}). Use 'other' if a room does not fit.")
        u = _upload(c, e["upload_id"])
        c.execute("""UPDATE core.rh_plan_extraction SET status = 'human_confirmed', confirmed_at = now(), confirmed_by = %s, level_name = COALESCE(%s, level_name) WHERE id = %s""", (by, level_name, eid))
        c.execute("""UPDATE core.rh_plan_extraction SET superseded_by = %s WHERE upload_id = %s AND page = %s AND id <> %s AND status = 'human_confirmed' AND superseded_by IS NULL""", (eid, e["upload_id"], e["page"], eid))
        c.execute("UPDATE core.rh_property SET evidence_level = %s WHERE parcel_id = %s", (evidence_level, u["parcel_id"]))
        facts = recompute_facts(c, u["parcel_id"], by)
        c.commit()
    return {"extraction": get_extraction(eid), "facts_written": facts}

def recompute_facts(c, parcel_id: int, by: str) -> list[dict]:
    """Aggregate every current human-confirmed extraction of the property into CONFIRMED facts. Measured facts exist only where calibrated."""
    exts = c.execute("""SELECT x.id, x.model, x.calibrated, x.level_name FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id = x.upload_id
                        WHERE u.parcel_id = %s AND x.status = 'human_confirmed' AND x.superseded_by IS NULL ORDER BY x.id""", (parcel_id,)).fetchall()
    if not exts: return []
    cnt = lambda *types: sum(1 for x in exts for r in x["model"]["rooms"] if r["type"] in types)
    ids = ", ".join(f"#{x['id']}" for x in exts); levels = ", ".join(str(x["level_name"] or "unnamed level") for x in exts)
    src = f"plan extraction {ids} (human confirmed)"; note = f"counted on confirmed levels only ({levels}); levels not uploaded or confirmed are unknown"
    out = []
    def put(field, value, extra=None):
        if value is None: return
        if set_fact(c, parcel_id, field, value, src, "CONFIRMED", "plan reader + human review", (extra + "; " if extra else "") + note, by=by): out.append({"field": field, "value": value})
    put("bedrooms_total", cnt("bedroom")); put("rooms_with_ensuite", cnt("ensuite"), "counts ensuite rooms; each is assumed to serve one bedroom: check")
    put("shared_bathrooms", cnt("bathroom")); put("kitchens", cnt("kitchen")); put("laundries", cnt("laundry")); put("lounge_dining_areas", cnt("lounge", "dining"))
    put("staff_office_rooms", cnt("office")); put("stairs_count", cnt("stairs")); put("lifts", {"count": cnt("lift")})
    cal = [x for x in exts if x["calibrated"]]
    if cal:
        widths = [cr["min_width_m"] for x in cal for cr in x["model"].get("corridors", [])]
        put("corridor_width_min_m", min(widths) if widths else None, "approximate: short side of minimum rotated rectangle")
        dw = [d["width_m"] for x in cal for d in x["model"].get("doors", []) if d.get("width_m")]
        put("door_width_min_m", min(dw) if dw else None)
        put("net_room_area_m2", round(sum(r["area_m2"] or 0 for x in cal for r in x["model"]["rooms"] if r["type"] not in ("corridor", "stairs", "lift")), 2), "sum of room areas excluding corridors, stairs, lifts, on calibrated levels only")
    return out
