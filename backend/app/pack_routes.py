"""Routes for the consent pack, statements, engineer reviews and feature flags (Part 7 step 4). The only routes reachable without the owner's login are /review/{token} and /api/review/{token}, and only while the engineer_review_links flag is ON."""
from datetime import date
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from . import consent_pack as cp, dealsheet, flags, plan_request, ranking, retrofit_calibration as rcal, reviews, validation
from .facts import get_property
from .layout import get_option
from .pack_pdf import md_to_pdf

r = APIRouter()

class PackIn(BaseModel): option_id: int
@r.post("/api/property/{parcel_id}/packs")
def make_pack(parcel_id: int, body: PackIn): return cp.build(parcel_id, body.option_id)
@r.get("/api/property/{parcel_id}/packs")
def packs(parcel_id: int): get_property(parcel_id); return cp.list_for_parcel(parcel_id)
@r.get("/api/packs/{pid}")
def pack(pid: int): return cp.get(pid)

class FieldsIn(BaseModel):
    fields: dict[str, str | None] = Field(default_factory=dict)
    resolutions: dict[str, str | None] = Field(default_factory=dict)
@r.put("/api/packs/{pid}/fields")
def put_fields(pid: int, body: FieldsIn): return cp.set_fields(pid, body.fields, body.resolutions)

class ReqIn(BaseModel):
    required: bool
    reason: str | None = None
@r.put("/api/packs/{pid}/documents/{key}/required")
def put_required(pid: int, key: str, body: ReqIn): return cp.set_not_required(pid, key, body.required, body.reason)

@r.get("/api/packs/{pid}/documents/{key}.md", response_class=PlainTextResponse)
def doc_md(pid: int, key: str): return PlainTextResponse(cp.render(pid, key))
@r.get("/api/packs/{pid}/documents/{key}.pdf")
def doc_pdf(pid: int, key: str): return Response(md_to_pdf(cp.render(pid, key), key), media_type="application/pdf")

@r.post("/api/packs/{pid}/documents/{key}/upload")
async def upload_doc(pid: int, key: str, file: UploadFile = File(...), author_name: str | None = Form(None), author_company: str | None = Form(None), psa_number: str | None = Form(None),
                     date_issued: date | None = Form(None), scope_note: str | None = Form(None)):
    data = await file.read(cp.MAX_UPLOAD_BYTES + 1)
    return cp.add_statement(pid, key, file.filename or "upload.pdf", data, {"author_name": author_name, "author_company": author_company, "psa_number": psa_number, "date_issued": date_issued, "scope_note": scope_note})

@r.get("/api/packs/{pid}/statements")
def list_statements(pid: int): return [cp.statement_view(s["id"]) for s in cp.statements(pid)]
class RegIn(BaseModel):
    status: str
    checked_by: str
    note: str | None = None
    checked_on: date | None = None
@r.post("/api/statements/{sid}/register-check")
def register_check(sid: int, body: RegIn): return cp.record_register_check(sid, body.status, body.checked_by, body.note, body.checked_on)
@r.post("/api/statements/{sid}/register-recheck")
def register_recheck(sid: int): return cp.recheck(sid)
@r.get("/api/statements/{sid}/file")
def statement_download(sid: int):
    name, data = cp.statement_file(sid); return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})

@r.get("/api/packs/{pid}/completeness")
def completeness(pid: int): return cp.completeness(pid)
@r.post("/api/packs/{pid}/ready-to-lodge")
def ready(pid: int): return cp.mark_ready(pid)
@r.get("/api/packs/{pid}/export.zip")
def export(pid: int): return Response(cp.export_zip(pid), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="consent-pack-DRAFT-{pid}.zip"'})
@r.get("/api/packs/{pid}/upload-sheet.pdf")
def upload_sheet(pid: int): return Response(md_to_pdf(cp.upload_sheet(pid), "Upload sheet"), media_type="application/pdf")

class LodgIn(BaseModel):
    answers: dict[str, str | None] = Field(default_factory=dict)
    sections_na: list[str] | None = None
@r.get("/api/packs/{pid}/lodgement")
def get_lodgement(pid: int): return cp.lodgement_view(pid)
@r.put("/api/packs/{pid}/lodgement")
def put_lodgement(pid: int, body: LodgIn): return cp.set_lodgement(pid, body.answers, body.sections_na)

# ---- reviews
class RevIn(BaseModel):
    role: str
    engineer_name: str | None = None
    engineer_company: str | None = None
@r.post("/api/packs/{pid}/reviews")
def new_review(pid: int, body: RevIn): return reviews.create(pid, body.role, body.engineer_name, body.engineer_company)
@r.get("/api/packs/{pid}/reviews")
def pack_reviews(pid: int): return reviews.list_for_pack(pid)
@r.post("/api/reviews/{rid}/send")
def send_review(rid: int): return reviews.send(rid)
@r.post("/api/reviews/{rid}/cancel")
def cancel_review(rid: int): return reviews.cancel(rid)
class RetIn(BaseModel): note: str | None = None
@r.post("/api/reviews/{rid}/returned")
def returned(rid: int, body: RetIn): return reviews.mark_returned(rid, body.note)
@r.get("/api/reviews/{rid}/package.zip")
def review_zip(rid: int): return Response(reviews.package_zip(rid), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="review-package-DRAFT-{rid}.zip"'})
@r.get("/api/reviews/metrics")
def review_metrics(): return reviews.metrics()

# ---- engineer side (token gated; 404 while the flag is off)
class CommentIn(BaseModel):
    author: str = ""
    body: str = Field(max_length=4000)
@r.get("/api/review/{tok}")
def rv_open(tok: str): return reviews.open_link(tok)
@r.post("/api/review/{tok}/comment")
def rv_comment(tok: str, body: CommentIn): return reviews.comment_link(tok, body.author, body.body)
@r.post("/api/review/{tok}/return")
def rv_return(tok: str, body: CommentIn): return reviews.return_link(tok, body.author)

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Engineer review (DRAFT)</title>
<style>body{font:15px system-ui;margin:12px;max-width:760px}pre{white-space:pre-wrap}.s{color:#b00;font-weight:600}textarea,input{width:100%;box-sizing:border-box;margin:4px 0}</style></head><body>
<div class="s" id="st"></div><h2 id="t"></h2><pre id="b"></pre><h3>Documents wanted from you</h3><ul id="w"></ul>
<h3>Comment</h3><input id="a" placeholder="Your name"><textarea id="c" rows="4" placeholder="Your comment"></textarea><button onclick="send()">Send comment</button> <button onclick="ret()">Return to owner</button><div id="m"></div>
<script>const tok=location.pathname.split('/').pop();
fetch('/api/review/'+tok).then(r=>r.ok?r.json():Promise.reject()).then(d=>{st.textContent=d.label;t.textContent=d.title;b.textContent=d.body_md;d.wanted_from_you.forEach(x=>{const l=document.createElement('li');l.textContent=x.document+' ('+x.type+'): return as a signed PDF to the owner';w.appendChild(l)})}).catch(()=>{document.body.textContent='This link is not available.'});
function post(p,body){return fetch('/api/review/'+tok+p,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}).then(r=>m.textContent=r.ok?'Done.':'Not available.')}
function send(){post('/comment',{author:a.value,body:c.value})}function ret(){post('/return',{author:a.value,body:''})}</script></body></html>"""
@r.get("/review/{tok}", response_class=HTMLResponse)
def rv_page(tok: str):
    if not flags.enabled("engineer_review_links"): raise HTTPException(404, "not found")
    return PAGE

# ---- flags
@r.get("/api/flags")
def get_flags(): return flags.all_flags()
class FlagIn(BaseModel): enabled: bool
@r.put("/api/flags/{key}")
def put_flag(key: str, body: FlagIn): return flags.set_flag(key, body.enabled)

# ---- deal sheet, ranking, what-if
@r.get("/api/property/{parcel_id}/dealsheet.pdf")
def deal_sheet_pdf(parcel_id: int, option_id: int | None = None): return Response(dealsheet.pdf(parcel_id, option_id), media_type="application/pdf")
@r.get("/api/property/{parcel_id}/dealsheet", response_class=PlainTextResponse)
def deal_sheet_md(parcel_id: int, option_id: int | None = None): return PlainTextResponse(dealsheet.build(parcel_id, option_id)["markdown"])
@r.get("/api/ranking")
def get_ranking(): return ranking.rank()
class WeightsIn(BaseModel): weights: dict[str, float]
@r.put("/api/ranking/weights")
def put_weights(body: WeightsIn): return ranking.set_weights(body.weights)
@r.get("/api/ranking/weights")
def get_weights(): return ranking.weights()
class WhatIfIn(BaseModel):
    option_id: int
    occupancy_pts: float = 0
    fee_pct: float = 0
    wage_pct: float = 0
    retrofit_pct: float = 0
@r.post("/api/property/{parcel_id}/whatif")
def what_if(parcel_id: int, body: WhatIfIn): return ranking.whatif(parcel_id, **body.model_dump())

# ---- retrofit calibration loop
class QuoteIn(BaseModel):
    line: str
    source: str
    quote_date: date
    quantity: float
    amount_ex_gst: float
    description: str | None = None
    unit: str | None = None
    region: str = "Auckland"
    parcel_id: int | None = None
    option_id: int | None = None
    note: str | None = None
@r.post("/api/retrofit/quotes")
def add_quote(body: QuoteIn): return rcal.add_quote(**body.model_dump())
@r.get("/api/retrofit/calibration")
def calibration_overview(): return rcal.overview()
@r.get("/api/retrofit/calibration/history")
def calibration_history(): return rcal.history()
@r.get("/api/retrofit/calibration/{line}")
def calibration_line(line: str): return rcal.summary_for(line)
@r.delete("/api/retrofit/quotes/{qid}")
def void_quote(qid: int): return rcal.void_quote(qid)
class ApplyIn(BaseModel):
    accept_single_quote: bool = False
    note: str | None = None
@r.post("/api/retrofit/calibration/{line}/apply")
def apply_calibration(line: str, body: ApplyIn): return rcal.apply(line, body.accept_single_quote, body.note)

# ---- plan request pack
@r.get("/api/property/{parcel_id}/plan-request/email")
def pr_email(parcel_id: int, sender: str | None = None): return plan_request.email(parcel_id, sender)
@r.get("/api/property/{parcel_id}/plan-request/council")
def pr_council(parcel_id: int): return plan_request.council_guidance(parcel_id)
@r.get("/api/property/{parcel_id}/site-visit")
def sv_form(parcel_id: int): return plan_request.site_visit_form(parcel_id)
class SiteVisitIn(BaseModel):
    values: dict[str, object]
    visitor: str | None = None
@r.post("/api/property/{parcel_id}/site-visit")
def sv_submit(parcel_id: int, body: SiteVisitIn): return plan_request.submit_site_visit(parcel_id, body.values, body.visitor)
class ReqLogIn(BaseModel):
    kind: str
    recipient: str | None = None
    sent_on: date | None = None
    follow_up_on: date | None = None
    note: str | None = None
@r.post("/api/property/{parcel_id}/plan-requests")
def pr_log(parcel_id: int, body: ReqLogIn): return plan_request.log_request(parcel_id, **body.model_dump())
@r.get("/api/property/{parcel_id}/plan-requests")
def pr_list(parcel_id: int): return plan_request.list_requests(parcel_id)
class StatusIn(BaseModel): status: str
@r.put("/api/plan-requests/{rid}")
def pr_status(rid: int, body: StatusIn): return plan_request.set_request_status(rid, body.status)

# ---- validation gate settings
class ValIn(BaseModel):
    tolerance_pct: float | None = None
    properties: list[int] | None = None
@r.get("/api/validation/config")
def val_get(): return validation.get_config()
@r.put("/api/validation/config")
def val_put(body: ValIn): return validation.set_config(body.tolerance_pct, body.properties)
