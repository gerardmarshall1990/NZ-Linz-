"""Every fixed API path the phone pages call must exist and not error (a page that calls a removed or renamed endpoint breaks silently)."""
import re
from pathlib import Path
from fastapi.testclient import TestClient
ROOT = Path(__file__).resolve().parent.parent

def test_fixed_get_paths_called_by_the_pages_work():
    from backend.app.main import app
    c = TestClient(app); seen = {}
    for f in ("app.html", "ui.html"):
        txt = (ROOT / "backend/app/static" / f).read_text()
        for m in re.finditer(r"api\(\s*['\"](/api/[A-Za-z0-9/_\-]+)['\"]\s*\)", txt): seen.setdefault(m.group(1), f)             # plain GETs: api('/api/x')
    assert len(seen) >= 8
    for path, f in sorted(seen.items()):
        r = c.get(path); assert r.status_code in (200, 403), (f, path, r.status_code, r.text[:120])                                  # 403 = a feature flag that is off, on purpose

def test_the_plans_page_status_line_uses_the_status_endpoint():
    txt = (ROOT / "backend/app/static/ui.html").read_text(); assert "api('/api/status')" in txt and "h.sites" in txt
    from backend.app.main import app
    assert "sites" in TestClient(app).get("/api/status").json()
