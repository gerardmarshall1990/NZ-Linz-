"""Test setup: the app now requires a login. Every TestClient made by the tests starts with a valid session (created through the real session code), except clients built from RAW_TESTCLIENT,
which the auth tests use to check that nothing is served without a login."""
import os
os.environ.setdefault("APP_PASSWORD", "test-password-0123456789")
import fastapi.testclient as _ftc
if not hasattr(_ftc, '_RAW_TESTCLIENT'): _ftc._RAW_TESTCLIENT = _ftc.TestClient     # the module can be imported twice (as conftest and tests.conftest): patch once
RAW_TESTCLIENT = _ftc._RAW_TESTCLIENT

class AuthedClient(RAW_TESTCLIENT):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        from backend.app import auth
        self.headers["cookie"] = f"{auth.COOKIE}={auth.create_session()}"

if _ftc.TestClient is RAW_TESTCLIENT: _ftc.TestClient = AuthedClient


import json, pytest

def _admin():
    import psycopg
    for l in open(os.path.join(os.path.dirname(__file__), "..", ".env")).read().splitlines():
        if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
    return psycopg.connect(f"host=localhost dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}", autocommit=True)

@pytest.fixture(scope="session", autouse=True)
def protect_the_owners_saved_inputs():
    """Several tests start from blank inputs and clean up with DELETE FROM core.user_setting. The owner's real saved inputs must survive the test run: snapshot them first
    (also to backups/, in case the run is killed) and put them back exactly afterwards."""
    try: c = _admin()
    except Exception: yield; return
    rows = c.execute("SELECT key, value, updated_at, updated_by FROM core.user_setting").fetchall()
    hist = c.execute("SELECT key, old_value, new_value, changed_at FROM core.user_setting_history ORDER BY id").fetchall()
    snap = os.path.join(os.path.dirname(__file__), "..", "backups", "user_settings_snapshot.json")
    os.makedirs(os.path.dirname(snap), exist_ok=True)
    c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history")      # tests start from pristine (blank) inputs; the owner's are put back below
    json.dump({"settings": [[r[0], r[1], str(r[2]), r[3]] for r in rows], "history": [[h[0], h[1], h[2], str(h[3])] for h in hist]}, open(snap, "w"))
    yield
    c.execute("DELETE FROM core.user_setting"); c.execute("DELETE FROM core.user_setting_history")
    for k, v, at, by in rows: c.execute("INSERT INTO core.user_setting (key, value, updated_at, updated_by) VALUES (%s, %s::jsonb, %s, %s)", (k, json.dumps(v), at, by))
    for k, o, n, at in hist: c.execute("INSERT INTO core.user_setting_history (key, old_value, new_value, changed_at) VALUES (%s, %s::jsonb, %s::jsonb, %s)", (k, json.dumps(o) if o is not None else None, json.dumps(n), at))
    c.close()
