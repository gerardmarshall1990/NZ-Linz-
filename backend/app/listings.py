"""Listings (MASTER_SPEC Part 4 section 2, Part 6.1): CSV/manual import, address matching to LINZ address points and parcels with a confidence level, history, dedupe, source coverage.
No scraping and no calls to listing sites: the only inputs are files you give it. Text and photos are not stored: only structured facts and the link."""
import csv, hashlib, io, re
from datetime import date
from fastapi import HTTPException
import yaml
from .config import ROOT
from .db import conn
from .facts import set_fact

STREET = {"st": "street", "rd": "road", "ave": "avenue", "av": "avenue", "dr": "drive", "cres": "crescent", "pl": "place", "tce": "terrace", "ln": "lane", "hwy": "highway", "cl": "close", "ct": "court",
          "pde": "parade", "bvd": "boulevard", "blvd": "boulevard", "esp": "esplanade", "sq": "square", "gr": "grove", "rise": "rise", "way": "way", "wy": "way", "cct": "circuit", "pk": "park"}
FIELDS = {  # canonical field -> accepted CSV header names (lower case)
    "source_id": ["source_id", "listing_id", "id", "listing id", "trademe_id"], "listing_type": ["listing_type", "type"], "address": ["address", "raw_address", "street_address", "full_address"],
    "suburb": ["suburb"], "rent_per_week": ["rent_per_week", "rent", "weekly_rent", "rent per week"], "price": ["price", "asking_price"], "bedrooms": ["bedrooms", "beds", "bedroom"],
    "bathrooms": ["bathrooms", "baths", "bathroom"], "property_type": ["property_type", "propertytype"], "floor_area_m2": ["floor_area_m2", "floor_area", "floor area"], "parking": ["parking", "carparks"],
    "available_from": ["available_from", "available"], "listed_date": ["listed_date", "listed"], "agent_name": ["agent_name", "agent"], "agent_business_contact": ["agent_business_contact", "agent_contact"],
    "url": ["url", "link"], "has_floor_plan": ["has_floor_plan", "floor_plan"], "has_photos": ["has_photos", "photos"], "description": ["description"]}

def sources() -> dict:
    s = yaml.safe_load((ROOT / "config/listing_sources.yaml").read_text())["sources"]
    with conn() as c: counts = {r["source"]: r["n"] for r in c.execute("SELECT source, count(*) n FROM core.user_listing WHERE status = 'active' GROUP BY 1").fetchall()}
    live = [v["label"] for v in s.values() if v["status"] == "live"]; not_live = [v["label"] for v in s.values() if v["status"] != "live"]
    return {"sources": {k: {**v, "active_listings": counts.get(k, 0)} for k, v in s.items()},
            "coverage_warning": f"{', '.join(live)} live; {', '.join(not_live)} not connected: coverage is incomplete." if not_live else None}

def parse_address(raw: str) -> dict:
    """'12B/45 Queen Street, Grey Lynn, Auckland' -> unit, number, suffix, street (normalised), suburb hint. Returns {} if no street number is found."""
    s = re.sub(r"\s+", " ", (raw or "").strip().lower().replace("’", "'"))
    parts = [p.strip() for p in s.split(",")]; head = parts[0]; tail = [p for p in parts[1:] if p and p not in ("auckland", "new zealand", "nz")]
    m = re.match(r"^(?:(?:unit|flat|apt|apartment)\s*)?(?:([0-9]+[a-z]?)\s*/\s*)?([0-9]+)\s*([a-z]?)\s+(.+)$", head)
    if not m: return {}
    unit, num, suf, street = m.groups()
    words = street.split()
    words = [STREET.get(w, w) for w in words]
    return {"unit": unit.upper() if unit else None, "number": int(num), "suffix": (suf or "").upper(), "street": " ".join(words), "suburb": tail[0] if tail else None}

def match_address(c, raw: str, suburb: str | None = None) -> dict:
    p = parse_address(raw)
    if not p: return {"confidence": "none", "method": "no street number found", "address_id": None, "parcel_id": None}
    sub = (suburb or p["suburb"] or "").lower() or None
    rows = c.execute("""SELECT address_id, unit, address_number_suffix AS suffix, lower(suburb_locality_ascii) AS suburb, lower(full_road_name_ascii) AS road
                        FROM raw.linz_addresses WHERE address_number = %s AND lower(full_road_name_ascii) = %s AND address_lifecycle = 'Current'""", (p["number"], p["street"])).fetchall()
    if not rows: return {"confidence": "none", "method": "street and number not found in LINZ addresses", "address_id": None, "parcel_id": None, "parsed": p}
    if sub:
        by_sub = [r for r in rows if r["suburb"] == sub]
        if by_sub: rows = by_sub
        elif len({r["suburb"] for r in rows}) > 1: return {"confidence": "low", "method": "street and number exist in several suburbs; suburb did not match", "address_id": None, "parcel_id": None, "parsed": p}
    if p["suffix"]: rows = [r for r in rows if (r["suffix"] or "").upper() == p["suffix"]] or rows
    exact = [r for r in rows if (p["unit"] or "").lower() == (r["unit"] or "").lower()]
    pick = exact if exact else rows
    ids = [r["address_id"] for r in pick]
    parcels = {x["parcel_id"] for x in c.execute("SELECT s.parcel_id FROM raw.linz_addresses a JOIN core.sites s ON ST_Intersects(s.geom, a.geom) WHERE a.address_id = ANY(%s)", (ids,)).fetchall()}
    if not parcels: return {"confidence": "low", "method": "address point is not inside any parcel in core.sites", "address_id": ids[0], "parcel_id": None, "parsed": p}
    if len(parcels) > 1: return {"confidence": "low", "method": "address matches points on different parcels (review)", "address_id": ids[0], "parcel_id": None, "parsed": p}
    n = len(pick); conf = "high" if (n == 1 or (exact and len(exact) == 1) or not p["unit"]) and (sub is None or pick[0]["suburb"] == sub) else "medium"
    if sub is None and conf == "high": conf = "medium"
    return {"confidence": conf, "method": ("unit and number matched" if exact and p["unit"] else "number and street matched") + ("" if sub else "; no suburb given"), "address_id": ids[0], "parcel_id": parcels.pop(), "parsed": p}

def _num(x):
    if x in (None, ""): return None
    try: return float(re.sub(r"[^0-9.]", "", str(x)))
    except ValueError: return None

def _bool(x):
    if x in (None, ""): return None
    return str(x).strip().lower() in ("1", "true", "yes", "y")

def _date(x):
    if not x: return None
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try: return __import__("datetime").datetime.strptime(str(x).strip(), f).date()
        except ValueError: pass
    return None

def read_rows(text: str) -> tuple[list[dict], list[str]]:
    rdr = csv.DictReader(io.StringIO(text)); hdr = {h.strip().lower(): h for h in (rdr.fieldnames or [])}
    colmap = {f: next((hdr[a] for a in alts if a in hdr), None) for f, alts in FIELDS.items()}
    if not colmap["address"]: raise HTTPException(422, f"CSV needs an address column (accepted names: {FIELDS['address']})")
    rows = []
    for r in rdr:
        g = lambda f: (r.get(colmap[f]) or "").strip() if colmap[f] else ""
        if not g("address"): continue
        rows.append({k: g(k) for k in FIELDS})
    return rows, [f for f, c_ in colmap.items() if c_ is None]

def import_csv(text: str, source: str = "csv_manual", dry_run: bool = True, snapshot: bool = False, today: date | None = None) -> dict:
    """Import listings. A row's identity is (source, source_id); without an id it is source + normalised address + unit + type. dry_run reports without writing.
    snapshot=True marks active listings of this source that are missing from the file as removed (use only for a complete export)."""
    today = today or date.today()
    if source not in yaml.safe_load((ROOT / "config/listing_sources.yaml").read_text())["sources"]: raise HTTPException(422, "unknown source")
    rows, missing_cols = read_rows(text); res = {"rows": len(rows), "new": 0, "changed": 0, "unchanged": 0, "removed": 0, "matched": {"high": 0, "medium": 0, "low": 0, "none": 0}, "missing_columns": missing_cols, "details": [], "dry_run": dry_run}
    seen_ids = set()
    with conn() as c:
        for r in rows:
            p = parse_address(r["address"]); ltype = (r["listing_type"] or ("rent" if r["rent_per_week"] else "sale")).lower()
            if ltype not in ("rent", "sale"): raise HTTPException(422, f"listing_type must be rent or sale (got {ltype!r})")
            sid = r["source_id"] or hashlib.sha1(f"{p.get('unit')}|{p.get('number')}{p.get('suffix')}|{p.get('street')}|{ltype}".encode()).hexdigest()[:16]
            m = match_address(c, r["address"], r["suburb"] or None); res["matched"][m["confidence"]] += 1
            vals = {"listing_type": ltype, "raw_address": r["address"], "suburb": r["suburb"] or (p.get("suburb") or None), "rent_per_week": _num(r["rent_per_week"]), "price": _num(r["price"]),
                    "bedrooms": int(_num(r["bedrooms"])) if _num(r["bedrooms"]) is not None else None, "bathrooms": int(_num(r["bathrooms"])) if _num(r["bathrooms"]) is not None else None,
                    "property_type": r["property_type"] or None, "floor_area_m2": _num(r["floor_area_m2"]), "parking": int(_num(r["parking"])) if _num(r["parking"]) is not None else None,
                    "available_from": _date(r["available_from"]), "listed_date": _date(r["listed_date"]), "agent_name": r["agent_name"] or None, "agent_business_contact": r["agent_business_contact"] or None,
                    "url": r["url"] or None, "description_hash": hashlib.sha256(r["description"].encode()).hexdigest() if r["description"] else None,
                    "has_floor_plan": _bool(r["has_floor_plan"]), "has_photos": _bool(r["has_photos"])}
            seen_ids.add(sid)
            old = c.execute("SELECT * FROM core.user_listing WHERE source = %s AND source_id = %s", (source, sid)).fetchone()
            if not old:
                res["new"] += 1; res["details"].append({"source_id": sid, "address": r["address"], "change": "new", "match": m["confidence"], "method": m["method"]})
                if dry_run: continue
                c.execute("""INSERT INTO core.user_listing (source, source_id, address_id, parcel_id, match_confidence, match_method, first_seen, last_seen, """ + ", ".join(vals) + ") VALUES (%s,%s,%s,%s,%s,%s,%s,%s," + ",".join(["%s"] * len(vals)) + ")",
                          (source, sid, m["address_id"], m["parcel_id"], m["confidence"], m["method"], today, today, *vals.values())); continue
            diffs = {k: (old[k], v) for k, v in vals.items() if (old[k] is not None and v is not None and old[k] != v and str(old[k]) != str(v)) or (old[k] is None and v is not None)}
            relist = old["status"] == "removed"
            if relist: diffs["status"] = ("removed", "active")
            if not diffs: res["unchanged"] += 1
            else: res["changed"] += 1; res["details"].append({"source_id": sid, "address": r["address"], "change": {k: [str(a), str(b)] for k, (a, b) in diffs.items()}})
            if dry_run: continue
            lid = old["id"]
            for k, (a, b) in diffs.items(): c.execute("INSERT INTO core.user_listing_history (listing_id, changed_on, field, old_value, new_value) VALUES (%s,%s,%s,%s,%s)", (lid, today, k, None if a is None else str(a), None if b is None else str(b)))
            keep_review = old["match_reviewed"]
            sets = {**{k: v for k, v in vals.items() if v is not None}, "last_seen": today, "status": "active"}
            if not keep_review: sets.update(address_id=m["address_id"], parcel_id=m["parcel_id"], match_confidence=m["confidence"], match_method=m["method"])
            c.execute("UPDATE core.user_listing SET " + ", ".join(f"{k} = %s" for k in sets) + " WHERE id = %s", (*sets.values(), lid))
        if snapshot:
            for o in c.execute("SELECT id, source_id FROM core.user_listing WHERE source = %s AND status = 'active'", (source,)).fetchall():
                if o["source_id"] in seen_ids: continue
                res["removed"] += 1
                if not dry_run:
                    c.execute("UPDATE core.user_listing SET status = 'removed' WHERE id = %s", (o["id"],)); c.execute("INSERT INTO core.user_listing_history (listing_id, changed_on, field, old_value, new_value) VALUES (%s,%s,'status','active','removed')", (o["id"], today))
        if not dry_run: c.commit()
    res["coverage"] = sources()["coverage_warning"]
    return res

def upgrade_property_record(listing_id: int) -> dict:
    """A listing matched with high or medium confidence upgrades the Property Record's bedrooms/bathrooms to DOCUMENTED (source: listing). Never overwrites a CONFIRMED fact."""
    with conn() as c:
        l = c.execute("SELECT * FROM core.user_listing WHERE id = %s", (listing_id,)).fetchone()
        if not l: raise HTTPException(404, "no such listing")
        if l["parcel_id"] is None or l["match_confidence"] not in ("high", "medium"): return {"upgraded": [], "reason": "address not matched with enough confidence: review the match first"}
        c.execute("INSERT INTO core.rh_property (parcel_id, created_by) VALUES (%s, 'listing') ON CONFLICT DO NOTHING", (l["parcel_id"],))
        done, skipped = [], []
        for field, v in (("bedrooms_total", l["bedrooms"]), ("bathrooms_total", l["bathrooms"])):
            if v is None: continue
            cur = c.execute("SELECT confidence FROM core.rh_property_fact WHERE parcel_id = %s AND field = %s", (l["parcel_id"], field)).fetchone()
            if cur and cur["confidence"] == "CONFIRMED": skipped.append({"field": field, "reason": "already CONFIRMED from a plan"}); continue
            if set_fact(c, l["parcel_id"], field, v, f"listing {l['source']}:{l['source_id']} ({l['listing_type']})", "DOCUMENTED", "listing facts as published", "from the listing, not verified on site", by="listing"): done.append(field)
        c.commit()
    return {"upgraded": done, "skipped": skipped, "parcel_id": l["parcel_id"]}

def review_match(listing_id: int, parcel_id: int | None) -> dict:
    """The owner fixes or confirms a low-confidence match. parcel_id=None leaves it unmatched but reviewed."""
    with conn() as c:
        if parcel_id is not None and not c.execute("SELECT 1 FROM core.sites WHERE parcel_id = %s", (parcel_id,)).fetchone(): raise HTTPException(404, "no such parcel")
        n = c.execute("UPDATE core.user_listing SET parcel_id = %s, match_confidence = %s, match_method = 'reviewed by owner', match_reviewed = true WHERE id = %s",
                      (parcel_id, "high" if parcel_id else "none", listing_id)).rowcount
        if not n: raise HTTPException(404, "no such listing")
        c.commit()
    return {"id": listing_id, "parcel_id": parcel_id, "match_confidence": "high" if parcel_id else "none"}

def review_queue() -> list[dict]:
    with conn() as c:
        return [{**r, "first_seen": str(r["first_seen"])} for r in c.execute("SELECT id, source, raw_address, suburb, match_confidence, match_method, first_seen FROM core.user_listing WHERE match_confidence IN ('low','none') AND NOT match_reviewed AND status = 'active' ORDER BY id").fetchall()]

# ----------------------------------------------------------------------------------- verdicts
def _listing_json(r: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else (float(v) if hasattr(v, "as_tuple") else v)) for k, v in r.items()}

def verdict_for(listing_id: int, overrides: dict | None = None) -> dict:
    from . import scenarios, verdict as V
    from .compliance import ACT_PATTERNS
    with conn() as c:
        l = c.execute("SELECT * FROM core.user_listing WHERE id = %s", (listing_id,)).fetchone()
        if not l: raise HTTPException(404, "no such listing")
        site = c.execute("SELECT parcel_id, zone_name, title_type, hazard_flags, pc120_depends, overlays FROM core.sites WHERE parcel_id = %s", (l["parcel_id"],)).fetchone() if l["parcel_id"] else None
        rows = c.execute("""SELECT activity, status_class, section_ref FROM analytics.rules WHERE topic = 'activity_status' AND status = 'operative' AND zone = %s AND activity ILIKE ANY (%s)""",
                         (site["zone_name"], list(ACT_PATTERNS))).fetchall() if site and site["zone_name"] else []
        tier = c.execute("SELECT confidence FROM core.rh_property_fact WHERE parcel_id = %s AND field = 'bedrooms_total'", (l["parcel_id"],)).fetchone() if l["parcel_id"] else None
        pt = c.execute("SELECT ST_X(ST_Transform(ST_Centroid(geom), 4326)) AS lon, ST_Y(ST_Transform(ST_Centroid(geom), 4326)) AS lat FROM raw.linz_addresses WHERE address_id = %s", (l["address_id"],)).fetchone() if l["address_id"] else None
    p = scenarios.assumptions(overrides)
    v = V.verdict(_listing_json(l), site, rows, p, (tier or {}).get("confidence", "DOCUMENTED"))
    return {"listing": _listing_json(l), **v, "lon": pt["lon"] if pt else None, "lat": pt["lat"] if pt else None, "source_coverage": sources()["coverage_warning"]}

def search(filters: dict, overrides: dict | None = None) -> dict:
    with conn() as c:
        q, a = ["status = 'active'"], []
        for k, col, op in (("min_beds", "bedrooms", ">="), ("max_beds", "bedrooms", "<="), ("min_rent", "rent_per_week", ">="), ("max_rent", "rent_per_week", "<=")):
            if filters.get(k) is not None: q.append(f"{col} {op} %s"); a.append(filters[k])
        if filters.get("suburb"): q.append("lower(suburb) = lower(%s)"); a.append(filters["suburb"])
        if filters.get("source"): q.append("source = %s"); a.append(filters["source"])
        ids = [r["id"] for r in c.execute("SELECT id FROM core.user_listing WHERE " + " AND ".join(q) + " ORDER BY id", a).fetchall()]
    out = [verdict_for(i, overrides) for i in ids]
    if filters.get("verdict"): out = [o for o in out if o["verdict"] == filters["verdict"]]
    counts = {k: sum(1 for o in out if o["verdict"] == k) for k in ("GREEN", "AMBER", "RED", "GREY")}
    return {"count": len(out), "verdict_counts": counts, "listings": out, "source_coverage": sources()["coverage_warning"]}
