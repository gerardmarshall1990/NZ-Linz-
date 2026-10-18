"""Self-serve capture portal (MASTER_SPEC 8.4): a mobile page per property reached by a secure expiring link, no account. The owner issues the link (needs an approval record) and passes it on; it works only while the capture_portal_links flag is ON
(default OFF) and is token-gated, expiring and revocable. The page records permission, shows the Capture Guide, accepts photos, scans and plans, checks completeness automatically (rooms vs expected bedrooms, door widths, exits, dark or blurry photos) and asks for
specific retakes. Only what is needed is kept, with a retention date; `purge` deletes expired submissions and files. Reminders are drafts that need an approval record."""
import hashlib, io, json, secrets
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import yaml
from fastapi import HTTPException
from . import approvals, audit, capture_guide, flags, uploads
from .config import ROOT, upload_dir
from .db import conn
from .facts import get_property

@lru_cache
def cfg() -> dict: return yaml.safe_load((ROOT / "config" / "capture_portal.yaml").read_text())
def _h(t): return hashlib.sha256(t.encode()).hexdigest()
ROOM_TYPES = ("bedroom", "ensuite", "bathroom", "kitchen", "laundry", "lounge", "dining", "office", "store", "other")

def create_link(parcel_id: int, days: int = 14, retention_days: int = 90) -> dict:
    get_property(parcel_id)
    if not (1 <= days <= 60 and 7 <= retention_days <= 365): raise HTTPException(422, "link days 1 to 60, retention 7 to 365 days")
    approvals.require("capture_link_issue", "parcel", parcel_id, f"Issue a self-serve capture link for parcel {parcel_id} (expires in {days} days, kept {retention_days} days)", "The link gives the owner or agent the Capture Guide and an upload page; it works only while the capture_portal_links flag is on.")
    tok = secrets.token_urlsafe(32)
    with conn() as c: cid = c.execute("INSERT INTO core.user_capture_link (parcel_id, token_hash, expires_at, retention_until) VALUES (%s,%s,%s,%s) RETURNING id", (parcel_id, _h(tok), datetime.now(timezone.utc) + timedelta(days=days), date.today() + timedelta(days=retention_days))).fetchone()["id"]; c.commit()
    on = flags.enabled("capture_portal_links")
    return {"id": cid, "link": f"/capture/{tok}" if on else None, "link_note": "Shown once. Send it yourself; the app sends nothing." if on else "The capture_portal_links flag is OFF: no working link was issued."}

def _link(tok: str) -> dict:
    if not flags.enabled("capture_portal_links"): raise HTTPException(404, "not found")
    with conn() as c: l = c.execute("SELECT * FROM core.user_capture_link WHERE token_hash=%s", (_h(tok),)).fetchone()
    if not l or l["status"] == "cancelled" or l["expires_at"] < datetime.now(timezone.utc): raise HTTPException(404, "not found")
    return l

def _save(lid: int, sub: dict, status: str | None = None):
    with conn() as c: c.execute("UPDATE core.user_capture_link SET submission=%s::jsonb, last_activity=now(), status=COALESCE(%s,status) WHERE id=%s", (json.dumps(sub), status, lid)); c.commit()

def expected(parcel_id: int) -> dict:
    with conn() as c:
        l = c.execute("SELECT max(bedrooms) AS b FROM core.user_listing WHERE parcel_id=%s AND status='active' AND bedrooms IS NOT NULL AND source_id NOT LIKE 'DEMO-%%'", (parcel_id,)).fetchone()["b"]
        f = c.execute("SELECT (value #>> '{}')::int AS b FROM core.rh_property_fact WHERE parcel_id=%s AND field='bedrooms_total'", (parcel_id,)).fetchone()
    return {"bedrooms": l if l is not None else (f["b"] if f else None), "source": "listing" if l is not None else ("Property Record" if f else None)}

def photo_quality(data: bytes) -> dict:
    """Heuristic: too dark / too small / blurry. Returns {ok, issues}."""
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(io.BytesIO(data)); w, h = im.size; g = im.convert("L"); g.thumbnail((800, 800)); a = np.asarray(g, dtype="float64")
    except Exception: return {"ok": False, "issues": ["unreadable image"]}
    issues = []; k = cfg()
    if w < k["min_photo_width_px"]: issues.append("too small: retake at a higher resolution")
    if a.mean() < k["photo_min_mean_brightness"]: issues.append("too dark: retake with the lights on")
    lap = a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    if lap.var() < k["photo_min_sharpness"]: issues.append("blurry: hold the phone steady and retake")
    return {"ok": not issues, "issues": issues}

def check(l: dict) -> dict:
    sub = l["submission"]; exp = expected(l["parcel_id"]); rooms = sub.get("rooms", []); photos = sub.get("photos", []); missing = []
    if not l["permission_by"]: missing.append("permission: who gave permission to capture")
    nb = sum(1 for r in rooms if r["type"] == "bedroom")
    if exp["bedrooms"] is not None and nb < exp["bedrooms"]: missing.append(f"bedrooms: {nb} listed, {exp['bedrooms']} expected from the {exp['source']}: add the missing {exp['bedrooms'] - nb}")
    if not rooms: missing.append("rooms: list each room")
    if sub.get("door_width_min_m") is None: missing.append("door width: the narrowest door clear width (m)")
    if sub.get("exits_count") is None: missing.append("exits: how many exits the building has")
    labelled = {p["label"] for p in photos if p["quality"]["ok"]}
    for r in rooms:
        if r["label"] not in labelled and not any(p["label"] == r["label"] for p in photos): missing.append(f"photos: a clear photo of {r['label']}")
    room_labels = {r["label"] for r in rooms}
    for lab in sorted({p["label"] for p in photos} & room_labels - labelled):
        last = [p for p in photos if p["label"] == lab][-1]; missing.append(f"retake {lab}: " + "; ".join(last["quality"]["issues"]))
    return {"complete": not missing, "missing": missing, "expected": exp}

def view(tok: str) -> dict:
    l = _link(tok); s = get_property_site(l["parcel_id"]); return {"address": s, "permission_recorded": bool(l["permission_by"]), "guide": capture_guide.build(l["parcel_id"])["markdown"], "submission": l["submission"], "check": check(l), "status": l["status"],
                                                                 "retention_until": l["retention_until"].isoformat(), "label": "We keep only what is needed, until the retention date. Nothing here states that the building complies with anything."}

def get_property_site(pid):
    with conn() as c: r = c.execute("SELECT address, suburb FROM core.sites WHERE parcel_id=%s", (pid,)).fetchone()
    return f"{r['address']}, {r['suburb']}" if r else str(pid)

def permission(tok: str, by: str, role: str) -> dict:
    l = _link(tok)
    if not (by or "").strip() or not (role or "").strip(): raise HTTPException(422, "your name and role (owner, agent or manager) are required")
    with conn() as c: c.execute("UPDATE core.user_capture_link SET permission_by=%s, permission_role=%s, permission_at=now(), last_activity=now() WHERE id=%s", (by.strip(), role.strip(), l["id"])); c.commit()
    return view(tok)

def details(tok: str, rooms: list[dict], door_width_min_m: float | None, exits_count: int | None) -> dict:
    l = _link(tok)
    if not l["permission_by"]: raise HTTPException(409, "record permission first")
    if any(r.get("type") not in ROOM_TYPES or not (r.get("label") or "").strip() for r in rooms): raise HTTPException(422, f"each room needs a label and a type from {list(ROOM_TYPES)}")
    if door_width_min_m is not None and not 0.3 <= door_width_min_m <= 3: raise HTTPException(422, "door width looks wrong: enter metres, for example 0.82")
    sub = {**l["submission"], "rooms": rooms, "door_width_min_m": door_width_min_m, "exits_count": exits_count}; _save(l["id"], sub); return view(tok)

def upload(tok: str, label: str, filename: str, data: bytes, kind: str = "photo") -> dict:
    l = _link(tok)
    if not l["permission_by"]: raise HTTPException(409, "record permission first")
    if kind not in ("photo", "plan", "scan"): raise HTTPException(422, "kind must be photo, plan or scan")
    t = uploads.detect_type(data, filename)
    if kind == "photo" and t not in ("jpg", "png"): raise HTTPException(415, "photos must be JPEG or PNG")
    s = uploads.store(l["parcel_id"], filename, data)
    with conn() as c:
        r = c.execute("""INSERT INTO core.rh_upload (parcel_id, kind, original_name, stored_name, detected_type, size_bytes, sha256, uploaded_by, source_note, page_count) VALUES (%s,%s,%s,%s,%s,%s,%s,'capture portal',%s,%s) RETURNING id""",
                      (l["parcel_id"], kind, uploads.safe_name(filename), s["stored_name"], s["detected_type"], s["size_bytes"], s["sha256"], f"capture portal ({l['permission_by']}): {label}", s["page_count"])).fetchone(); c.commit()
    sub = l["submission"]; q = photo_quality(data) if kind == "photo" else {"ok": True, "issues": []}
    sub.setdefault("photos", []).append({"label": (label or "").strip(), "upload_id": r["id"], "kind": kind, "quality": q}); _save(l["id"], sub); return view(tok)

def submit(tok: str) -> dict:
    l = _link(tok); chk = check(l)
    if not chk["complete"]: return {"submitted": False, **chk, "message": "Not complete yet: please add the items listed."}
    _save(l["id"], l["submission"], "complete"); audit.log("capture_portal_complete", "parcel", l["parcel_id"], {"link_id": l["id"]}); return {"submitted": True, **chk, "message": "Thank you: the submission is complete. It is reviewed before anything is treated as confirmed."}

def status_all(stall_days: int | None = None) -> list[dict]:
    with conn() as c: rows = c.execute("SELECT id, parcel_id, status, permission_by, last_activity, expires_at, retention_until FROM core.user_capture_link ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        stalled = bool(stall_days and r["status"] == "open" and r["last_activity"] and (datetime.now(timezone.utc) - r["last_activity"]).days >= stall_days)
        out.append({**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}, "stalled": stalled, "notification": "complete: review it" if r["status"] == "complete" else ("stalled: draft a reminder" if stalled else None)})
    return out

def draft_reminder(link_id: int) -> dict:
    with conn() as c: l = c.execute("SELECT * FROM core.user_capture_link WHERE id=%s", (link_id,)).fetchone()
    if not l: raise HTTPException(404, "no such link")
    miss = check(l)["missing"]
    text = "Hello,\n\nThank you for starting the property capture. A few items are still needed:\n" + "\n".join(f"- {m}" for m in miss[:10]) + "\n\nThere is no rush: the link stays open until it expires. If you would prefer not to continue, just reply and we will stop.\n"
    return approvals.request("owner_message", "capture_link", link_id, f"Reminder to the person capturing parcel {l['parcel_id']}", text)

def purge() -> dict:
    with conn() as c:
        rows = c.execute("SELECT id, parcel_id FROM core.user_capture_link WHERE retention_until < current_date").fetchall(); n_files = 0
        for r in rows:
            ids = [p["upload_id"] for p in (c.execute("SELECT submission FROM core.user_capture_link WHERE id=%s", (r["id"],)).fetchone()["submission"].get("photos") or [])]
            for u in c.execute("SELECT stored_name FROM core.rh_upload WHERE id = ANY(%s)", (ids,)).fetchall():
                f = upload_dir() / str(r["parcel_id"]) / u["stored_name"]
                if f.exists(): f.unlink(); n_files += 1
            c.execute("DELETE FROM core.rh_upload WHERE id = ANY(%s)", (ids,))
        c.execute("DELETE FROM core.user_capture_link WHERE retention_until < current_date"); c.commit()
    return {"links_purged": len(rows), "files_deleted": n_files}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Property capture</title>
<style>body{font:16px system-ui;margin:12px;max-width:640px}input,select,textarea{width:100%;box-sizing:border-box;padding:8px;margin:4px 0}button{padding:10px 14px;margin:6px 4px 0 0}.b{background:#fff3cd;padding:8px;border-radius:6px}.r{background:#fee;padding:8px;border-radius:6px}pre{white-space:pre-wrap}</style></head><body>
<h2>Property capture</h2><div id="a"></div><div id="x">Loading...</div>
<script>const tok=location.pathname.split('/').pop();const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(p,o){const r=await fetch('/api/capture/'+tok+p,o);if(!r.ok){let m='Not available';try{const j=await r.json();m=typeof j.detail==='string'?j.detail:m}catch(e){}throw new Error(m)}return r.json()}
const J=b=>({method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b)});
async function load(){try{const v=await api('');a.textContent=v.address;let h='';
 if(!v.permission_recorded)h+='<div class="b"><b>Permission first.</b> Please enter your name and your role (owner, agent or manager). Only continue if you are allowed to capture at this property.</div><input id="pb" placeholder="Your name"><input id="pr" placeholder="Role"><button onclick="perm()">I have permission</button>';
 else{h+='<details><summary>Capture guide</summary><pre>'+E(v.guide)+'</pre></details><h3>Rooms</h3><textarea id="rm" rows="5" placeholder="bedroom, Bedroom 1&#10;kitchen, Kitchen"></textarea><input id="dw" type="number" step="0.01" placeholder="Narrowest door width (m)"><input id="ex" type="number" placeholder="Number of exits"><button onclick="det()">Save rooms and measurements</button><h3>Photos and plans</h3><input id="lb" placeholder="Which room is this? (same label as above)"><input id="fi" type="file" accept="image/*,application/pdf" capture="environment"><button onclick="up()">Upload</button>'}
 h+='<h3>Still needed</h3>'+(v.check.missing.length?'<ul>'+v.check.missing.map(m=>'<li class="r">'+E(m)+'</li>').join('')+'</ul>':'<div class="b">Everything needed is in.</div>')+'<button onclick="sub()">Submit</button><div id="m"></div><div>'+E(v.label)+'</div>';x.innerHTML=h}catch(e){x.textContent='This link is not available.'}}
async function perm(){await api('/permission',J({by:pb.value,role:pr.value})).catch(e=>alert(e.message));load()}
async function det(){const rooms=rm.value.split('\\n').map(l=>l.split(',').map(s=>s.trim())).filter(a=>a[0]).map(a=>({type:a[0],label:a[1]||a[0]}));await api('/details',J({rooms,door_width_min_m:dw.value?+dw.value:null,exits_count:ex.value?+ex.value:null})).catch(e=>alert(e.message));load()}
async function up(){const f=fi.files[0];if(!f)return alert('Choose a file');const fd=new FormData();fd.append('file',f);fd.append('label',lb.value);fd.append('kind',f.type==='application/pdf'?'plan':'photo');const r=await fetch('/api/capture/'+tok+'/upload',{method:'POST',body:fd});if(!r.ok){alert('Upload failed')}load()}
async function sub(){const r=await api('/submit',{method:'POST'});m.textContent=r.message;load()}
load()</script></body></html>"""
