"""Part 7 step 1 tests: DXF reader against a synthetic ground-truth plan, Property Record facts and history, upload validation,
calibration maths, the human-confirmation gate, and the vision-blocked path. Needs the local database (`make up`, `make core`, `make app-db`)."""
import io, os
import ezdxf
import pytest
from fastapi.testclient import TestClient

PARCEL = 4898114   # a real parcel with 4 buildings and 3 address points

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads"))
    os.environ.pop("ANTHROPIC_API_KEY", None); os.environ.pop("ANTHROPIC_MODEL", None)
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            for t in ("rh_plan_edit", "rh_plan_extraction", "rh_plan_calibration", "rh_upload", "rh_property_fact_history", "rh_property_fact", "rh_property"):
                if t in ("rh_plan_edit",): c.execute("DELETE FROM core.rh_plan_edit WHERE extraction_id IN (SELECT x.id FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id=%s)", (PARCEL,))
                elif t == "rh_plan_extraction": c.execute("DELETE FROM core.rh_plan_extraction WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
                elif t == "rh_plan_calibration": c.execute("DELETE FROM core.rh_plan_calibration WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
                else: c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.commit()
    clean(); yield TestClient(app); clean()

def make_dxf(units=6) -> bytes:
    d = ezdxf.new("R2010"); d.header["$INSUNITS"] = units; d.layers.add("A-ROOM"); d.layers.add("A-DOOR")
    m = d.modelspace()
    def room(x, y, w, h, label):
        m.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": "A-ROOM"})
        m.add_text(label, dxfattribs={"layer": "A-ROOM", "insert": (x + 0.5, y + 0.5), "height": 0.2})
    room(0, 0, 4, 3, "Bedroom 1"); room(4, 0, 4, 3, "Bedroom 2"); room(8, 0, 4, 3, "Bedroom 3 ensuite")
    room(0, 3, 12, 1.2, "Corridor"); room(0, 4.2, 4, 4, "Kitchen")
    blk = d.blocks.new("DOOR900"); blk.add_line((0, 0), (0.9, 0))
    i = m.add_blockref("DOOR900", (2, 0), dxfattribs={"layer": "A-DOOR"}); i.add_attrib("WIDTH", "0.9", (2, 0))
    s = io.StringIO(); d.write(s); return s.getvalue().encode()

def mk_prop(client): assert client.post(f"/api/property/{PARCEL}").status_code == 200

def test_health_and_site(client):
    assert client.get("/api/health").json()["sites"] > 500000
    assert client.get(f"/api/sites/{PARCEL}").json()["parcel_id"] == PARCEL
    assert client.get("/api/sites/1").status_code == 404

def test_dxf_ground_truth():
    from backend.app.dxf_reader import parse_dxf
    m = parse_dxf(make_dxf())
    by = {r["label"]: r for r in m["rooms"]}
    assert len(m["rooms"]) == 5
    assert by["Bedroom 1"]["area_m2"] == 12.0 and by["Bedroom 1"]["type"] == "bedroom"
    assert by["Bedroom 3 ensuite"]["type"] == "ensuite"       # first matching rule wins: ensuite label is flagged, not silently a bedroom
    assert by["Kitchen"]["area_m2"] == 16.0 and by["Kitchen"]["type"] == "kitchen"
    assert m["corridors"][0]["min_width_m"] == 1.2
    assert m["doors"][0]["width_m"] == 0.9
    assert m["calibrated"] is True

def test_dxf_millimetres_scale():
    from backend.app.dxf_reader import parse_dxf
    d = ezdxf.new("R2010"); d.header["$INSUNITS"] = 4; d.layers.add("ROOM"); m = d.modelspace()
    m.add_lwpolyline([(0, 0), (4000, 0), (4000, 3000), (0, 3000)], close=True, dxfattribs={"layer": "ROOM"}); m.add_text("Bedroom", dxfattribs={"layer": "ROOM", "insert": (500, 500)})
    s = io.StringIO(); d.write(s)
    assert parse_dxf(s.getvalue().encode())["rooms"][0]["area_m2"] == 12.0

def test_unitless_dxf_has_no_measurements():
    from backend.app.dxf_reader import parse_dxf
    m = parse_dxf(make_dxf(units=0))
    assert m["unscaled"] and all(r["area_m2"] is None for r in m["rooms"]) and not m["corridors"] and m["warnings"]
    assert parse_dxf(make_dxf(units=0), "m")["rooms"][0]["area_m2"] is not None   # declared units fix it

def test_calibration_maths():
    from backend.app.calibration import two_point, stated_scale
    c = two_point([{"a": [0, 0], "b": [100, 0], "metres": 5.0}, {"a": [0, 0], "b": [0, 200], "metres": 10.0}])
    assert abs(c["metres_per_unit"] - 0.05) < 1e-9 and c["residual_m"] < 1e-9
    c2 = two_point([{"a": [0, 0], "b": [100, 0], "metres": 5.0}, {"a": [0, 0], "b": [0, 100], "metres": 6.0}])
    assert c2["residual_m"] > 0.4                              # disagreement is visible, not hidden
    s = stated_scale(100, True)                                # 1:100 at 100 dpi: 1 px = 0.254 mm paper = 0.0254 m
    assert abs(s["metres_per_unit"] - 0.0254) < 1e-9
    with pytest.raises(Exception): stated_scale(100, False)

def test_estimates_and_fact_history(client):
    r = client.post(f"/api/property/{PARCEL}").json()
    f = {x["field"]: x for x in r["facts"]} if isinstance(r["facts"], list) else r["facts"]
    assert f["building_count"]["confidence"] == "ESTIMATED"
    assert "storeys_per_building" not in f                      # never guessed
    assert f["bedrooms_total"]["confidence"] == "ESTIMATED" and "NOT a bedroom count" in (f["bedrooms_total"].get("note") or "")
    body = {"field": "bedrooms_total", "value": 22, "source": "listing text", "confidence": "DOCUMENTED"}
    assert client.put(f"/api/property/{PARCEL}/facts", json=body).status_code == 200
    body["value"] = 24; body["source"] = "owner phone call"
    client.put(f"/api/property/{PARCEL}/facts", json=body)
    h = client.get(f"/api/property/{PARCEL}/history", params={"field": "bedrooms_total"}).json()
    assert len(h) >= 3 and h[0]["new_value"] in (24, "24")
    assert client.put(f"/api/property/{PARCEL}/facts", json={**body, "field": "nope"}).status_code == 422
    assert client.put(f"/api/property/{PARCEL}/facts", json={**body, "field": "sprinklers", "value": "banana"}).status_code == 422

def test_csv_roundtrip_dry_run(client):
    csv = client.get(f"/api/property/{PARCEL}/export.csv").text
    assert "bedrooms_total" in csv
    r = client.post(f"/api/property/{PARCEL}/import", data={"source": "test", "dry_run": "true"}, files={"file": ("p.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200

def test_upload_validation(client):
    mk_prop(client)
    up = lambda name, data: client.post(f"/api/property/{PARCEL}/uploads", files={"file": (name, data)})
    assert up("evil.pdf", b"MZ\x90\x00 not a pdf").status_code == 415      # extension lies, bytes decide
    assert up("empty.pdf", b"").status_code == 422
    assert up("../../etc/passwd.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50).status_code == 200   # stored under a sanitised name
    r = up("scan.obj", b"v 0 0 0\n"); assert r.status_code == 200 and r.json()["detected_type"] == "scan_reference"
    from backend.app.uploads import safe_name
    assert safe_name("../../a b/c;d.pdf") == "c_d.pdf"
    from backend.app import uploads
    old = uploads.MAX_UPLOAD_BYTES; uploads.MAX_UPLOAD_BYTES = 10
    try: assert up("big.pdf", b"%PDF-1.4" + b"0" * 100).status_code == 413
    finally: uploads.MAX_UPLOAD_BYTES = old

def test_dxf_confirm_flow_and_confidence(client):
    mk_prop(client)
    u = client.post(f"/api/property/{PARCEL}/uploads", files={"file": ("plan.dxf", make_dxf())}).json()
    assert u["detected_type"] == "dxf"
    e = client.post(f"/api/uploads/{u['id']}/extract", json={"mode": "auto"}).json()
    assert e["status"] == "extracted" and e["calibrated"]
    # extraction alone writes nothing at CONFIRMED
    facts = client.get(f"/api/property/{PARCEL}").json()["facts"]
    f = {x["field"]: x for x in facts} if isinstance(facts, list) else facts
    assert f["bedrooms_total"]["confidence"] != "CONFIRMED"
    assert client.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "bogus"}).status_code == 422
    # an unknown room type blocks confirmation
    rooms = e["model"]["rooms"]
    client.patch(f"/api/extractions/{e['id']}", json={"ops": [{"op": "set_room", "id": rooms[0]["id"], "type": "unknown"}]})
    assert client.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE"}).status_code == 422
    client.patch(f"/api/extractions/{e['id']}", json={"ops": [{"op": "set_room", "id": rooms[0]["id"], "type": "bedroom"}]})
    r = client.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE", "level_name": "Ground"})
    assert r.status_code == 200, r.text
    f = {x["field"]: x for x in client.get(f"/api/property/{PARCEL}").json()["facts"]} if isinstance(client.get(f"/api/property/{PARCEL}").json()["facts"], list) else client.get(f"/api/property/{PARCEL}").json()["facts"]
    assert f["kitchens"]["value"] == 1 and f["kitchens"]["confidence"] == "CONFIRMED"
    assert f["corridor_width_min_m"]["value"] == 1.2 and f["door_width_min_m"]["value"] == 0.9
    assert client.patch(f"/api/extractions/{e['id']}", json={"ops": []}).status_code == 409   # confirmed is read-only
    n = client.post(f"/api/extractions/{e['id']}/reopen").json()
    assert n["status"] == "extracted" and n["id"] != e["id"]

def test_manual_pdf_needs_calibration_and_vision_blocked(client):
    import pymupdf
    mk_prop(client)
    doc = pymupdf.open(); doc.new_page(width=842, height=595); pdf = doc.tobytes()
    u = client.post(f"/api/property/{PARCEL}/uploads", files={"file": ("plan.pdf", pdf)}).json()
    assert u["page_count"] == 1
    assert client.post(f"/api/uploads/{u['id']}/extract", json={"mode": "vision"}).status_code == 503
    e = client.post(f"/api/uploads/{u['id']}/extract", json={"mode": "manual"}).json()
    assert e["calibrated"] is False and e["source"] == "manual"
    sq = [[100, 100], [300, 100], [300, 250], [100, 250]]
    e = client.patch(f"/api/extractions/{e['id']}", json={"ops": [{"op": "add_room", "label": "Bedroom 1", "polygon": sq}]}).json()
    assert e["model"]["rooms"][0]["area_m2"] is None             # no scale, no area
    c = client.post(f"/api/uploads/{u['id']}/calibrate", json={"method": "two_point", "measurements": [{"a": [100, 100], "b": [300, 100], "metres": 4.0}]}).json()
    assert abs(c["metres_per_unit"] - 0.02) < 1e-9
    e = client.get(f"/api/extractions/{e['id']}").json()
    assert e["model"]["rooms"][0]["area_m2"] == 12.0              # 4 m x 3 m after calibration
