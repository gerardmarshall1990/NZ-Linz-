"""Login and access control: nothing is served without a session, fail-closed without a password, rate limiting, cookie flags, cross-site writes refused, security headers,
no secrets in any response, bound to localhost by default."""
import os, re
from pathlib import Path
import pytest
from tests.conftest import RAW_TESTCLIENT
from backend.app import auth
from backend.app.main import app

ROOT = Path(__file__).resolve().parent.parent
PW = os.environ["APP_PASSWORD"]

@pytest.fixture()
def raw():
    auth._fails.clear()
    return RAW_TESTCLIENT(app)

PAGES = ["/", "/plans", "/api/status", "/api/sites/search?q=queen", "/api/sites/4898114", "/api/property/4898114", "/api/listings/sources", "/api/settings", "/api/map/listings",
         "/api/listings/review-queue", "/api/uploads/1/preview.png", "/api/briefs/1", "/api/layouts/1", "/api/property/4898114/gaps", "/api/scenarios/1/proposal?mode=jv"]

def test_nothing_is_served_without_login(raw):
    for p in PAGES:
        r = raw.get(p, follow_redirects=False)
        assert r.status_code in (401, 303), (p, r.status_code)
        if p.startswith("/api"): assert r.status_code == 401 and "login required" in r.text
        else: assert r.headers["location"] == "/login"
    for method, p, kw in (("post", "/api/chat", {"json": {"message": "hi"}}), ("put", "/api/settings/assumptions", {"json": {"values": {}}}), ("post", "/api/listings/import", {}), ("post", "/api/property/4898114", {}),
                          ("post", "/api/uploads/1/extract", {"json": {"mode": "manual"}}), ("post", "/logout", {})):
        r = getattr(raw, method)(p, follow_redirects=False, **kw); assert r.status_code in (401, 303), (p, r.status_code)
        if p.startswith('/api'): assert r.status_code == 401, (p, r.status_code)

def test_only_login_and_minimal_health_are_public(raw):
    assert raw.get("/login").status_code == 200 and "password" in raw.get("/login").text.lower()
    h = raw.get("/api/health"); assert h.status_code == 200 and h.json() == {"ok": True}                 # nothing about data or configuration
    assert raw.get("/docs", follow_redirects=False).status_code in (401, 303, 404) and raw.get("/openapi.json", follow_redirects=False).status_code in (401, 303, 404)
    c = RAW_TESTCLIENT(app); c.headers["cookie"] = "session=" + auth.create_session(); assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404   # API docs are off

def test_wrong_password_rejected_and_rate_limited(raw):
    for i in range(auth.MAX_FAILS): assert raw.post("/login", json={"password": "nope"}).status_code == 401
    r = raw.post("/login", json={"password": PW}); assert r.status_code == 429                          # locked even with the right password until the window passes
    assert "session" not in r.headers.get("set-cookie", "")

def test_login_cookie_flags_and_session_flow(raw):
    r = raw.post("/login", json={"password": PW}); assert r.status_code == 200
    c = r.headers["set-cookie"].lower(); assert "httponly" in c and "samesite=strict" in c and "path=/" in c and "max-age=" in c
    assert raw.get("/api/status").status_code == 200                                                    # cookie jar carries the session
    rs = RAW_TESTCLIENT(app, base_url="https://testserver").post("/login", json={"password": PW}); assert "secure" in rs.headers["set-cookie"].lower()   # Secure over https
    raw.post("/logout"); assert raw.get("/api/status", follow_redirects=False).status_code == 401       # logout kills the server-side session

def test_forged_or_expired_sessions_rejected(raw):
    raw.headers["cookie"] = "session=" + "x" * 43; assert raw.get("/api/status").status_code == 401
    t = auth.create_session(); auth._sessions[__import__("hashlib").sha256(t.encode()).hexdigest()] = 1.0       # expired
    raw.headers["cookie"] = "session=" + t; assert raw.get("/api/status").status_code == 401

def test_cross_site_writes_are_refused():
    c = RAW_TESTCLIENT(app); c.headers["cookie"] = "session=" + auth.create_session()
    r = c.put("/api/settings/assumptions", json={"values": {}}, headers={"Origin": "https://evil.example"}); assert r.status_code == 403
    r = c.put("/api/settings/assumptions", json={"values": {}}, headers={"Origin": "http://testserver"}); assert r.status_code == 200

def test_fails_closed_without_a_password(monkeypatch, raw):
    monkeypatch.delenv("APP_PASSWORD")
    assert raw.get("/api/sites/search?q=queen street", follow_redirects=False).status_code in (401, 503)
    c = RAW_TESTCLIENT(app); c.headers["cookie"] = "session=" + auth.create_session()
    assert c.get("/api/status").status_code == 503 and c.get("/", follow_redirects=False).status_code == 303   # even a valid-looking session is refused
    assert raw.post("/login", json={"password": ""}).status_code == 503 and "APP_PASSWORD" in raw.get("/login").text
    monkeypatch.setenv("APP_PASSWORD", "short"); assert not auth.configured()                           # too short counts as not set

def test_security_headers_present(raw):
    for p in ("/login", "/api/health", "/api/status"):
        h = raw.get(p).headers
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer" and "no-store" in h["cache-control"] and "frame-ancestors 'none'" in h["content-security-policy"]

def test_no_secret_appears_in_any_response_or_page():
    secrets_ = [os.environ.get(k) for k in ("APP_PASSWORD", "POSTGRES_PASSWORD", "AI_READONLY_PASSWORD", "APP_RW_PASSWORD", "LINZ_API_KEY", "ANTHROPIC_API_KEY", "BACKUP_PASSPHRASE")]
    secrets_ = [s for s in secrets_ if s and len(s) >= 8]
    c = RAW_TESTCLIENT(app); c.headers["cookie"] = "session=" + auth.create_session()
    bodies = [c.get(p).text for p in ("/", "/plans", "/login", "/api/status", "/api/settings", "/api/listings/sources", "/api/health")]
    for f in (ROOT / "backend/app/static").glob("*.html"): bodies.append(f.read_text())
    for b in bodies:
        for s in secrets_: assert s not in b
        assert not re.search(r"sk-ant-[A-Za-z0-9_-]{10,}", b)
    assert not re.search(r"ANTHROPIC_API_KEY|process\.env|APP_PASSWORD", "".join((ROOT / "backend/app/static" / f).read_text() for f in ("app.html", "ui.html")))   # the pages never reference server secrets

def test_app_binds_to_localhost_only_by_default():
    mk = (ROOT / "Makefile").read_text()
    assert "--host 127.0.0.1" in mk and "0.0.0.0" not in mk
    assert "0.0.0.0" not in (ROOT / "scripts/start_private.sh").read_text() and "--host 127.0.0.1" in (ROOT / "scripts/start_private.sh").read_text()
