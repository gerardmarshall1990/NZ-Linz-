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
