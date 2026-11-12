from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi import Depends, Header, Request

from app.ai.service import AiService
from app.auth import sessions as auth_sessions
from app.auth.identity import bearer_token, record_auth_event, resolve_identity
from app.auth.tokens import TokenError
from app.config import Settings
from app.db import connect
from app.errors import unauthorized
from app.repositories.store import Store
from app.safety.rate_limit import SlidingWindowLimiter
from app.services.auth import get_user


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_store(request: Request) -> Generator[Store, None, None]:
    settings: Settings = request.app.state.settings
    conn = connect(settings.db_path)
    store = Store(conn)
    try:
        yield store
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def get_ai_service(settings: Settings = Depends(get_settings)) -> AiService:
    return AiService(settings)


def get_rate_limiter(request: Request) -> SlidingWindowLimiter:
    return request.app.state.rate_limiter


def current_user(
    request: Request,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
    x_demo_user_id: str | None = Header(default=None, alias="X-Demo-User-Id"),
) -> dict[str, Any]:
    """Resolve the caller from a trusted identity source for the active mode.

    Demo mode keeps the synthetic header identity. Production mode never reads that
    header: it requires a verified bearer token and a server-side account link, so
    role, patient and account are never taken from browser input.
    """
    if settings.auth_mode != "production":
        return get_user(store, x_demo_user_id)

    # Server-managed cookie session first: it is the browser path and carries no
    # provider token. Bearer tokens remain supported for non-browser API clients.
    session_token = request.cookies.get(auth_sessions.SESSION_COOKIE)
    if session_token:
        session = auth_sessions.validate_session(
            store, session_token, idle_seconds=settings.auth_session_idle_seconds
        )
        auth_sessions.require_csrf(request, session)
        session_user = store.get_user(session["user_id"])
        if not session_user:
            raise unauthorized("This identity is not linked to a CareTwin account.")
        return session_user

    provider = getattr(request.app.state, "identity_provider", None)
    if provider is None:
        raise unauthorized("Authentication is not configured on this server.")
    token = bearer_token(authorization)
    try:
        identity = provider.verify(token, revoked=store.is_token_revoked)
    except TokenError as exc:
        record_auth_event(
            store,
            event="auth.token_rejected",
            outcome="denied",
            reason=exc.reason,
        )
        raise unauthorized("A valid access token is required.") from exc
    return resolve_identity(
        store, identity, require_link=settings.auth_require_identity_link
    )
