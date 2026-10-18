"""Routes for the consent pack, statements, engineer reviews and feature flags (Part 7 step 4). The only routes reachable without the owner's login are /review/{token} and /api/review/{token}, and only while the engineer_review_links flag is ON."""
from datetime import date
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from . import approvals, capacity, engineers, capture_portal, dashboard, nba, tasks, audit, field, offers, routeplan, portfolio, screen, screenapi, playbooks, bestuse, maori, layers, rcpack, devreport, devscenarios, services, crm, digest, trademe, capture_guide, certification, rfi, timeline, consent_pack as cp, dealsheet, flags, plan_request, ranking, retrofit_calibration as rcal, reviews, validation
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

# ---- approval records
@r.get("/api/approvals")
def approvals_pending(): return approvals.pending()
@r.get("/api/approvals/history")
def approvals_history(): return approvals.history()
class DecideIn(BaseModel):
    approve: bool
    note: str | None = None
@r.post("/api/approvals/{aid}/decide")
def approvals_decide(aid: int, body: DecideIn): return approvals.decide(aid, body.approve, body.note)
class LodgedIn(BaseModel):
    portal_ref: str
    lodged_on: date | None = None
    note: str | None = None
@r.post("/api/packs/{pid}/lodged")
def pack_lodged(pid: int, body: LodgedIn): return cp.mark_lodged(pid, body.portal_ref, body.lodged_on, body.note)

# ---- capture guide, RFI tracker, timeline, metrics, certification
@r.get("/api/property/{parcel_id}/capture-guide", response_class=PlainTextResponse)
def cg_md(parcel_id: int): return PlainTextResponse(capture_guide.build(parcel_id)["markdown"])
@r.get("/api/property/{parcel_id}/capture-guide.pdf")
def cg_pdf(parcel_id: int): return Response(capture_guide.pdf(parcel_id), media_type="application/pdf")

class RfiItemIn(BaseModel):
    text: str
    owner_role: str | None = None
class RfiIn(BaseModel):
    received_on: date
    summary: str
    items: list[RfiItemIn]
    due_on: date | None = None
    council_ref: str | None = None
    pack_id: int | None = None
@r.post("/api/property/{parcel_id}/rfis")
def rfi_add(parcel_id: int, body: RfiIn): return rfi.add(parcel_id, body.received_on, body.summary, [i.model_dump() for i in body.items], body.due_on, body.council_ref, body.pack_id)
@r.get("/api/property/{parcel_id}/rfis")
def rfi_list(parcel_id: int): return rfi.list_for(parcel_id)
@r.get("/api/rfis/overdue")
def rfi_overdue(): return rfi.overdue_all()
class RfiAnsIn(BaseModel):
    status: str
    response: str | None = None
@r.put("/api/rfi-items/{iid}")
def rfi_item(iid: int, body: RfiAnsIn): return rfi.answer_item(iid, body.status, body.response)
class RespIn(BaseModel): responded_on: date | None = None
@r.post("/api/rfis/{rid}/responded")
def rfi_responded(rid: int, body: RespIn): return rfi.mark_responded(rid, body.responded_on)
@r.post("/api/rfis/{rid}/close")
def rfi_close(rid: int): return rfi.close(rid)

@r.get("/api/property/{parcel_id}/timeline")
def tl_get(parcel_id: int, scenario: str = "target", opening: date | None = None): return timeline.plan(parcel_id, scenario, opening)
class TrackIn(BaseModel):
    lead_weeks: float | None = None
    source: str | None = None
@r.put("/api/timeline/tracks/{key}")
def tl_track(key: str, body: TrackIn): return timeline.set_track(key, body.lead_weeks, body.source)
class StructIn(BaseModel): light: bool | None = None
@r.put("/api/property/{parcel_id}/structure-light")
def tl_struct(parcel_id: int, body: StructIn): return timeline.set_structure_light(parcel_id, body.light)
class MsIn(BaseModel):
    planned_on: date | None = None
    actual_on: date | None = None
    note: str | None = None
@r.put("/api/property/{parcel_id}/milestones/{key}")
def tl_ms(parcel_id: int, key: str, body: MsIn): return timeline.set_milestone(parcel_id, key, body.planned_on, body.actual_on, body.note)
@r.get("/api/property/{parcel_id}/milestones")
def tl_ms_get(parcel_id: int): return timeline.milestones(parcel_id)
class MinIn(BaseModel):
    parcel_id: int | None = None
    step: str
    minutes: float
    note: str | None = None
    role: str = "owner"
@r.post("/api/metrics/minutes")
def metrics_log(body: MinIn): return timeline.log_minutes(body.parcel_id, body.step, body.minutes, body.note, body.role)
@r.get("/api/metrics")
def metrics_get(): return timeline.metrics()

@r.get("/api/property/{parcel_id}/certification")
def cert_get(parcel_id: int): return certification.view(parcel_id)
class CertIn(BaseModel):
    status: str
    note: str | None = None
@r.put("/api/property/{parcel_id}/certification/{key}")
def cert_set(parcel_id: int, key: str, body: CertIn): return certification.set_status(parcel_id, key, body.status, body.note)
@r.get("/api/certification/templates/{key}", response_class=PlainTextResponse)
def cert_template(key: str): return PlainTextResponse(certification.template(key))

# ---- digest, saved searches
@r.get("/api/digest")
def digest_get(since: date | None = None): return digest.build(since)
@r.post("/api/digest/run")
def digest_run(since: date | None = None): return digest.run_and_store(since)
@r.get("/api/digest/history")
def digest_history(): return digest.history()
class SearchIn(BaseModel):
    name: str
    filters: dict
@r.post("/api/saved-searches")
def ss_add(body: SearchIn): return digest.save_search(body.name, body.filters)
@r.get("/api/saved-searches")
def ss_list(): return digest.list_searches()
@r.delete("/api/saved-searches/{sid}")
def ss_del(sid: int): digest.delete_search(sid); return {"ok": True}

# ---- Trade Me connector (off until terms are read and keys are set)
@r.get("/api/trademe/status")
def tm_status(): return trademe.status()
class TmIn(BaseModel): params: dict = Field(default_factory=dict)
@r.post("/api/trademe/sync")
def tm_sync(body: TmIn): return trademe.sync(body.params)

# ---- CRM (all under /api/crm: 403 while outreach_enabled is false)
class LeadIn(BaseModel):
    listing_id: int | None = None
    parcel_id: int | None = None
    notes: str | None = None
@r.post("/api/crm/leads")
def crm_create(body: LeadIn): return crm.create_lead(body.listing_id, body.parcel_id, body.notes)
@r.get("/api/crm/leads/{lid}")
def crm_get(lid: int): return crm.view(lid)
@r.put("/api/crm/leads/{lid}")
def crm_update(lid: int, body: dict): return crm.update_lead(lid, body)
class ContIn(BaseModel): contactable: bool
@r.put("/api/crm/leads/{lid}/contactable")
def crm_contactable(lid: int, body: ContIn): return crm.set_contactable(lid, body.contactable)
class ActIn(BaseModel):
    kind: str
    outcome: str | None = None
    notes: str | None = None
@r.post("/api/crm/leads/{lid}/activities")
def crm_activity(lid: int, body: ActIn): return crm.add_activity(lid, body.kind, body.outcome, body.notes)
class StageIn(BaseModel):
    stage: str
    lost_reason: str | None = None
@r.put("/api/crm/leads/{lid}/stage")
def crm_stage(lid: int, body: StageIn): return crm.set_stage(lid, body.stage, body.lost_reason)
class DncIn(BaseModel):
    reason: str
    contact_name: str | None = None
    business_detail: str | None = None
    parcel_id: int | None = None
@r.post("/api/crm/do-not-contact")
def crm_dnc(body: DncIn): return crm.add_do_not_contact(body.reason, body.contact_name, body.business_detail, body.parcel_id)
@r.get("/api/crm/funnel")
def crm_funnel(): return crm.funnel()

# ---- development scenarios (Site Panel button 1), services
class DevIn(BaseModel):
    typology: str = "houses"
    unit: dict = Field(default_factory=dict)
    finance: dict = Field(default_factory=dict)
    access_width_m: float | None = None
    timeline_weeks: dict = Field(default_factory=dict)
@r.post("/api/dev/{parcel_id}/scenarios")
def dev_run(parcel_id: int, body: DevIn): return devscenarios.run(parcel_id, body.model_dump())
@r.get("/api/dev/{parcel_id}/latest")
def dev_latest(parcel_id: int): return devscenarios.latest(parcel_id) or {"status": "none"}
@r.get("/api/dev/runs/{run_id}")
def dev_get(run_id: int): return devscenarios.get_run(run_id)
@r.get("/api/property/{parcel_id}/services")
def svc_get(parcel_id: int): return services.get(parcel_id)
@r.put("/api/property/{parcel_id}/services")
def svc_put(parcel_id: int, body: dict): return services.put(parcel_id, body)
@r.get("/api/dev/{parcel_id}/report", response_class=PlainTextResponse)
def dev_report_md(parcel_id: int, run_id: int | None = None): return PlainTextResponse(devreport.build(parcel_id, run_id)["markdown"])
@r.get("/api/dev/{parcel_id}/report.pdf")
def dev_report_pdf(parcel_id: int, run_id: int | None = None): return Response(devreport.pdf(parcel_id, run_id), media_type="application/pdf")

# ---- resource consent pack (site panel button 3)
class RcIn(BaseModel): run_id: int | None = None
@r.post("/api/dev/{parcel_id}/rc-pack")
def rc_build(parcel_id: int, body: RcIn): return rcpack.build(parcel_id, body.run_id)
@r.get("/api/rc-packs/{pid}")
def rc_get(pid: int): return rcpack.get(pid)
class RcFieldsIn(BaseModel): fields: dict[str, str | None]
@r.put("/api/rc-packs/{pid}/fields")
def rc_fields(pid: int, body: RcFieldsIn): return rcpack.set_fields(pid, body.fields)
@r.get("/api/rc-packs/{pid}/documents/{key}.md", response_class=PlainTextResponse)
def rc_doc(pid: int, key: str): return PlainTextResponse(rcpack.render(pid, key))
@r.post("/api/rc-packs/{pid}/documents/{key}/upload")
async def rc_upload(pid: int, key: str, file: UploadFile = File(...)): return rcpack.add_upload(pid, key, file.filename or "upload.pdf", await file.read(cp.MAX_UPLOAD_BYTES + 1))
@r.post("/api/rc-packs/{pid}/ready-to-lodge")
def rc_ready(pid: int): return rcpack.mark_ready(pid)
@r.get("/api/rc-packs/{pid}/export.zip")
def rc_export(pid: int): return Response(rcpack.export_zip(pid), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="rc-pack-DRAFT-{pid}.zip"'})

# ---- map layers
@r.get("/api/layers")
def layers_kinds(): return layers.kinds()
@r.get("/api/layers/{kind}")
def layers_get(kind: str, bbox: str, name: str | None = None): return layers.get(kind, bbox, name)

# ---- Māori land
@r.get("/api/maori/gap")
def maori_gap(): return maori.tpk_gap()
@r.post("/api/maori/{parcel_id}")
def maori_get(parcel_id: int, body: dict | None = None): return maori.get(parcel_id, (body or {}).get("unit"))
class EntIn(BaseModel):
    name: str
    role: str | None = None
    source: str
@r.put("/api/maori/{parcel_id}/entity")
def maori_entity(parcel_id: int, body: EntIn): return maori.set_entity(parcel_id, body.name, body.role, body.source)
@r.get("/api/maori/{parcel_id}/outline", response_class=PlainTextResponse)
def maori_outline(parcel_id: int): return PlainTextResponse(maori.outline_md(parcel_id))

# ---- Best Use
class BestIn(BaseModel):
    newbuild: dict = Field(default_factory=dict)
    horizon_years: float | None = None
@r.post("/api/bestuse/{parcel_id}")
def best_use(parcel_id: int, body: BestIn): return bestuse.compare(parcel_id, body.newbuild, body.horizon_years)
class HzIn(BaseModel): reviewed: bool
@r.put("/api/bestuse/{parcel_id}/hazard-reviewed")
def best_hz(parcel_id: int, body: HzIn): return bestuse.set_hazard_reviewed(parcel_id, body.reviewed)

# ---- playbooks
@r.get("/api/playbooks")
def pb_list(): return playbooks.list_()
@r.get("/api/property/{parcel_id}/playbooks/match")
def pb_match(parcel_id: int): return playbooks.match(parcel_id)
class AptIn(BaseModel):
    units_total: int | None = None
    units_per_role: dict[str, int] = Field(default_factory=dict)
    owners: int | None = None
    single_party_controls: bool | None = None
@r.post("/api/property/{parcel_id}/playbooks/apartment")
def pb_apartment(parcel_id: int, body: AptIn): return playbooks.apartment(parcel_id, body.units_total, body.units_per_role, body.owners, body.single_party_controls)
@r.get("/api/property/{parcel_id}/playbooks/{name}/delta")
def pb_delta(parcel_id: int, name: str, option_id: int | None = None): return playbooks.delta(parcel_id, option_id, name)

# ---- bulk screening
class ScrIn(BaseModel):
    filters: dict = Field(default_factory=dict)
    sort: str = "profit_per_effort"
    desc: bool = True
    limit: int = 100
    offset: int = 0
@r.get("/api/screen/status")
def scr_status(): return screen.status()
@r.post("/api/screen/query")
def scr_query(body: ScrIn): return screenapi.query(body.filters, body.sort, body.desc, body.limit, body.offset)
class PtsIn(BaseModel):
    bbox: list[float]
    filters: dict = Field(default_factory=dict)
@r.post("/api/screen/points")
def scr_points(body: PtsIn):
    if len(body.bbox) != 4: raise HTTPException(422, "bbox needs 4 numbers")
    return screenapi.points(tuple(body.bbox), body.filters)
@r.get("/api/screen/suburbs")
def scr_suburbs(): return screenapi.suburbs()
@r.get("/api/screen/parcel/{parcel_id}")
def scr_parcel(parcel_id: int): return screenapi.explain_parcel(parcel_id)
class SlIn(BaseModel):
    name: str
    filters: dict
    weights: dict | None = None
    notes: str | None = None
@r.post("/api/shortlists")
def sl_add(body: SlIn): return screenapi.save_shortlist(body.name, body.filters, body.weights, body.notes)
@r.get("/api/shortlists")
def sl_list(): return screenapi.list_shortlists()
@r.post("/api/shortlists/{sid}/run")
def sl_run(sid: int): return screenapi.run_shortlist(sid)
@r.get("/api/shortlists/{sid}/audit")
def sl_audit(sid: int): return screenapi.audit(sid)
@r.get("/api/shortlists/{sid}/export")
def sl_export(sid: int, fmt: str = "csv"):
    rows = screenapi.run_shortlist(sid, 2000)["rows"]; b, mt, fn = screenapi.export(rows, fmt)
    return Response(b, media_type=mt, headers={"Content-Disposition": f'attachment; filename="{fn}"'})

# ---- portfolio
class PfIn(BaseModel):
    parcel_ids: list[int] = Field(default_factory=list)
    homes: list[dict] = Field(default_factory=list)
    overrides: dict = Field(default_factory=dict)
    homes_per_manager: float | None = None
    certification_cost_per_site: float | None = None
    cash_limit_dollars: float | None = None
    staff_positions_limit: float | None = None
    horizon_months: int = 36
@r.post("/api/portfolio")
def pf_run(body: PfIn):
    homes = body.homes or portfolio.homes_from_screen(body.parcel_ids)
    return portfolio.evaluate(homes, body.overrides, {k: v for k, v in body.model_dump().items() if k not in ("parcel_ids", "homes", "overrides") and v is not None})

# ---- CRM extras (gated), audit log
@r.get("/api/crm/leads")
def crm_list(rep: str | None = None, stage: str | None = None): return crm.leads(rep, stage)
@r.get("/api/crm/funnel/{dim}")
def crm_funnel_by(dim: str): return crm.funnel_by(dim)
@r.get("/api/crm/audit")
def crm_audit(): return audit.recent()

# ---- field capture (gated: /field and /api/field)
@r.get("/field", response_class=HTMLResponse)
def field_page(): return field.PAGE
@r.get("/field/manifest.json")
def field_manifest(): return field.MANIFEST
@r.get("/field/sw.js")
def field_sw(): return Response(field.SW, media_type="application/javascript")
from datetime import datetime as _dt
class CapIn(BaseModel):
    parcel_id: int
    rep_name: str
    permission_given_by: str = ""
    permission_note: str | None = None
    gps: dict | None = None
    captured_at: _dt | None = None
    values: dict = Field(default_factory=dict)
    rooms: list[dict] = Field(default_factory=list)
    photo_upload_ids: list[int] = Field(default_factory=list)
@r.post("/api/field/capture")
def field_capture(body: CapIn): return field.capture(body.parcel_id, body.rep_name, body.permission_given_by, body.permission_note, body.gps, body.captured_at, body.values, body.rooms, body.photo_upload_ids)
@r.get("/api/field/captures")
def field_list(status: str | None = None): return field.list_(status)
class RevIn2(BaseModel): accept: bool
@r.post("/api/field/captures/{cid}/review")
def field_review(cid: int, body: RevIn2): return field.review(cid, body.accept)
@r.post("/api/field/photo")
async def field_photo(parcel_id: int = Form(...), file: UploadFile = File(...)): return field.add_photo(parcel_id, file.filename or "photo.jpg", await file.read(cp.MAX_UPLOAD_BYTES + 1))

# ---- call sheets and route plans (gated)
class CsIn(BaseModel):
    parcel_ids: list[int]
    name: str = "Call sheet"
    start: list[float] | None = None
@r.post("/api/call-sheets")
def call_sheet(body: CsIn): return routeplan.build(body.parcel_ids, body.name, tuple(body.start) if body.start else None)
@r.post("/api/call-sheets/pdf")
def call_sheet_pdf(body: CsIn): return Response(routeplan.pdf(routeplan.build(body.parcel_ids, body.name, tuple(body.start) if body.start else None, save=False)["markdown"]), media_type="application/pdf")

# ---- offer generator (gated)
class OfIn(BaseModel):
    kind: str
    scenario_id: int
    mode: str
    lead_id: int | None = None
    sender: str | None = None
    rent_offered: float | None = None
    terms: dict = Field(default_factory=dict)
@r.post("/api/offer-letters")
def offer_make(body: OfIn): return offers.create(body.kind, body.scenario_id, body.mode, body.lead_id, body.sender, body.rent_offered, body.terms)
@r.get("/api/offer-letters")
def offer_versions(lead_id: int | None = None, scenario_id: int | None = None): return offers.versions(lead_id, scenario_id)
@r.get("/api/offer-letters/{did}")
def offer_get(did: int): return offers.get(did)
@r.post("/api/offer-letters/{did}/sent")
def offer_sent(did: int): return offers.mark_sent(did)
@r.get("/crm", response_class=HTMLResponse)
def crm_page(): return crm.PAGE

# ---- approval queue extras, tasks, next best action
class EditIn(BaseModel): draft_text: str
@r.put("/api/approvals/{aid}/draft")
def approvals_edit(aid: int, body: EditIn): return approvals.edit(aid, body.draft_text)
class TaskIn(BaseModel):
    title: str
    assignee: str | None = None
    due_on: date | None = None
    subject_type: str | None = None
    subject_id: int | None = None
@r.post("/api/tasks")
def task_add(body: TaskIn): return tasks.create(body.title, body.assignee, body.due_on, body.subject_type, body.subject_id)
@r.get("/api/tasks")
def task_list(assignee: str | None = None, status: str | None = "open"): return tasks.list_(assignee, status)
class TaskSt(BaseModel): status: str
@r.put("/api/tasks/{tid}")
def task_status(tid: int, body: TaskSt): return tasks.set_status(tid, body.status)
@r.get("/api/nba")
def nba_queue(limit: int = 50): return nba.queue(limit)
@r.get("/api/nba/probabilities")
def nba_probs(): return nba.probs()
class ProbIn(BaseModel): p: float | None = None
@r.put("/api/nba/probabilities/{stage}")
def nba_set(stage: str, body: ProbIn): return nba.set_prob(stage, body.p)
@r.get("/api/dashboard")
def dash(): return dashboard.build()
@r.post("/api/dashboard/weekly")
def dash_weekly(): return dashboard.weekly()

# ---- capture portal: owner side (login) and public side (token + flag)
class CapLinkIn(BaseModel):
    parcel_id: int
    days: int = 14
    retention_days: int = 90
@r.post("/api/capture-links")
def cap_link(body: CapLinkIn): return capture_portal.create_link(body.parcel_id, body.days, body.retention_days)
@r.get("/api/capture-links")
def cap_links(stall_days: int | None = None): return capture_portal.status_all(stall_days)
@r.post("/api/capture-links/{lid}/reminder")
def cap_reminder(lid: int): return capture_portal.draft_reminder(lid)
@r.post("/api/capture-links/purge")
def cap_purge(): return capture_portal.purge()
@r.get("/capture/{tok}", response_class=HTMLResponse)
def cap_page(tok: str):
    if not flags.enabled("capture_portal_links"): raise HTTPException(404, "not found")
    return capture_portal.PAGE
@r.get("/api/capture/{tok}")
def cap_view(tok: str): return capture_portal.view(tok)
class PermIn(BaseModel):
    by: str
    role: str
@r.post("/api/capture/{tok}/permission")
def cap_perm(tok: str, body: PermIn): return capture_portal.permission(tok, body.by, body.role)
class DetIn(BaseModel):
    rooms: list[dict] = Field(default_factory=list)
    door_width_min_m: float | None = None
    exits_count: int | None = None
@r.post("/api/capture/{tok}/details")
def cap_details(tok: str, body: DetIn): return capture_portal.details(tok, body.rooms, body.door_width_min_m, body.exits_count)
@r.post("/api/capture/{tok}/upload")
async def cap_upload(tok: str, file: UploadFile = File(...), label: str = Form(""), kind: str = Form("photo")): return capture_portal.upload(tok, label, file.filename or "upload", await file.read(cp.MAX_UPLOAD_BYTES + 1), kind)
@r.post("/api/capture/{tok}/submit")
def cap_submit(tok: str): return capture_portal.submit(tok)

# ---- batch engineering workflow
class EngIn(BaseModel):
    name: str
    company: str | None = None
    discipline: str
    fee_per_review: float | None = None
    target_turnaround_days: int | None = None
    review_window: str | None = None
@r.post("/api/engineers")
def eng_add(body: EngIn): return engineers.add(**body.model_dump())
@r.get("/api/engineers")
def eng_list(): return engineers.list_()
class AssignIn(BaseModel):
    package_ids: list[int]
    engineer_id: int
@r.post("/api/engineers/assign")
def eng_assign(body: AssignIn): return engineers.assign(body.package_ids, body.engineer_id)
@r.get("/api/engineers/queue")
def eng_queue(engineer_id: int | None = None): return engineers.queue(engineer_id)
@r.post("/api/engineers/escalate")
def eng_escalate(): return engineers.escalate_overdue()
@r.get("/api/engineers/scorecard")
def eng_scorecard(): return engineers.scorecard()
class TplIn(BaseModel):
    title: str
    body: str
    discipline: str | None = None
@r.post("/api/comment-templates")
def tpl_add(body: TplIn): return engineers.add_template(body.title, body.body, body.discipline)
@r.get("/api/comment-templates")
def tpl_list(discipline: str | None = None): return engineers.templates(discipline)

# ---- capacity planner
class CapPlanIn(BaseModel):
    parcel_ids: list[int] = Field(default_factory=list)
    homes: list[dict] = Field(default_factory=list)
    overrides: dict = Field(default_factory=dict)
    capacities: dict = Field(default_factory=dict)
    horizon_weeks: int = 156
    opening_target: str | None = None
@r.post("/api/capacity")
def cap_plan(body: CapPlanIn): return capacity.plan(body.homes or portfolio.homes_from_screen(body.parcel_ids), body.capacities, body.overrides, body.horizon_weeks, body.opening_target)
