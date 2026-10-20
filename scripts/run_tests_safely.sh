#!/usr/bin/env bash
# Full test suite, protecting your saved inputs and the demo listings (the suite clears them). Exit code = the test result.
cd "$(dirname "$0")/.."
G=$(mktemp); python3 scripts/test_state_guard.py save "$G" || { echo "could not snapshot saved inputs: not running the tests"; exit 2; }
# warm the database cache first: right after a restart the heavy queries are slow enough to hit the tests'/app's statement timeout (the only cause of failures seen so far)
python3 - <<'PY'
import os
from pathlib import Path
for l in Path(".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
from backend.app.db import conn
with conn() as c:
    for r in c.execute("select schemaname s, relname t from pg_stat_user_tables where schemaname in ('core','analytics') order by pg_total_relation_size(relid) desc limit 12").fetchall():
        try: c.execute(f'select count(*) from "{r["s"]}"."{r["t"]}"').fetchone()
        except Exception: c.rollback()
print("database cache warmed")
PY
LOG=${TMPDIR:-/tmp}/nzlinz_last_test_run.log; python3 -m pytest -q -p no:cacheprovider 2>&1 | tee "$LOG"; rc=${PIPESTATUS[0]}
[ $rc -ne 0 ] && { echo '--- failing tests ---'; grep -E '^(FAILED|ERROR)' "$LOG"; grep -E 'statement timeout|Connection refused' "$LOG" | sort | uniq -c | head -3; }
python3 scripts/test_state_guard.py restore "$G"; rm -f "$G"; exit $rc
