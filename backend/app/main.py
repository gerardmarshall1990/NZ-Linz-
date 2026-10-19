"""FastAPI app: property intake, Property Record, uploads, plan reader with human review (MASTER_SPEC Part 7 step 1).
Run:  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000   (from the repo root)"""
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from . import agent, auth, briefs, settings, listings, proposal, scenarios, calibration, compliance, drawings, estimates, facts, gaps, layout, plans, uploads, vision_reader
from .config import upload_dir
from .db import conn
from .pack_routes import r as pack_router

app = FastAPI(title="NZ Property Intelligence: Remote Conversion Pipeline", version="0.1", docs_url=None, redoc_url=None, openapi_url=None)
app.middleware("http")(auth.middleware)
app.include_router(pack_router)
STATIC = Path(__file__).parent / "static"
FOOTER = "Screening and preparation tool. Not planning, legal, engineering or financial advice. Council decides applications. Confirm with a qualified planner and the relevant professionals."

@app.get("/api/health")
def health(): return {"ok": True}          # public and minimal: nothing about the data or configuration

@app.get("/api/status")
def status():
    with conn() as c: n = c.execute("SELECT count(*) AS n FROM core.sites").fetchone()["n"]
    return {"ok": True, "sites": n, "vision_available": vision_reader.available(), "agent_available": agent.available(), "footer": FOOTER}

class LoginIn(BaseModel):
    password: str = Field(max_length=200)

@app.get("/login", response_class=HTMLResponse)
def login_form(): return auth.login_page()

@app.post("/login")
def login(body: LoginIn, request: Request):
    from fastapi.responses import JSONResponse
    ip = auth._ip(request)
    if not auth.configured(): return JSONResponse({"detail": "server not configured: set APP_PASSWORD"}, 503)
    if auth.locked(ip): return JSONResponse({"detail": "too many attempts: wait 15 minutes"}, 429)
    if not auth.check_password(body.password):
        auth.record_fail(ip); return JSONResponse({"detail": "wrong password"}, 401)
    r = JSONResponse({"ok": True}); auth.set_cookie(r, request, auth.create_session()); return r

@app.post("/logout")
def logout(request: Request):
    from fastapi.responses import JSONResponse
    auth.destroy(request.cookies.get(auth.COOKIE)); r = JSONResponse({"ok": True}); r.delete_cookie(auth.COOKIE, path="/"); return r

@app.get("/", response_class=HTMLResponse)
def home(): return (STATIC / "app.html").read_text()

@app.get("/plans", response_class=HTMLResponse)
def ui(): return (STATIC / "ui.html").read_text()

# ---------------- sites
@app.get("/api/sites/search")
def search_sites(q: str = Query(min_length=3, max_length=80)):
    with conn() as c:
        rows = c.execute("""SELECT parcel_id, address, suburb, area_m2::float AS area_m2, zone_name, building_count FROM core.sites WHERE address ILIKE %s ORDER BY address LIMIT 20""", (f"%{q.strip()}%",)).fetchall()
    return rows

@app.get("/api/sites/at")
def site_at(lat: float = Query(ge=-48, le=-34), lon: float = Query(ge=165, le=179)):
    with conn() as c:
        r = c.execute("""SELECT parcel_id, address, suburb, zone_name FROM core.sites WHERE ST_Intersects(geom, ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 2193)) LIMIT 1""", (lon, lat)).fetchone()
    if not r: raise HTTPException(404, "no parcel here (outside the loaded area or on road/water)")
    return r

@app.get("/api/map/listings")
def map_listings(min_beds: int | None = None, max_beds: int | None = None, min_rent: float | None = None, max_rent: float | None = None, suburb: str | None = None, verdict: str | None = None):
    r = listings.search({"min_beds": min_beds, "max_beds": max_beds, "min_rent": min_rent, "max_rent": max_rent, "suburb": suburb, "verdict": verdict})
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [o["lon"], o["lat"]]},
              "properties": {"id": o["listing"]["id"], "verdict": o["verdict"], "beds": o["listing"]["bedrooms"], "rent": o["listing"]["rent_per_week"], "address": o["listing"]["raw_address"],
                             "confidence": o["confidence"], "parcel_id": o["listing"]["parcel_id"], "match": o["listing"]["match_confidence"], "placeholders": bool(o.get("placeholder_banner"))}} for o in r["listings"] if o["lon"] is not None]
    return {"type": "FeatureCollection", "features": feats, "verdict_counts": r["verdict_counts"], "not_on_map": r["count"] - len(feats), "source_coverage": r["source_coverage"], "placeholder_banner": ("Uses placeholder inputs: not decision-grade: verdicts are capped at AMBER" if any(f["properties"]["placeholders"] for f in feats) else None)}

@app.get("/api/sites/{parcel_id}")
def get_site(parcel_id: int):
    with conn() as c:
        s = c.execute("""SELECT parcel_id, appellation, address, suburb, area_m2::float AS area_m2, zone_name, title_type, title_no, building_count, total_footprint_m2::float AS footprint_m2,
                                address_count, overlays, hazard_flags, maori_land_linz, pc120_depends, pc120_proposed_zone,
                                ST_AsGeoJSON(ST_Transform(geom, 4326))::json AS geometry,
                                EXISTS (SELECT 1 FROM core.rh_property p WHERE p.parcel_id = core.sites.parcel_id) AS has_property_record
                         FROM core.sites WHERE parcel_id = %s""", (parcel_id,)).fetchone()
    if not s: raise HTTPException(404, "no such parcel")
    s["hazard_note"] = "Natural hazard flags are information only for rest home conversions of existing buildings (decision 13)."
    return s

# ---------------- Property Record
class FactIn(BaseModel):
    field: str
    value: object
    source: str = Field(min_length=2)
    confidence: Literal["ESTIMATED", "DOCUMENTED", "CONFIRMED"]
    note: str | None = None

@app.post("/api/property/{parcel_id}")
def create_property(parcel_id: int, auto_estimate: bool = True):
    with conn() as c:
        if not c.execute("SELECT 1 FROM core.sites WHERE parcel_id = %s", (parcel_id,)).fetchone(): raise HTTPException(404, "no such parcel")
        c.execute("INSERT INTO core.rh_property (parcel_id, created_by) VALUES (%s, 'owner') ON CONFLICT DO NOTHING", (parcel_id,)); c.commit()
    done = estimates.auto_estimates(parcel_id) if auto_estimate else []
    return {**facts.get_property(parcel_id), "auto_estimates_written": done}

@app.get("/api/property/{parcel_id}")
def read_property(parcel_id: int): return facts.get_property(parcel_id)

@app.put("/api/property/{parcel_id}/facts")
def put_fact(parcel_id: int, f: FactIn):
    facts.get_property(parcel_id)
    with conn() as c:
        changed = facts.set_fact(c, parcel_id, f.field, f.value, f.source, f.confidence, "manual entry", f.note); c.commit()
    return {"changed": changed, "property": facts.get_property(parcel_id)}

@app.get("/api/property/{parcel_id}/history")
def read_history(parcel_id: int, field: str | None = None): return facts.history(parcel_id, field)

@app.get("/api/property/{parcel_id}/export.csv", response_class=PlainTextResponse)
def export(parcel_id: int): return PlainTextResponse(facts.export_csv(parcel_id), media_type="text/csv")

@app.post("/api/property/{parcel_id}/import")
async def import_facts(parcel_id: int, file: UploadFile = File(...), source: str = Form(min_length=2), dry_run: bool = Form(True)):
    facts.get_property(parcel_id)
    return facts.import_csv(parcel_id, (await file.read(1_000_000)).decode("utf-8", errors="replace"), source, dry_run)

# ---------------- uploads
@app.post("/api/property/{parcel_id}/uploads")
async def upload(parcel_id: int, file: UploadFile = File(...), kind: Literal["plan", "photo", "document", "scan", "other"] = Form("plan"), source_note: str | None = Form(None)):
    facts.get_property(parcel_id)
    data = await file.read(uploads.MAX_UPLOAD_BYTES + 1)
    s = uploads.store(parcel_id, file.filename or "upload", data)
    with conn() as c:
        r = c.execute("""INSERT INTO core.rh_upload (parcel_id, kind, original_name, stored_name, detected_type, size_bytes, sha256, uploaded_by, source_note, page_count) VALUES (%s,%s,%s,%s,%s,%s,%s,'owner',%s,%s)
                         RETURNING id, kind, original_name, detected_type, size_bytes, page_count""", (parcel_id, kind, uploads.safe_name(file.filename or "upload"), s["stored_name"], s["detected_type"], s["size_bytes"], s["sha256"], source_note, s["page_count"])).fetchone()
        c.commit()
    return r

@app.get("/api/property/{parcel_id}/uploads")
def list_uploads(parcel_id: int):
    with conn() as c:
        return [{**r, "uploaded_at": r["uploaded_at"].isoformat()} for r in c.execute("""SELECT id, kind, original_name, detected_type, size_bytes, page_count, uploaded_at, source_note FROM core.rh_upload WHERE parcel_id = %s ORDER BY id DESC""", (parcel_id,)).fetchall()]

@app.get("/api/uploads/{upload_id}/preview.png")
def preview(upload_id: int, page: int = 1):
    png, w, h = plans.preview_png(upload_id, page)
    return Response(png, media_type="image/png", headers={"X-Width": str(w), "X-Height": str(h), "Cache-Control": "private, max-age=3600"})

@app.get("/api/uploads/{upload_id}/download")
def download(upload_id: int):
    with conn() as c: u = plans._upload(c, upload_id)
    return FileResponse(upload_dir() / str(u["parcel_id"]) / u["stored_name"], filename=u["original_name"], headers={"Content-Disposition": f'attachment; filename="{u["original_name"]}"', "X-Content-Type-Options": "nosniff"})

# ---------------- plan reader
class CalIn(BaseModel):
    method: Literal["two_point", "stated_scale"]
    page: int = 1
    measurements: list[dict] | None = None
    denominator: float | None = None

@app.post("/api/uploads/{upload_id}/calibrate")
def do_calibrate(upload_id: int, body: CalIn):
    with conn() as c: u = plans._upload(c, upload_id)
    cal = calibration.two_point(body.measurements or []) if body.method == "two_point" else calibration.stated_scale(body.denominator or 0, u["detected_type"] == "pdf")
    return plans.calibrate(upload_id, body.page, cal)

class ExtractIn(BaseModel):
    mode: Literal["auto", "manual", "vision"] = "auto"
    page: int = 1
    units_override: str | None = None

@app.post("/api/uploads/{upload_id}/extract")
def do_extract(upload_id: int, body: ExtractIn):
    mode = body.mode
    if mode == "auto":
        with conn() as c: t = plans._upload(c, upload_id)["detected_type"]
        mode = "manual" if t != "dxf" and not vision_reader.available() else ("vision" if t != "dxf" else "manual")
    return plans.extract(upload_id, mode, body.page, body.units_override)

@app.get("/api/uploads/{upload_id}/extractions")
def list_extractions(upload_id: int):
    with conn() as c:
        return [{**r, "created_at": r["created_at"].isoformat()} for r in c.execute("SELECT id, page, level_name, source, status, calibrated, created_at, superseded_by FROM core.rh_plan_extraction WHERE upload_id = %s ORDER BY id DESC", (upload_id,)).fetchall()]

@app.get("/api/extractions/{eid}")
def read_extraction(eid: int): return plans.get_extraction(eid)

class EditIn(BaseModel):
    ops: list[dict]

@app.patch("/api/extractions/{eid}")
def patch_extraction(eid: int, body: EditIn): return plans.edit(eid, body.ops)

class ConfirmIn(BaseModel):
    evidence_level: Literal["PLANS_ON_FILE", "REMOTE_SCAN", "SCAN_VISIT", "ENGINEER_VISIT"]
    level_name: str | None = None

@app.post("/api/extractions/{eid}/confirm")
def do_confirm(eid: int, body: ConfirmIn): return plans.confirm(eid, body.evidence_level, body.level_name)

@app.post("/api/extractions/{eid}/reopen")
def do_reopen(eid: int): return plans.reopen(eid)

# ---------------- step 2: evidence gaps, layout options, compliance, briefs, drawings
class GapIn(BaseModel):
    status: Literal["NEEDS_PROFESSIONAL", "REQUESTED", "RECEIVED", "NOT_RELEVANT"]
    note: str | None = None

@app.get("/api/property/{parcel_id}/gaps")
def read_gaps(parcel_id: int): return gaps.compute(parcel_id)

@app.put("/api/property/{parcel_id}/gaps/{key}")
def put_gap(parcel_id: int, key: str, body: GapIn): return gaps.set_status(parcel_id, key, body.status, body.note)

@app.post("/api/property/{parcel_id}/layouts")
def make_layouts(parcel_id: int): facts.get_property(parcel_id); return layout.generate(parcel_id)

@app.get("/api/property/{parcel_id}/layouts")
def read_layouts(parcel_id: int): return layout.list_options(parcel_id)

@app.get("/api/layouts/{oid}")
def read_layout(oid: int): return layout.get_option(oid)

@app.get("/api/layouts/{oid}/drawing.dxf")
def layout_dxf(oid: int, level: int = 0):
    return Response(drawings.dxf(oid, level), media_type="application/dxf", headers={"Content-Disposition": f'attachment; filename="option{oid}_DRAFT.dxf"'})

@app.get("/api/layouts/{oid}/drawing.pdf")
def layout_pdf(oid: int, level: int = 0):
    return Response(drawings.pdf(oid, level), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="option{oid}_DRAFT.pdf"'})

@app.post("/api/property/{parcel_id}/compliance")
def run_compliance(parcel_id: int, option_id: int | None = None): facts.get_property(parcel_id); return compliance.run(parcel_id, option_id)

class BriefIn(BaseModel):
    option_id: int
    kind: Literal["fire", "structural", "accessibility", "services"]

@app.post("/api/property/{parcel_id}/briefs")
def make_brief(parcel_id: int, body: BriefIn): facts.get_property(parcel_id); return briefs.build(parcel_id, body.option_id, body.kind)

@app.get("/api/property/{parcel_id}/briefs")
def list_briefs(parcel_id: int):
    with conn() as c: return [{**r, "created_at": r["created_at"].isoformat()} for r in c.execute("SELECT id, option_id, kind, created_at FROM core.rh_brief WHERE parcel_id = %s ORDER BY id DESC", (parcel_id,)).fetchall()]

@app.get("/api/briefs/{bid}", response_class=PlainTextResponse)
def read_brief(bid: int):
    with conn() as c: r = c.execute("SELECT body_md FROM core.rh_brief WHERE id = %s", (bid,)).fetchone()
    if not r: raise HTTPException(404, "no such brief")
    return PlainTextResponse(r["body_md"], media_type="text/markdown")

# ---------------- economics, retrofit cost, Offer Builder
class EconIn(BaseModel):
    option_id: int
    assumptions: dict | None = None
    retrofit_total: float | None = None

@app.post("/api/property/{parcel_id}/retrofit")
def post_retrofit(parcel_id: int, option_id: int): facts.get_property(parcel_id); return scenarios.retrofit_cost(parcel_id, option_id)

@app.post("/api/property/{parcel_id}/economics")
def post_economics(parcel_id: int, body: EconIn): facts.get_property(parcel_id); return scenarios.economics_run(parcel_id, body.option_id, body.assumptions, body.retrofit_total)

class OfferIn(BaseModel):
    option_id: int
    asking_rent: float
    current_net: float | None = None
    terms: dict
    assumptions: dict | None = None
    retrofit: dict | float | None = None
    allowance_pct: float | None = None
    timeline: dict | None = None
    timeline_scenario: Literal['target', 'delay', 'contract'] | None = None
    downside: dict | None = None

@app.post("/api/property/{parcel_id}/offers")
def post_offer(parcel_id: int, body: OfferIn):
    facts.get_property(parcel_id); d = body.model_dump(); return scenarios.offer_run(parcel_id, d.pop("option_id"), d)

@app.get("/api/property/{parcel_id}/scenarios")
def list_scenarios(parcel_id: int, kind: str | None = None):
    with conn() as c:
        return [{**r, "created_at": r["created_at"].isoformat()} for r in c.execute("SELECT id, option_id, kind, confidence, created_at FROM core.rh_scenario WHERE parcel_id = %s AND (%s::text IS NULL OR kind = %s) ORDER BY id DESC", (parcel_id, kind, kind)).fetchall()]

@app.get("/api/scenarios/{sid}/proposal")
def get_proposal(sid: int, mode: Literal["fixed", "jv", "hybrid"]): return proposal.build(sid, mode)

@app.get("/api/scenarios/{sid}/proposal.pdf")
def get_proposal_pdf(sid: int, mode: Literal["fixed", "jv", "hybrid"]):
    return Response(proposal.pdf(proposal.build(sid, mode)["markdown"]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="proposal_{sid}_{mode}.pdf"'})

# ---------------- listings (CSV / manual only: no scraping), match review, verdicts
@app.get("/api/listings/sources")
def listing_sources(): return listings.sources()

@app.post("/api/listings/import")
async def listing_import(file: UploadFile = File(...), source: str = Form("csv_manual"), dry_run: bool = Form(True), snapshot: bool = Form(False)):
    return listings.import_csv((await file.read(5_000_000)).decode("utf-8-sig", errors="replace"), source, dry_run, snapshot)

@app.get("/api/listings/review-queue")
def listing_review_queue(): return listings.review_queue()

class MatchIn(BaseModel):
    parcel_id: int | None = None

@app.put("/api/listings/{lid}/match")
def listing_review_match(lid: int, body: MatchIn): return listings.review_match(lid, body.parcel_id)

@app.post("/api/listings/{lid}/upgrade-record")
def listing_upgrade(lid: int): return listings.upgrade_property_record(lid)

class ListingOfferIn(BaseModel):
    terms: dict
    asking_rent: float | None = None
    current_net: float | None = None
    assumptions: dict | None = None
    retrofit: float | None = None
    timeline: dict | None = None
    downside: dict | None = None

@app.post("/api/listings/{lid}/offer")
def listing_offer(lid: int, body: ListingOfferIn): return scenarios.offer_for_listing(lid, body.model_dump())

class QuickOfferIn(BaseModel):
    current_rent: float | None = None
    beds: int | None = None
    fee_per_bed_per_week: float | None = None
    stabilised_occupancy: float | None = None
    retrofit: float | None = None
    assumptions: dict | None = None

@app.post("/api/listings/{lid}/quick-offer")
def listing_quick_offer(lid: int, body: QuickOfferIn): return scenarios.quick_offer_for_listing(lid, body.model_dump())

@app.get("/api/listings/{lid}")
def listing_get(lid: int): return listings.verdict_for(lid)

class SearchIn(BaseModel):
    filters: dict = {}
    assumptions: dict | None = None

@app.post("/api/listings/search")
def listing_search(body: SearchIn): return listings.search(body.filters, body.assumptions)

# ---------------- Placeholders page
@app.get("/api/placeholders")
def get_placeholders():
    from .labels import PLACEHOLDER_BANNER
    return {"banner": PLACEHOLDER_BANNER, "placeholders": settings.placeholder_rows(), "rule": "While any placeholder or estimated input is used, verdicts are capped at AMBER and every dependent figure carries the banner. Editing a value here turns it into your own figure."}

@app.post("/api/placeholders/load")
def load_placeholders(): return settings.load_placeholders()

# ---------------- My inputs (assumptions and rates entered in the app)
@app.get("/api/settings")
def get_settings(): return settings.view()

class AssumptionsIn(BaseModel):
    values: dict
    flags: dict | None = None
    notes: dict | None = None

@app.put("/api/settings/assumptions")
def put_assumptions(body: AssumptionsIn): return settings.set_assumptions(body.values, body.flags, body.notes)

class RatesIn(BaseModel):
    lines: dict | None = None
    pct: dict | None = None

@app.put("/api/settings/rates")
def put_rates(body: RatesIn): return settings.set_rates(body.lines, body.pct)

# ---------------- chat agent (blocked until ANTHROPIC_API_KEY and ANTHROPIC_MODEL are set)
class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None

@app.post("/api/chat")
def chat(body: ChatIn):
    import json as _json
    from fastapi.responses import StreamingResponse
    client = agent.make_client()          # 503 here if not configured, before any stream starts
    def gen():
        try:
            for ev in agent.chat(body.message, body.conversation_id, client): yield f"data: {_json.dumps(ev)}\n\n"
        except HTTPException as e: yield f"data: {_json.dumps({'type': 'error', 'text': e.detail})}\n\n"
        except Exception as e: yield f"data: {_json.dumps({'type': 'error', 'text': 'The agent hit an error: ' + type(e).__name__})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})
