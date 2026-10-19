#!/usr/bin/env python3
"""Saves and restores the owner's saved inputs (core.user_setting) and notes whether the demo listings existed, because the full test suite clears them.
Usage: test_state_guard.py save <file> | restore <file>   (restore also re-seeds the demo listings if they existed before)"""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
sys.path.insert(0, str(ROOT))
from backend.app.db import conn

def main(cmd, f):
    if cmd == "save":
        with conn() as c:
            rows = c.execute("SELECT key, value FROM core.user_setting").fetchall()
            demo = c.execute("SELECT count(*) n FROM core.user_listing").fetchone()["n"]
        Path(f).write_text(json.dumps({"settings": [{"key": r["key"], "value": r["value"]} for r in rows], "listings": demo})); print(f"saved {len(rows)} settings, {demo} listings")
    else:
        d = json.loads(Path(f).read_text())
        with conn() as c:
            for r in d["settings"]: c.execute("INSERT INTO core.user_setting (key,value,updated_by) VALUES (%s,%s::jsonb,'owner') ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (r["key"], json.dumps(r["value"])))
            c.commit(); n = c.execute("SELECT count(*) n FROM core.user_setting").fetchone()["n"]
        print(f"restored {len(d['settings'])} settings (now {n})")
        if d["listings"]: subprocess.run(["make", "-C", str(ROOT), "demo-seed"], check=False, capture_output=True); print("demo listings re-seeded")

if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
