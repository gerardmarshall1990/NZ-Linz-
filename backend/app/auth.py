"""Owner login. Everything except /login and a minimal /api/health needs a valid session; with no APP_PASSWORD set the app refuses to serve (fails closed).
The password comes only from the APP_PASSWORD environment variable (never a file in the repo). Sessions are random 256-bit tokens kept on the server; the cookie is HttpOnly,
SameSite=Strict and Secure over https. Failed logins are rate limited. API keys (Anthropic, database, backups) are read from the server environment only and are never sent to the browser."""
import hashlib, hmac, os, secrets, time
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

COOKIE = "session"; SESSION_SECONDS = 7 * 24 * 3600
PUBLIC = {"/login", "/api/health", "/favicon.ico", "/robots.txt"}
_sessions: dict[str, float] = {}
_fails: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 15 * 60

def configured() -> bool: return len(os.environ.get("APP_PASSWORD", "")) >= 12

def _digest(s: str) -> bytes: return hashlib.sha256(("nzlinz|" + s).encode()).digest()

def check_password(pw: str) -> bool:
    return configured() and hmac.compare_digest(_digest(pw or ""), _digest(os.environ["APP_PASSWORD"]))

def create_session() -> str:
    now = time.time()
    for k in [k for k, exp in _sessions.items() if exp < now]: _sessions.pop(k, None)
    t = secrets.token_urlsafe(32); _sessions[hashlib.sha256(t.encode()).hexdigest()] = now + SESSION_SECONDS; return t

def valid(token: str | None) -> bool:
    if not token: return False
    exp = _sessions.get(hashlib.sha256(token.encode()).hexdigest())
    return bool(exp and exp > time.time())

def destroy(token: str | None) -> None:
    if token: _sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)

def _ip(req: Request) -> str: return (req.headers.get("x-forwarded-for", "").split(",")[0].strip() or (req.client.host if req.client else "?"))

def locked(ip: str) -> bool:
    now = time.time(); _fails[ip] = [t for t in _fails.get(ip, []) if now - t < WINDOW]
    glob = sum(len(v) for v in _fails.values())
    return len(_fails[ip]) >= MAX_FAILS or glob >= MAX_FAILS * 4

def record_fail(ip: str) -> None: _fails.setdefault(ip, []).append(time.time())

HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
           "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
           "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                                      "img-src 'self' data: blob: https://*.openstreetmap.org https://cdnjs.cloudflare.com; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"}

LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in</title>
<style>:root{--bg:#fff;--fg:#14202b;--bd:#d5dde5;--acc:#0b5cab}@media(prefers-color-scheme:dark){:root{--bg:#0f1720;--fg:#e8eef4;--bd:#2a3a49;--acc:#6db3f2}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px system-ui,-apple-system,sans-serif;display:grid;place-items:center;min-height:100vh}form{width:min(92vw,360px)}
input,button{font:inherit;width:100%;padding:12px;margin:6px 0;border-radius:10px;border:1px solid var(--bd);background:var(--bg);color:var(--fg);box-sizing:border-box}button{background:var(--acc);color:#fff;border-color:var(--acc)}
#m{color:#b91c1c;min-height:1.4em}</style></head><body><form id="f"><h2>Rest Home Finder</h2><div class="mut">__NOTE__</div>
<input id="p" type="password" autocomplete="current-password" placeholder="Password" autofocus required><button>Sign in</button><div id="m"></div></form>
<script>document.getElementById('f').onsubmit=async e=>{e.preventDefault();const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('p').value})});
if(r.ok){location.href='/'}else{let m='Sign-in failed';try{m=(await r.json()).detail}catch(x){}document.getElementById('m').textContent=m}}</script></body></html>"""

def login_page() -> HTMLResponse:
    note = "" if configured() else "This server has no APP_PASSWORD set (16+ characters recommended, 12 minimum), so it refuses to serve anything. Set it in the environment settings."
    return HTMLResponse(LOGIN_HTML.replace("__NOTE__", note))

async def middleware(request: Request, call_next):
    path = request.url.path; resp: Response
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):      # cross-site writes are refused (SameSite=Strict is the first defence)
        origin = request.headers.get("origin"); host = request.headers.get("host", "")
        if origin and origin.split("://", 1)[-1] != host: return _with(JSONResponse({"detail": "cross-site request refused"}, 403))
    if path in PUBLIC: resp = await call_next(request)
    elif not configured(): resp = JSONResponse({"detail": "server not configured: set APP_PASSWORD"}, 503) if path.startswith("/api") else RedirectResponse("/login", 303)
    elif not valid(request.cookies.get(COOKIE)): resp = JSONResponse({"detail": "login required"}, 401) if path.startswith("/api") else RedirectResponse("/login", 303)
    else: resp = await call_next(request)
    return _with(resp)

def _with(resp: Response) -> Response:
    for k, v in HEADERS.items(): resp.headers.setdefault(k, v)
    return resp

def set_cookie(resp: Response, req: Request, token: str) -> None:
    secure = req.url.scheme == "https" or req.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="strict", secure=secure, path="/")
