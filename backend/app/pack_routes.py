"""Routes for the consent pack, statements, engineer reviews and feature flags (Part 7 step 4). The only routes reachable without the owner's login are /review/{token} and /api/review/{token}, and only while the engineer_review_links flag is ON."""
from datetime import date
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from . import consent_pack as cp, flags, reviews
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
