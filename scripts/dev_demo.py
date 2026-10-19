#!/usr/bin/env python3
"""Runs the development-site flow (buttons 1 to 3) for chosen parcels and writes the full JSON of each step to an output folder. Usage: python3 scripts/dev_demo.py <out_dir> <parcel_id:typology> ...
Unit sizes are an ILLUSTRATION (flagged); finance inputs are left blank."""
import json, os, sys
from pathlib import Path
env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
for k, v in env.items(): os.environ.setdefault(k, v)
from fastapi.testclient import TestClient
from backend.app.main import app
UNIT = {"houses": {"width_m": 7, "depth_m": 10, "height_m": 7.5, "wall_height_m": 5.5, "gfa_m2": 110, "bedrooms": 3}, "terraces": {"width_m": 5.5, "depth_m": 11, "height_m": 10.5, "wall_height_m": 8.5, "gfa_m2": 130, "bedrooms": 3}}
c = TestClient(app); r = c.post("/login", json={"password": os.environ["APP_PASSWORD"]}); assert r.status_code in (200, 204, 303), r.status_code
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for a in sys.argv[2:]:
    pid, typ = a.split(":"); d = out / pid; d.mkdir(exist_ok=True)
    body = {"typology": typ, "unit": UNIT[typ], "access_width_m": 3.5, "finance": {}}
    r1 = c.post(f"/api/dev/{pid}/scenarios", json=body); (d / "button1.json").write_text(json.dumps(r1.json(), indent=1, default=str)); print(pid, "b1", r1.status_code)
    r2 = c.get(f"/api/dev/{pid}/report.pdf"); (d / "button2.pdf").write_bytes(r2.content); print(pid, "b2", r2.status_code, len(r2.content))
    r2t = c.get(f"/api/dev/{pid}/report"); (d / "button2.txt").write_text(r2t.text)
    r3 = c.post(f"/api/dev/{pid}/rc-pack", json={}); (d / "button3.json").write_text(json.dumps(r3.json(), indent=1, default=str)); print(pid, "b3", r3.status_code)
    if r3.status_code == 200:
        z = c.get(f"/api/rc-packs/{r3.json()['id']}/export.zip"); (d / "pack.zip").write_bytes(z.content); print(pid, "zip", z.status_code, len(z.content))
