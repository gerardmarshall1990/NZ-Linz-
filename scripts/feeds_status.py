#!/usr/bin/env python3
"""Print the feeds register: status, last refresh, live row counts, what is blocked. `make feeds-status`."""
import os, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1); os.environ.setdefault(k, v)
E = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
def sql(q): return subprocess.run(["psql", "-h", "localhost", "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-At", "-F", "\x1f", "-c", q], env=E, capture_output=True, text=True)
rows = [l.split("\x1f") for l in sql("SELECT feed, status, coalesce(last_refresh::text,'-'), coalesce(count_sql,''), coalesce(blocked_reason,''), coalesce(next_action,''), cost_licence FROM core.feeds ORDER BY id").stdout.splitlines()]
print(f"{'STATUS':16} {'LAST':10} {'ROWS':>10}  FEED")
for feed, status, last, csql, why, nxt, lic in rows:
    n = "-"
    if csql:
        r = sql(csql); n = f"{int(r.stdout.strip() or 0):,}" if r.returncode == 0 and r.stdout.strip().isdigit() else "n/a"
    print(f"{status:16} {last:10} {n:>10}  {feed}")
    if status != "live" or why:
        print(f"{'':16} {'':10} {'':>10}    licence: {lic}" + (f" | blocked: {why}" if why else "") + (f" | next: {nxt}" if nxt else ""))
