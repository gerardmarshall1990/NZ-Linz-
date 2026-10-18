#!/usr/bin/env python3
"""`make screen`: build or refresh analytics.rh_screen for the whole database (incremental). Optional: SCREEN_BBOX=minE,minN,maxE,maxN. Long job: run in the background (make screen-bg)."""
import os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
from backend.app import screen
bb = tuple(float(x) for x in os.environ["SCREEN_BBOX"].split(",")) if os.environ.get("SCREEN_BBOX") else None
t = time.time(); r = screen.run(bb); print(r, f"{time.time() - t:.0f}s")
