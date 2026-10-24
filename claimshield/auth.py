"""Optional Supabase login (README), over Supabase's REST API with the stdlib only.

On when SUPABASE_URL + SUPABASE_ANON_KEY are set (.env), off otherwise: then the frontend's demo
personas and the X-Reviewer header keep working, so a demo is never blocked at login.

Tokens are verified BY Supabase (GET /auth/v1/user), so every signing scheme works (legacy HS256
and the current asymmetric keys alike) and revoked sessions are rejected. The app role comes from
public.user_profiles, read with the user's own token (RLS: "own profile"): no service key here.
Calls go through HTTPS_PROXY when set (the offline GPU node uses the laptop proxy).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from . import config  # noqa: F401  (loads .env)

TIMEOUT = 10
_cache: dict[str, tuple[float, dict]] = {}   # token → (expires_at, user)
CACHE_S = 60   # ponytail: per-process token cache; a revoked token can live ≤ 60 s here


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def enabled() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY"))


def _call(method: str, path: str, body: dict | None = None, token: str | None = None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    headers = {"apikey": os.environ["SUPABASE_ANON_KEY"], "Content-Type": "application/json",
               "Authorization": f"Bearer {token or os.environ['SUPABASE_ANON_KEY']}"}
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read() or b"{}")
        except ValueError:
            err = {}
        msg = err.get("msg") or err.get("error_description") or err.get("message") or err.get("error") or e.reason
        raise AuthError(e.code, str(msg)) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AuthError(503, f"Supabase unreachable: {getattr(e, 'reason', e)}") from None


def _session(data: dict) -> dict:
    """GoTrue response → what the frontend needs (no refresh token juggling on the server)."""
    user = data.get("user") or (data if data.get("id") else {})
    return {"access_token": data.get("access_token"), "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"), "user": _user(user)}


def _user(u: dict, role: str | None = None) -> dict:
    meta = u.get("user_metadata") or {}
    return {"id": u.get("id"), "email": u.get("email"), "full_name": meta.get("full_name") or "",
            "organization": meta.get("organization"), "role": role or "reviewer"}


def sign_up(email: str, password: str, full_name: str = "", organization: str | None = None) -> dict:
    data = _call("POST", "/auth/v1/signup", {"email": email, "password": password,
                                             "data": {"full_name": full_name, "organization": organization}})
    out = _session(data)
    if not out["access_token"]:
        out["message"] = ("Account created. Confirm the email (or turn off 'Confirm email' in Supabase → "
                          "Authentication → Providers → Email), then log in.")
    return out


def sign_in(email: str, password: str) -> dict:
    out = _session(_call("POST", "/auth/v1/token?grant_type=password", {"email": email, "password": password}))
    if out["access_token"]:
        out["user"]["role"] = _role(out["user"]["id"], out["access_token"])
    return out


def sign_out(token: str) -> None:
    _call("POST", "/auth/v1/logout", {}, token)
    _cache.pop(token, None)


def _role(user_id: str, token: str) -> str:
    try:
        rows = _call("GET", f"/rest/v1/user_profiles?id=eq.{user_id}&select=role", token=token)
        return rows[0]["role"] if rows else "reviewer"
    except AuthError:
        return "reviewer"   # profiles table missing / RLS not set up: least privilege


def user_from_token(token: str) -> dict:
    """Verified user for a bearer token, or AuthError(401)."""
    hit = _cache.get(token)
    if hit and hit[0] > time.time():
        return hit[1]
    try:
        u = _call("GET", "/auth/v1/user", token=token)
    except AuthError as e:
        raise AuthError(401 if e.status in (400, 401, 403) else e.status,
                        "Invalid or expired token" if e.status in (400, 401, 403) else e.message) from None
    user = _user(u, _role(u.get("id"), token))
    _cache[token] = (time.time() + CACHE_S, user)
    return user
