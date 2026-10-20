"""Supabase login through the real API against a FAKE Supabase (stdlib HTTP server speaking the
GoTrue + PostgREST endpoints claimshield/auth.py uses): signup, login, verified user, admin role
from user_profiles, bad token → 401, logout revokes, and auth off → demo personas still work."""
import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from claimshield import audit, auth  # noqa: E402

USERS: dict[str, dict] = {}     # email → {id, password, meta}
TOKENS: dict[str, str] = {}     # token → email
ROLES = {"admin@claimshield.dev": "admin"}


class FakeSupabase(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _who(self):
        return TOKENS.get(self.headers.get("Authorization", "")[7:])

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/auth/v1/signup":
            if body["email"] in USERS:
                return self._send(422, {"msg": "User already registered"})
            USERS[body["email"]] = {"id": f"u{len(USERS)}", "password": body["password"], "meta": body.get("data", {})}
            return self._login(body["email"])
        if self.path.startswith("/auth/v1/token"):
            u = USERS.get(body["email"])
            if not u or u["password"] != body["password"]:
                return self._send(400, {"error_description": "Invalid login credentials"})
            return self._login(body["email"])
        if self.path == "/auth/v1/logout":
            TOKENS.pop(self.headers.get("Authorization", "")[7:], None)
            return self._send(204 if False else 200, {})
        self._send(404, {})

    def _login(self, email):
        tok = f"tok-{email}-{len(TOKENS)}"
        TOKENS[tok] = email
        u = USERS[email]
        self._send(200, {"access_token": tok, "refresh_token": "r", "expires_in": 3600,
                         "user": {"id": u["id"], "email": email, "user_metadata": u["meta"]}})

    def do_GET(self):
        email = self._who()
        if self.path == "/auth/v1/user":
            if not email:
                return self._send(401, {"msg": "invalid JWT"})
            u = USERS[email]
            return self._send(200, {"id": u["id"], "email": email, "user_metadata": u["meta"]})
        if self.path.startswith("/rest/v1/user_profiles"):
            return self._send(200, [{"role": ROLES.get(email, "reviewer")}] if email else [])
        self._send(404, {})


@pytest.fixture
def client(tmp_path, monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeSupabase)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("SUPABASE_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setattr(audit, "DB", tmp_path / "audit.sqlite")
    USERS.clear(), TOKENS.clear(), auth._cache.clear()
    sys.modules.pop("claimshield.api", None)
    mod = importlib.import_module("claimshield.api")
    with TestClient(mod.app) as c:
        yield c
    srv.shutdown()


def test_signup_login_verified_user_and_admin_role(client):
    assert client.get("/api/auth/status").json() == {"enabled": True}
    r = client.post("/api/auth/signup", json={"email": "asha@claimshield.dev", "password": "pw123456",
                                              "full_name": "Asha Patel"})
    assert r.status_code == 200 and r.json()["access_token"]
    assert client.post("/api/auth/signup", json={"email": "asha@claimshield.dev", "password": "x"}).status_code == 422

    bad = client.post("/api/auth/login", json={"email": "asha@claimshield.dev", "password": "nope"})
    assert bad.status_code == 400 and "Invalid login" in bad.json()["error"]["message"]
    tok = client.post("/api/auth/login", json={"email": "asha@claimshield.dev", "password": "pw123456"}).json()["access_token"]
    me = client.get("/api/auth/user", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["verified"] and me["user"] == "Asha Patel" and me["role"] == "reviewer"

    client.post("/api/auth/signup", json={"email": "admin@claimshield.dev", "password": "pw123456"})
    atok = client.post("/api/auth/login", json={"email": "admin@claimshield.dev", "password": "pw123456"}).json()
    assert atok["user"]["role"] == "admin"


def test_bad_token_401_and_logout_revokes(client):
    client.post("/api/auth/signup", json={"email": "bob@claimshield.dev", "password": "pw123456"})
    tok = client.post("/api/auth/login", json={"email": "bob@claimshield.dev", "password": "pw123456"}).json()["access_token"]
    assert client.get("/api/auth/user", headers={"Authorization": "Bearer forged"}).status_code == 401
    assert client.get("/api/health", headers={"Authorization": "Bearer forged"}).status_code == 200  # public stays public
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {tok}"}).json() == {"ok": True}
    assert client.get("/api/auth/user", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_auth_off_keeps_demo_personas(client, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL")
    assert client.get("/api/auth/status").json() == {"enabled": False}
    assert client.post("/api/auth/login", json={"email": "a", "password": "b"}).status_code == 503
    assert client.get("/api/auth/user", headers={"X-Reviewer": "asha"}).status_code == 401   # not verified
