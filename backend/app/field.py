"""Field capture (MASTER_SPEC Part 4 section 4.3; behind the field_capture_enabled flag). Guided capture for the owner or a rep, ONLY with the owner's or agent's permission: a capture without a named person who gave permission is refused, and a parcel on the
do-not-contact list is refused. Values are written to the Property Record as DOCUMENTED with the rep, the permission and the capture id as the source; the owner reviews, and only then they become CONFIRMED. Photos are stored as uploads (kind photo)."""
from datetime import datetime
import json
from fastapi import HTTPException
from . import audit, crm, uploads
from .db import conn
from .facts import get_property, set_fact
from .plan_request import SITE_VISIT

ALLOWED = {f for f, _ in SITE_VISIT}
ROOM_TYPES = ("bedroom", "ensuite", "bathroom", "kitchen", "laundry", "lounge", "dining", "office", "store", "other")

def _ensure_record(parcel_id: int):
    with conn() as c:
        if not c.execute("SELECT 1 FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone(): raise HTTPException(404, "no such parcel")
        c.execute("INSERT INTO core.rh_property (parcel_id, created_by) VALUES (%s,'field capture') ON CONFLICT DO NOTHING", (parcel_id,)); c.commit()

def derive(values: dict, rooms: list[dict]) -> dict:
    out = {k: v for k, v in values.items() if v not in (None, "")}
    bad = [k for k in out if k not in ALLOWED]
    if bad: raise HTTPException(422, f"not on the capture form: {bad}")
    if rooms:
        if any(r.get("type") not in ROOM_TYPES for r in rooms): raise HTTPException(422, f"room type must be one of {list(ROOM_TYPES)}")
        cnt = lambda t: sum(1 for r in rooms if r["type"] == t)
        out.setdefault("bedrooms_total", cnt("bedroom")); out.setdefault("kitchens", cnt("kitchen")); out.setdefault("laundries", cnt("laundry")); out.setdefault("rooms_with_ensuite", cnt("ensuite")); out.setdefault("shared_bathrooms", cnt("bathroom"))
    return out

def capture(parcel_id: int, rep_name: str, permission_given_by: str, permission_note: str | None, gps: dict | None, captured_at: datetime | None, values: dict, rooms: list[dict], photo_upload_ids: list[int] | None = None) -> dict:
    if not (rep_name or "").strip(): raise HTTPException(422, "rep name required")
    if not (permission_given_by or "").strip():
        audit.log("capture_refused", "parcel", parcel_id, {"why": "no permission recorded"}); raise HTTPException(422, "permission first: name the owner or agent who gave permission to capture at this property")
    if crm.on_do_not_contact({"parcel_id": parcel_id}): audit.log("capture_refused", "parcel", parcel_id, {"why": "do-not-contact"}); raise HTTPException(409, "do-not-contact: capture refused")
    facts = derive(values, rooms); _ensure_record(parcel_id)
    with conn() as c:
        r = c.execute("""INSERT INTO core.user_field_capture (parcel_id, rep_name, permission_given_by, permission_note, gps, captured_at, payload, photo_upload_ids) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s) RETURNING id""",
                      (parcel_id, rep_name.strip(), permission_given_by.strip(), permission_note, json.dumps(gps) if gps else None, captured_at or datetime.now(), json.dumps({"facts": facts, "rooms": rooms}), photo_upload_ids or [])).fetchone()
        for k, v in facts.items(): set_fact(c, parcel_id, k, v, f"field capture {r['id']} by {rep_name.strip()} (permission: {permission_given_by.strip()})", "DOCUMENTED", "field capture")
        c.commit()
    audit.log("capture", "parcel", parcel_id, {"capture_id": r["id"], "rep": rep_name})
    return get(r["id"])

def get(cid: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.user_field_capture WHERE id=%s", (cid,)).fetchone()
    if not r: raise HTTPException(404, "no such capture")
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}

def list_(status: str | None = None) -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.user_field_capture" + (" WHERE status=%s" if status else "") + " ORDER BY id DESC LIMIT 200", (status,) if status else ()).fetchall()]
    return [get(i) for i in ids]

def review(cid: int, accept: bool) -> dict:
    cap = get(cid)
    if cap["status"] != "pending_review": raise HTTPException(409, f"capture is {cap['status']}")
    with conn() as c:
        if accept:
            for k, v in cap["payload"]["facts"].items(): set_fact(c, cap["parcel_id"], k, v, f"field capture {cid} by {cap['rep_name']}, reviewed by owner", "CONFIRMED", "field capture reviewed")
        c.execute("UPDATE core.user_field_capture SET status=%s, reviewed_at=now() WHERE id=%s", ("confirmed" if accept else "rejected", cid)); c.commit()
    audit.log("capture_review", "capture", cid, {"accepted": accept}); return get(cid)

def add_photo(parcel_id: int, filename: str, data: bytes) -> dict:
    if uploads.detect_type(data, filename) not in ("jpg", "png"): raise HTTPException(415, "photos must be JPEG or PNG")
    _ensure_record(parcel_id); s = uploads.store(parcel_id, filename, data)
    with conn() as c:
        r = c.execute("""INSERT INTO core.rh_upload (parcel_id, kind, original_name, stored_name, detected_type, size_bytes, sha256, uploaded_by, source_note, page_count) VALUES (%s,'photo',%s,%s,%s,%s,%s,'field capture','field capture photo',NULL) RETURNING id""",
                      (parcel_id, uploads.safe_name(filename), s["stored_name"], s["detected_type"], s["size_bytes"], s["sha256"])).fetchone(); c.commit()
    return {"upload_id": r["id"]}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="manifest" href="/field/manifest.json"><title>Field capture</title>
<style>body{font:16px system-ui;margin:12px;max-width:640px}label{display:block;margin-top:8px;font-weight:600}input,select,textarea{width:100%;box-sizing:border-box;padding:8px;margin-top:2px}button{padding:10px 14px;margin:8px 4px 0 0}.b{background:#fee;border:1px solid #c00;padding:8px;border-radius:6px}.ok{background:#efe;padding:6px}</style></head><body>
<h2>Field capture</h2><div class="b"><b>Permission first.</b> Capture only with the owner's or agent's permission. Record who gave it. Do not enter any part of a property without it, and do not contact tenants.</div>
<label>Parcel ID</label><input id="p" type="number"><label>Your name</label><input id="r"><label>Who gave permission (name and role)</label><input id="pg"><label>Permission note</label><input id="pn">
<label>Corridor narrowest (m)</label><input id="corridor_width_min_m" type="number" step="0.01"><label>Door narrowest (m)</label><input id="door_width_min_m" type="number" step="0.01">
<label>Rooms (one per line: type, label, approx m2; types: bedroom ensuite bathroom kitchen laundry lounge dining office store other)</label><textarea id="rooms" rows="5" placeholder="bedroom, Bed 1, 12"></textarea>
<label>Sprinklers</label><select id="sprinklers"><option value="">not checked</option><option>none</option><option>partial</option><option>full</option></select><label>Fire alarm</label><select id="fire_alarm"><option value="">not checked</option><option>none</option><option>detection</option><option>full</option></select>
<label>Stairs</label><input id="stairs_count" type="number"><label>Photos</label><input id="ph" type="file" accept="image/*" multiple capture="environment">
<button onclick="save()">Save capture</button><div id="m"></div><div id="q"></div>
<script>const Q=()=>{try{return JSON.parse(localStorage.getItem('fq')||'[]')}catch(e){return[]}};const setQ=x=>localStorage.setItem('fq',JSON.stringify(x));
function gps(){return new Promise(r=>navigator.geolocation?navigator.geolocation.getCurrentPosition(p=>r({lat:p.coords.latitude,lon:p.coords.longitude,accuracy:p.coords.accuracy}),()=>r(null),{timeout:4000}):r(null))}
async function save(){const v={};['corridor_width_min_m','door_width_min_m','stairs_count'].forEach(k=>{const e=document.getElementById(k).value;if(e!=='')v[k]=+e});['sprinklers','fire_alarm'].forEach(k=>{const e=document.getElementById(k).value;if(e)v[k]=e});
 const rooms=document.getElementById('rooms').value.split('\\n').map(l=>l.split(',').map(x=>x.trim())).filter(a=>a[0]).map(a=>({type:a[0],label:a[1]||'',approx_m2:a[2]?+a[2]:null}));
 const body={parcel_id:+p.value,rep_name:r.value,permission_given_by:pg.value,permission_note:pn.value,gps:await gps(),captured_at:new Date().toISOString(),values:v,rooms};
 try{const x=await fetch('/api/field/capture',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});if(!x.ok){const j=await x.json();m.innerHTML='<div class="b">'+(typeof j.detail==='string'?j.detail:JSON.stringify(j.detail))+'</div>';return}const j=await x.json();m.innerHTML='<div class="ok">Saved as DOCUMENTED (capture '+j.id+'). The owner reviews it before it counts as confirmed.</div>'}
 catch(e){const q=Q();q.push(body);setQ(q);m.innerHTML='<div class="ok">Offline: saved on this phone, will send when online ('+q.length+' waiting).</div>'}}
async function flush(){const q=Q();if(!q.length)return;const rest=[];for(const b of q){try{const x=await fetch('/api/field/capture',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b)});if(!x.ok)rest.push(b)}catch(e){rest.push(b)}}setQ(rest)}
window.addEventListener('online',flush);flush();if('serviceWorker' in navigator)navigator.serviceWorker.register('/field/sw.js');</script></body></html>"""
MANIFEST = {"name": "Field capture", "short_name": "Capture", "start_url": "/field", "display": "standalone", "background_color": "#ffffff", "theme_color": "#0b5cab", "icons": []}
SW = "self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{const c=r.clone();caches.open('f1').then(k=>k.put(e.request,c));return r}).catch(()=>caches.match(e.request)))});"
