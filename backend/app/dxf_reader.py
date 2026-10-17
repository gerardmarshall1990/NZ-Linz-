"""DXF plan reader: parses CAD geometry directly (far more accurate than vision). Deterministic; no model involved.
Rooms come from closed polylines on room-like layers; if none exist, from polygonised wall lines (flagged). Labels from TEXT/MTEXT inside the polygon."""
import io, math, re
import ezdxf
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

INSUNITS = {1: ("in", 0.0254), 2: ("ft", 0.3048), 4: ("mm", 0.001), 5: ("cm", 0.01), 6: ("m", 1.0)}
ROOM_LAYER = re.compile(r"room|space|area|zone|\brm\b", re.I)
WALL_LAYER = re.compile(r"wall", re.I)
TYPE_RULES = [  # order matters
    ("ensuite", r"en-?suite|\bens\b"), ("bathroom", r"bath|toilet|\bwc\b|shower|wetroom|wet room"), ("bedroom", r"bed(room)?\b|\bbdrm\b|\bbr\b|bedroom"),
    ("kitchen", r"kitchen"), ("laundry", r"laundry|\bldy\b"), ("dining", r"dining"), ("lounge", r"lounge|living|sitting|family room|common room"),
    ("office", r"office|nurse|staff"), ("store", r"store|storage|cupboard|linen|pantry"), ("corridor", r"corridor|hall(way)?|passage|lobby"),
    ("stairs", r"stair"), ("lift", r"\blift\b|elevator"),
]

def classify(label: str) -> str:
    l = (label or "").lower()
    for t, rx in TYPE_RULES:
        if re.search(rx, l): return t
    return "unknown"

def _clean(text: str) -> str:
    t = re.sub(r"\\[A-Za-z0-9.]+;?|[{}]", " ", text or "")       # MTEXT formatting codes
    return re.sub(r"\s+", " ", t.replace("\\P", " ")).strip()

def parse_dxf(data: bytes, units_override: str | None = None) -> dict:
    try: doc = ezdxf.read(io.StringIO(data.decode("utf-8", errors="replace")))
    except Exception as e: raise ValueError(f"unreadable DXF: {e}")
    msp = doc.modelspace(); warnings = []
    code = doc.header.get("$INSUNITS", 0)
    unit, factor = INSUNITS.get(code, (None, None))
    if units_override:
        override = {u: f for u, f in ((v[0], v[1]) for v in INSUNITS.values())}
        if units_override not in override: raise ValueError(f"units_override must be one of {sorted(override)}")
        unit, factor = units_override, override[units_override]
    scaled = factor is not None
    f = factor or 1.0
    if not scaled: warnings.append("DXF has no drawing units ($INSUNITS): unscaled. Areas and widths are blank until you declare the units (calibration).")
    xf = lambda x, y: (x * f, y * f)

    texts = []
    for e in msp.query("TEXT MTEXT"):
        ins = e.dxf.insert; t = _clean(e.dxf.text if e.dxftype() == "TEXT" else e.text)
        if t: texts.append({"text": t, "pt": (ins.x, ins.y)})

    polys = []
    for e in msp.query("LWPOLYLINE POLYLINE"):
        if not getattr(e, "is_closed", False): continue
        pts = [(p[0], p[1]) for p in e.get_points("xy")] if e.dxftype() == "LWPOLYLINE" else [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if len(pts) >= 3: polys.append({"layer": e.dxf.layer, "poly": Polygon(pts)})
    derived = False
    room_polys = [p for p in polys if ROOM_LAYER.search(p["layer"])]
    if not room_polys:
        # fallback: polygonise wall lines
        segs = []
        for e in msp.query("LINE"):
            if WALL_LAYER.search(e.dxf.layer): segs.append(LineString([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]))
        for e in msp.query("LWPOLYLINE POLYLINE"):
            if WALL_LAYER.search(e.dxf.layer):
                pts = [(p[0], p[1]) for p in e.get_points("xy")] if e.dxftype() == "LWPOLYLINE" else [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                segs.append(LineString(pts + ([pts[0]] if getattr(e, "is_closed", False) else [])))
        if segs:
            room_polys = [{"layer": "walls(polygonised)", "poly": p} for p in polygonize(unary_union(segs))]
            derived = True; warnings.append("No room polygons found: rooms were derived by polygonising wall lines. Check every room.")
        else:
            room_polys = polys; warnings.append("No room or wall layers found: all closed polylines treated as candidate rooms. Check every room.")
    # drop a containing outline (a polygon that contains >= 2 others)
    keep = []
    for p in room_polys:
        inner = sum(1 for q in room_polys if q is not p and p["poly"].contains(q["poly"].representative_point()))
        if inner >= 2 and not derived: continue
        keep.append(p)
    rooms = []
    for i, p in enumerate(sorted(keep, key=lambda r: (round(r["poly"].centroid.y, 3), round(r["poly"].centroid.x, 3))), 1):
        inside = [t["text"] for t in texts if p["poly"].contains(Point(t["pt"]))]
        label = " ".join(inside)
        t = classify(label)
        coords = [xf(x, y) for x, y in list(p["poly"].exterior.coords)[:-1]]
        area = round(Polygon(coords).area, 3) if scaled else None
        rooms.append({"id": f"r{i}", "label": label or None, "type": t, "polygon": [[round(x, 4), round(y, 4)] for x, y in coords], "area_m2": area, "layer": p["layer"], "confidence": "extracted"})
        if not label: warnings.append(f"room r{i} has no text label inside it")
        elif t == "ensuite" and re.search(r"bed", label, re.I): warnings.append(f"room r{i} ('{label}') mentions both bedroom and ensuite: typed as ensuite; change it to bedroom if it is a bedroom with an ensuite")

    doors = []
    for e in msp.query("INSERT"):
        name, layer = e.dxf.name, e.dxf.layer
        if not (re.search(r"door", name, re.I) or re.search(r"door", layer, re.I)): continue
        w = None; how = None
        for a in e.attribs:
            if a.dxf.tag.upper() in ("WIDTH", "W", "DOOR_WIDTH"):
                try: w = float(re.sub(r"[^0-9.]", "", a.dxf.text)) * f; how = "attribute"
                except ValueError: pass
        if w is None and scaled:
            try:
                blk = doc.blocks.get(name); xs = []
                for be in blk:
                    if be.dxftype() == "LINE": xs += [be.dxf.start.x, be.dxf.end.x]
                if xs: w = (max(xs) - min(xs)) * abs(e.dxf.xscale) * f; how = "block size (approximate)"
            except Exception: pass
        doors.append({"id": f"d{len(doors) + 1}", "width_m": round(w, 3) if (w is not None and scaled) else None, "width_method": how, "at": [round(e.dxf.insert.x * f, 4), round(e.dxf.insert.y * f, 4)],
                      "layer": layer, "block": name, "fire_rated": None, "confidence": "extracted"})
    dims = []
    for e in msp.query("DIMENSION"):
        try: dims.append({"text": _clean(e.dxf.text), "measurement_m": round(e.dxf.actual_measurement * f, 4) if scaled else None})
        except Exception: pass
    corridors = []
    if scaled:
        for r in rooms:
            if r["type"] == "corridor":
                poly = Polygon(r["polygon"]); mrr = poly.minimum_rotated_rectangle
                xs = list(mrr.exterior.coords); edges = sorted(math.dist(xs[i], xs[i + 1]) for i in range(4))
                corridors.append({"room_id": r["id"], "min_width_m": round(edges[0], 3), "method": "short side of minimum rotated rectangle (approximate for non-rectangular corridors)"})
    allpts = [pt for r in rooms for pt in r["polygon"]]
    return {"schema": 1, "source": "dxf", "level_name": None, "units": {"drawing_unit": unit, "metres_per_unit": factor} if scaled else None, "calibrated": scaled, "unscaled": not scaled,
            "rooms": rooms, "doors": doors, "stairs": [], "lifts": [], "exits": [], "corridors": corridors, "dimensions": dims,
            "bounds": [min(p[0] for p in allpts), min(p[1] for p in allpts), max(p[0] for p in allpts), max(p[1] for p in allpts)] if allpts else None,
            "warnings": warnings, "derived_from_walls": derived}
