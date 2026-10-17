"""Browser smoke test of the map app (headless Chromium via the node Playwright tools, phone width). Skipped when those tools are not installed."""
import os, shutil, socket, subprocess, sys, time
from pathlib import Path
import pytest
from tests.test_listings import addrs, admin, CSV_HEAD  # noqa: F401
from tests.test_settings_map import INPUTS

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
pytestmark = pytest.mark.skipif(not (shutil.which("node") and Path("/opt/node-tools/node_modules/playwright").exists() and Path(CHROME).exists()), reason="node Playwright / Chromium not installed")

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def test_map_app_in_browser(addrs, tmp_path):
    num, road, sub = addrs["single"][1], addrs["single"][2], addrs["single"][3]
    port = free_port(); pw = os.environ["APP_PASSWORD"]; env = {**os.environ, "UPLOAD_DIR": str(tmp_path), "APP_PASSWORD": pw}
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    try:
        import httpx
        for _ in range(60):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2).status_code == 200: break
            except Exception: time.sleep(0.5)
        base = f"http://127.0.0.1:{port}"
        assert httpx.get(base + "/api/status").status_code == 401                       # nothing without a login
        cl = httpx.Client(base_url=base); assert cl.post("/login", json={"password": pw}).status_code == 200
        cl.put("/api/settings/assumptions", json={"values": INPUTS})
        cl.post("/api/listings/import", files={"file": ("l.csv", (CSV_HEAD + f"T-ui,{num} {road},{sub},500,12,3,rent,\n").encode())}, data={"source": "csv_manual", "dry_run": "false"})
        shot = str(tmp_path / "map.png")
        r = subprocess.run(["node", str(ROOT / "tests/ui/map_smoke.js"), base, shot, f"{num} {road}"], capture_output=True, text=True, timeout=120, env={**os.environ, "UI_PASSWORD": pw})
        assert r.returncode == 0, r.stdout + r.stderr
        assert Path(shot).stat().st_size > 5000
        Path(os.environ.get("UI_SHOT_COPY", "/dev/null")).write_bytes(Path(shot).read_bytes()) if os.environ.get("UI_SHOT_COPY") else None
    finally:
        srv.terminate(); srv.wait(timeout=10)
        with admin() as c:
            c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history"); c.execute("DELETE FROM core.user_listing WHERE source_id = 'T-ui'")
