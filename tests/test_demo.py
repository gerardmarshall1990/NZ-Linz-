"""Demo listings: loaded labelled DEMO, removable, never touch saved inputs."""
import subprocess, sys
from pathlib import Path
from backend.app.db import conn
ROOT = Path(__file__).resolve().parent.parent
def run(*a): return subprocess.run([sys.executable, "scripts/demo_seed.py", *a], cwd=ROOT, capture_output=True, text=True)
def test_demo_seed_and_clear():
    with conn() as c: before = c.execute("SELECT count(*) AS n FROM core.user_setting").fetchone()["n"]
    r = run(); assert r.returncode == 0 and "DEMO listings loaded" in r.stdout
    with conn() as c:
        n = c.execute("SELECT count(*) AS n FROM core.user_listing WHERE source_id LIKE 'DEMO-%'").fetchone()["n"]; assert n == 3
        assert c.execute("SELECT count(*) AS n FROM core.user_setting").fetchone()["n"] == before
    assert "removed 3" in run("--clear").stdout
    with conn() as c: assert c.execute("SELECT count(*) AS n FROM core.user_listing WHERE source_id LIKE 'DEMO-%'").fetchone()["n"] == 0
def test_app_html_badges_demo_listings():
    assert "DEMO listing:" in (ROOT / "backend/app/static/app.html").read_text()
