"""Server-managed browser sessions and CSRF protection.

Session identifiers are random opaque values from ``secrets``; only their SHA-256
hash is stored, so a database read cannot replay a session. Cookies are HttpOnly,
Secure in production, SameSite=Lax, and paired with a double-submit CSRF token for
state-changing requests. Provider tokens are never stored in the browser.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request, Response

from app.errors import ApiError, unauthorized

SESSION_COOKIE = "caretwin_session"
CSRF_COOKIE = "caretwin_csrf"
CSRF_HEADER = "X-CSRF-Token"
OAUTH_STATE_COOKIE = "caretwin_oauth_state"

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_TOUCH_INTERVAL_SECONDS = 60


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def token_hash(token: str) -> str:
    """Expose the stored hash for session lookup without exposing the token."""
    return _hash(token)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def create_session(
    store,
    *,
    user_id: str,
    issuer: str,
    subject: str,
    auth_time: int | None,
    amr: tuple[str, ...] | list[str] | None,
    ttl_seconds: int,
) -> tuple[str, str, dict[str, Any]]:
    """Create a server-side session and return (cookie token, csrf token, row)."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = _now()
    row = {
        "id": f"ses_{secrets.token_hex(12)}",
        "token_hash": _hash(token),
        "csrf_hash": _hash(csrf),
        "user_id": user_id,
        "issuer": issuer,
        "subject": subject,
        "auth_time": int(auth_time) if auth_time else None,
        "amr": " ".join(amr or ()),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=max(60, ttl_seconds))).isoformat(),
        "last_seen_at": now.isoformat(),
        "revoked_at": None,
        "revoked_reason": "",
    }
    store.create_auth_session(row)
    store.conn.commit()
    return token, csrf, row


def validate_session(
    store,
    token: str | None,
    *,
    idle_seconds: int,
) -> dict[str, Any]:
    """Validate a session cookie value, enforcing expiry, idle timeout and revocation."""
    if not token:
        raise unauthorized("A valid session is required.")
    row = store.get_auth_session_by_hash(_hash(token))
    if not row or row.get("revoked_at"):
        raise unauthorized("A valid session is required.")
    now = _now()
    if now >= _parse(row["expires_at"]):
        store.revoke_auth_session(row["id"], reason="expired")
        store.conn.commit()
        raise unauthorized("The session has expired. Sign in again.")
    idle_limit = max(60, idle_seconds)
    if (now - _parse(row["last_seen_at"])).total_seconds() > idle_limit:
        store.revoke_auth_session(row["id"], reason="idle_timeout")
        store.conn.commit()
        raise unauthorized("The session has expired. Sign in again.")
    if (now - _parse(row["last_seen_at"])).total_seconds() > _TOUCH_INTERVAL_SECONDS:
        store.touch_auth_session(row["id"], now.isoformat())
        store.conn.commit()
    return row


def require_csrf(request: Request, session: dict[str, Any]) -> None:
    """Double-submit CSRF check for session-authenticated state changes."""
    if request.method.upper() not in _UNSAFE_METHODS:
        return
    presented = request.headers.get(CSRF_HEADER, "")
    if not presented or not secrets.compare_digest(_hash(presented), session["csrf_hash"]):
        raise ApiError(
            403,
            "csrf_failed",
            "The request could not be verified. Reload the page and try again.",
        )


def set_session_cookies(
    response: Response, token: str, csrf: str, *, ttl_seconds: int, secure: bool
) -> None:
    max_age = max(60, ttl_seconds)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response, *, secure: bool) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE, OAUTH_STATE_COOKIE):
        response.delete_cookie(name, path="/", secure=secure, httponly=name != CSRF_COOKIE)
