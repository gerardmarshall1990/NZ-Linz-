"""Part 7 step 2 tests: layout options against a ground-truth plan, drawings (stamp, scale), compliance statuses, briefs, evidence gaps,
no-signature / forbidden-words scan, hazard flags not read. Needs the local database with `make app-db` applied."""
import io, os, re
from pathlib import Path
import ezdxf
import pytest
from fastapi.testclient import TestClient

PARCEL = 4899224
SRC = Path(__file__).resolve().parent.parent / "backend" / "app"

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads2"))
    from backend.app.main import app
    from backend.app.db import conn
    def clean():
        with conn() as c:
            for t in ("rh_brief", "rh_check_run", "rh_layout_option", "rh_evidence_gap_status"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_edit WHERE extraction_id IN (SELECT x.id FROM core.rh_plan_extraction x JOIN core.rh_upload u ON u.id=x.upload_id WHERE u.parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_extraction WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            c.execute("DELETE FROM core.rh_plan_calibration WHERE upload_id IN (SELECT id FROM core.rh_upload WHERE parcel_id=%s)", (PARCEL,))
            for t in ("rh_upload", "rh_property_fact_history", "rh_property_fact", "rh_property"): c.execute(f"DELETE FROM core.{t} WHERE parcel_id=%s", (PARCEL,))
            c.commit()
    clean(); yield TestClient(app); clean()

def plan_dxf(with_laundry=True, extra_store=True) -> bytes:
    """4 bedrooms (B1,B2 have adjacent ensuites; B3 has an adjacent bathroom; B4 has nothing), corridor, lounge, kitchen, office, store (+ optional second store, laundry)."""
    d = ezdxf.new("R2010"); d.header["$INSUNITS"] = 6; d.layers.add("A-ROOM"); m = d.modelspace()
    def room(x, y, w, h, label):
        m.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": "A-ROOM"})
        m.add_text(label, dxfattribs={"layer": "A-ROOM", "insert": (x + 0.3, y + 0.3), "height": 0.2})
    for i in range(4): room(i * 4, 0, 4, 3, f"Bedroom {i + 1}")
    room(0, -1.5, 2, 1.5, "Ensuite 1"); room(4, -1.5, 2, 1.5, "Ensuite 2"); room(8, -1.5, 2, 1.5, "Bathroom A")
    room(0, 3, 16, 1.2, "Corridor")
    room(0, 4.2, 4, 4, "Lounge"); room(4, 4.2, 4, 4, "Kitchen"); room(8, 4.2, 4, 4, "Staff office"); room(12, 4.2, 4, 4, "Store")
    if with_laundry: room(16, 4.2, 4, 4, "Laundry")
    if extra_store: room(16, 0, 4, 3, "Store 2")
    s = io.StringIO(); d.write(s); return s.getvalue().encode()

def setup_property(client, **kw):
    assert client.post(f"/api/property/{PARCEL}").status_code == 200
    u = client.post(f"/api/property/{PARCEL}/uploads", files={"file": ("plan.dxf", plan_dxf(**kw))}).json()
    e = client.post(f"/api/uploads/{u['id']}/extract", json={"mode": "auto"}).json()
    types = {r["label"]: r["type"] for r in e["model"]["rooms"]}
    assert types["Bedroom 1"] == "bedroom" and types["Ensuite 1"] == "ensuite" and types["Bathroom A"] == "bathroom" and types["Store 2" if kw.get("extra_store", True) else "Store"] == "store"
    r = client.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE", "level_name": "Ground"}); assert r.status_code == 200, r.text
    return e

def test_layout_options_ground_truth(client):
    setup_property(client)
    opts = {o["scenario"]: o for o in client.post(f"/api/property/{PARCEL}/layouts").json()}
    assert opts["conservative"]["beds"] == 2                      # B1, B2 only
    assert opts["base"]["beds"] == 4                              # + B3 (bathroom converted) + B4 (new ensuite)
    assert opts["max"]["beds"] == 5                               # + Store 2 converted (first store is kept)
    assert opts["conservative"]["roles_missing"] == [] and not opts["conservative"]["sacrificed"]
    base_items = [i for lv in opts["base"]["levels"] for a in lv["rooms"] for i in a["items"]]
    assert sum("ensuite" in i for i in base_items) == 2
    assert opts["conservative"]["binding_constraint"].startswith("no ensuite") and "cost 2" in opts["conservative"]["binding_constraint"]
    assert opts["base"]["below_target"] is True and opts["base"]["target_beds"] == 50          # < 50 beds flagged
    assert "min_resident_room_m2" in opts["base"]["rules_not_applied"]                          # unsourced regulatory rules are named, not applied
    assert opts["base"]["occupancy_per_room"] == 1

def test_missing_role_sacrifices_a_resident_room(client):
    from backend.app import layout
    # same plan without a laundry: one resident room becomes the laundry
    setup = client.get(f"/api/property/{PARCEL}/layouts").json()
    assert setup   # options exist from the previous test
    from backend.app.model_view import confirmed_levels
    levels = confirmed_levels(PARCEL)
    assert any(r["type"] == "laundry" for r in levels[0]["rooms"])
    # simulate absence by filtering the model view
    import backend.app.layout as L
    orig = L.confirmed_levels
    L.confirmed_levels = lambda pid: [{**lv, "rooms": [r for r in lv["rooms"] if r["type"] != "laundry"]} for lv in orig(pid)]
    try: o = L.plan_option(PARCEL, "base")
    finally: L.confirmed_levels = orig
    assert o["roles_missing"] == ["laundry"] and o["sacrificed"][0]["role"] == "laundry" and o["beds"] == 3

def test_drawings_stamped_and_scaled(client):
    oid = client.get(f"/api/property/{PARCEL}/layouts").json()[1]["id"]
    r = client.get(f"/api/layouts/{oid}/drawing.dxf"); assert r.status_code == 200
    from backend.app.stamp import STAMP
    assert STAMP in r.text and "NEW_WORK" in r.text
    doc = ezdxf.read(io.StringIO(r.text)); assert doc.header["$INSUNITS"] == 6
    p = client.get(f"/api/layouts/{oid}/drawing.pdf"); assert p.status_code == 200 and p.content.startswith(b"%PDF")
    import pymupdf
    assert STAMP in pymupdf.open(stream=p.content, filetype="pdf")[0].get_text()
    assert client.get(f"/api/layouts/{oid}/drawing.dxf", params={"level": 5}).status_code == 404

def test_unscaled_level_gets_no_drawing(client):
    import pymupdf
    from backend.app.db import conn
    doc = pymupdf.open(); doc.new_page(width=842, height=595)
    u = client.post(f"/api/property/{PARCEL}/uploads", files={"file": ("p.pdf", doc.tobytes())}).json()
    e = client.post(f"/api/uploads/{u['id']}/extract", json={"mode": "manual"}).json()
    sq = [[100, 100], [300, 100], [300, 250], [100, 250]]
    e = client.patch(f"/api/extractions/{e['id']}", json={"ops": [{"op": "add_room", "label": "Bedroom X", "polygon": sq, "type": "bedroom"}]}).json()
    assert client.post(f"/api/extractions/{e['id']}/confirm", json={"evidence_level": "PLANS_ON_FILE"}).status_code == 200
    opts = client.post(f"/api/property/{PARCEL}/layouts").json()
    assert any(o["unscaled_levels"] for o in opts)
    o = opts[0]; idx = [i for i, lv in enumerate(o["levels"]) if not lv["calibrated"]][0]
    r = client.get(f"/api/layouts/{o['id']}/drawing.dxf", params={"level": idx}); assert r.status_code == 422 and "no scale" in r.text
    # restore the single-level state used by later tests: re-open and delete the extra extraction's effect
    with conn() as c:
        c.execute("UPDATE core.rh_plan_extraction SET superseded_by = id WHERE id = %s", (e["id"],)); c.commit()
    client.post(f"/api/property/{PARCEL}/layouts")

def test_compliance_statuses(client):
    oid = [o for o in client.get(f"/api/property/{PARCEL}/layouts").json() if o["scenario"] == "base"][0]["id"]
    r = client.post(f"/api/property/{PARCEL}/compliance", params={"option_id": oid}).json()
    by = {c["id"]: c for c in r["checks"]}
    assert by["corridor_width"]["status"] == "NEEDS_PROFESSIONAL" and "not loaded" in by["corridor_width"]["detail"]   # measured but no sourced requirement: never PASS
    assert by["ensuite_per_resident_room"]["status"] == "FAIL" and by["ensuite_per_resident_room"]["quantity"]["ensuites_to_add"] == 2
    assert by["sprinklers_alarm"]["status"] == "UNKNOWN"                      # nothing recorded: not assumed
    assert by["exits_and_escape"]["status"] == "NEEDS_PROFESSIONAL" and by["exits_and_escape"]["signs_off"]
    assert by["zone_activity"]["status"] in ("NEEDS_PROFESSIONAL", "UNKNOWN")
    assert r["counts"]["PASS"] == 0 or all(c["status"] != "PASS" or c["id"] in ("unit_title",) for c in r["checks"])
    # a sourced value flips corridor width to a real verdict
    from backend.app import bedrules
    reqs = bedrules.requirements(); old = [dict(x) for x in reqs]
    for x in reqs:
        if x["id"] == "corridor_width": x["value"] = 1.5
    try: r2 = client.post(f"/api/property/{PARCEL}/compliance", params={"option_id": oid}).json()
    finally:
        for x, o in zip(reqs, old): x.update(o)
    assert {c["id"]: c for c in r2["checks"]}["corridor_width"]["status"] == "FAIL"        # measured 1.2 < 1.5

def test_gaps_and_status(client):
    g = client.get(f"/api/property/{PARCEL}/gaps").json()
    keys = {x["key"] for x in g["gaps"]}
    assert {"wall_construction_fire_ratings", "structure_type", "asbestos", "service_capacity", "consented_plans_match"} <= keys
    assert all(x["status"] == "NEEDS_PROFESSIONAL" and x["confirmed_by"] for x in g["gaps"])
    g2 = client.put(f"/api/property/{PARCEL}/gaps/asbestos", json={"status": "REQUESTED", "note": "survey ordered"}).json()
    assert {x["key"]: x for x in g2["gaps"]}["asbestos"]["status"] == "REQUESTED" and g2["open"] == g["open"]
    assert client.put(f"/api/property/{PARCEL}/gaps/nonsense", json={"status": "RECEIVED"}).status_code == 404

FORBIDDEN = [r"\bPS[1-4]\s*(no|number|ref|#|:)\s*\d", r"\b(LBP|registration|licen[cs]e)\s*(no\.?|number|#)\s*[:#]?\s*\d", r"signed by", r"\bsignature\s*:", r"(?i)guarantee", r"(?i)will be approved", r"(?i)certified compliant", r"(?i)\bis compliant\b"]

def test_briefs_stamped_unsigned_and_clean(client):
    oid = [o for o in client.get(f"/api/property/{PARCEL}/layouts").json() if o["scenario"] == "base"][0]["id"]
    from backend.app.stamp import STAMP
    for kind in ("fire", "structural", "accessibility", "services"):
        b = client.post(f"/api/property/{PARCEL}/briefs", json={"option_id": oid, "kind": kind}).json()
        t = b["body_md"]
        assert t.startswith(f"**{STAMP}**") and "Questions for you" in t and "Upload slots" in t and "requested" in t
        for rx in FORBIDDEN: assert not re.search(rx, t), (kind, rx)
    assert len(client.get(f"/api/property/{PARCEL}/briefs").json()) == 4
    assert client.get("/api/briefs/999999").status_code == 404

def test_no_signature_code_paths_and_hazards_not_read():
    for f in SRC.glob("*.py"):
        src = f.read_text()
        assert not re.search(r"def\s+(\w*_)?(sign|signature|signed|producer_statement|registration)(_\w*)?\(", src, re.I), f.name
    for name in ("layout.py", "compliance.py", "briefs.py", "gaps.py", "model_view.py", "drawings.py"):
        src = (SRC / name).read_text()
        assert "hazard_flags" not in src and "flood" not in src.lower(), name       # decision 13: hazard data never feeds conversion results
    assert "hazard_flags" in (SRC / "facts.py").read_text()                        # shown on the record as information only
