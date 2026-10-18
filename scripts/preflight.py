#!/usr/bin/env python3
"""`make preflight`: checks what is needed to open the app on the iPhone. Prints names and OK/MISSING only, never values."""
import os, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
rows = []
def row(name, ok, note=""): rows.append((name, ok, note)); print(f"{'OK     ' if ok else 'MISSING'}  {name}" + (f"  ({note})" if note else ""))
pw = os.environ.get("APP_PASSWORD", ""); row("APP_PASSWORD set, 12+ characters", len(pw) >= 12, "16+ random characters recommended" if len(pw) < 16 else "")
row("TS_AUTHKEY set (Tailscale private access)", bool(os.environ.get("TS_AUTHKEY")))
row("BACKUP_PASSPHRASE set (encrypted backups)", bool(os.environ.get("BACKUP_PASSPHRASE")))
row("ANTHROPIC_API_KEY and ANTHROPIC_MODEL set (chat and plan vision)", bool(os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_MODEL")), "the rest of the app works without them")
row("tailscale installed", bool(shutil.which("tailscale")), "scripts/start_private.sh installs it")
try:
    import psycopg
    c = psycopg.connect(f"host=localhost dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}")
    n = c.execute("SELECT count(*) FROM core.sites").fetchone()[0]; d = c.execute("SELECT count(*) FROM core.user_listing WHERE source_id LIKE 'DEMO-%'").fetchone()[0]
    row("database up with parcels", n > 0, f"{n:,} parcels"); row("3 DEMO listings loaded", d == 3, "run: make demo-seed" if d != 3 else "")
except Exception as e: row("database up", False, "run: bash scripts/db_up.sh")
need = [r for r in rows[:2] if not r[1]]
print("\nTo open on the iPhone you need APP_PASSWORD and TS_AUTHKEY (docs/ACCESS.md)." if need else "\nReady: run `make app-private` and open the address it prints.")
