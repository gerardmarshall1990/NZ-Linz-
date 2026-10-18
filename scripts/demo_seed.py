#!/usr/bin/env python3
"""Load or remove 3 DEMO listings (real Auckland addresses, INVENTED rent and bedrooms) for testing the app on a phone. They are labelled DEMO (source_id DEMO-n) and the app shows a DEMO badge.
Never touches your saved inputs. Usage: demo_seed.py [--clear]"""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
from backend.app.db import conn
from backend.app import listings
SAMPLE = """source_id,address,suburb,rent_per_week,bedrooms,bathrooms,listing_type,url
DEMO-1,80 Hinemoa Street,Birkenhead,4800,30,12,rent,
DEMO-2,282 Lincoln Road,Henderson,3900,24,10,rent,
DEMO-3,14 Shipherds Avenue,Epsom,1950,7,3,rent,
"""
if "--clear" in sys.argv:
    with conn() as c: n = c.execute("DELETE FROM core.user_listing WHERE source_id LIKE 'DEMO-%'").rowcount; c.commit()
    print(f"removed {n} DEMO listing(s)"); sys.exit(0)
r = listings.import_csv(SAMPLE, "csv_manual", dry_run=False)
print(f"DEMO listings loaded: new {r['new']}; matched {r['matched']}. They are invented (rent and bedrooms) and badged DEMO. Remove with: make demo-clear")
