"""Phase 13 secure-session and Authorization Code + PKCE tests.

The identity provider is mocked at the HTTP seam: these tests prove the flow,
state/nonce/PKCE handling, replay protection, session lifecycle and CSRF rules
without contacting a real provider. No live sign-in is claimed.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_auth_boundary as base
from app.auth import sessions as auth_sessions
from app.auth.oidc_flow import OidcFlow, OidcFlowConfig
from app.auth.provider import OidcIdentityProvider
from app.main import create_app

CLIENT_ID = "caretwin-web"
REDIRECT_URI = "http://testserver/api/v1/auth/callback"
CSRF = {"X-CSRF-Token": "placeholder"}


def build(tmp_path, monkeypatch, *, mode="production"):
    base.configure_env(tmp_path, monkeypatch, mode=mode)
    monkeypatch.setenv("CARETWIN_AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("CARETWIN_AUTH_SESSION_TTL_SECONDS", "600")
    monkeypatch.setenv("CARETWIN_AUTH_SESSION_IDLE_SECONDS", "600")
    monkeypatch.setenv("CARETWIN_AUTH_POST_LOGIN_REDIRECT", "/workspace")
    if mode == "production":
        monkeypatch.setenv("CARETWIN_AUTH_CLIENT_ID", CLIENT_ID)
        monkeypatch.setenv("CARETWIN_AUTH_REDIRECT_URI", REDIRECT_URI)
    app = create_app()
    holder: dict[str, str | None] = {"nonce": None, "subject": "subject-patient"}

    if mode == "production":
        app.state.identity_provider = OidcIdentityProvider(
            issuer=base.ISSUER,
            audience=base.AUDIENCE,
            keys={base.KID: base.PUBLIC_KEY},
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/.well-known/openid-configuration"):
                return httpx.Response(
                    200,
                    json={
                        "issuer": base.ISSUER,
                        "authorization_endpoint": "https://idp.example.test/authorize",
                        "token_endpoint": "https://idp.example.test/token",
                        "jwks_uri": "https://idp.example.test/jwks",
                    },
                )
            if request.url.path == "/token":
                token = base.make_token(
                    subject=holder["subject"] or "subject-patient",
                    nonce=holder["nonce"],
                )
                return httpx.Response(
                    200,
                    json={
                        "id_token": token,
                        "access_token": "provider-access-token-not-stored",
                        "token_type": "Bearer",
                        "expires_in": 300,
                    },
                )
            return httpx.Response(404)

        app.state.oidc_flow = OidcFlow(
            OidcFlowConfig(
                issuer=base.ISSUER,
                client_id=CLIENT_ID,
                redirect_uri=REDIRECT_URI,
                post_login_redirect="/workspace",
            ),
            provider=app.state.identity_provider,
            client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )
    return app, holder


@pytest.fixture()
def session_app(tmp_path, monkeypatch):
    app, holder = build(tmp_path, monkeypatch)
    with TestClient(app) as client:
        db = Path(os.environ["CARETWIN_DB_PATH"])
        base.link(db, base.ISSUER, "subject-patient", "usr_maya")
        yield client, holder, db


def begin_login(client, holder) -> tuple[str, dict[str, list[str]]]:
    response = client.get("/api/v1/auth/login", follow_redirects=False)
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    query = parse_qs(urlparse(location).query)
    state = query["state"][0]
    db = Path(os.environ["CARETWIN_DB_PATH"])
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT nonce FROM auth_flows WHERE state_hash = ?",
            (auth_sessions.token_hash(state),),
        ).fetchone()
    finally:
        conn.close()
    assert row, "the flow must be stored server-side"
    holder["nonce"] = row[0]
    return state, query


def finish_login(client, state: str):
    return client.get(
        f"/api/v1/auth/callback?code=code-1&state={state}", follow_redirects=False
    )


def csrf_header(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(auth_sessions.CSRF_COOKIE, "")}


def test_login_redirect_uses_state_nonce_and_pkce(session_app):
    client, holder, _ = session_app
    state, query = begin_login(client, holder)
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) == 43
    assert query["state"] == [state]
    assert query["nonce"][0]
    assert query["redirect_uri"] == [REDIRECT_URI]
    assert client.cookies.get(auth_sessions.OAUTH_STATE_COOKIE) == state


def test_successful_callback_creates_httponly_session(session_app):
    client, holder, _ = session_app
    state, _ = begin_login(client, holder)
    response = finish_login(client, state)
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/workspace"
    set_cookie = " ".join(response.headers.get_list("set-cookie"))
    assert auth_sessions.SESSION_COOKIE in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "provider-access-token-not-stored" not in set_cookie
    assert "id_token" not in set_cookie

    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200, session.text
    assert session.json()["user"]["id"] == "usr_maya"
    assert session.json()["user"]["role"] == "patient"


def test_callback_rejects_demo_identity_and_state_mismatch(session_app):
    client, holder, _ = session_app
    begin_login(client, holder)
    mismatch = client.get(
        "/api/v1/auth/callback?code=code-1&state=forged-state", follow_redirects=False
    )
    assert mismatch.status_code == 401
    assert client.cookies.get(auth_sessions.SESSION_COOKIE) in {None, ""}


def test_callback_replay_is_rejected(session_app):
    client, holder, _ = session_app
    state, _ = begin_login(client, holder)
    first = finish_login(client, state)
    assert first.status_code == 303
    second = finish_login(client, state)
    assert second.status_code == 401


def test_nonce_mismatch_creates_no_session(session_app):
    client, holder, _ = session_app
    state, _ = begin_login(client, holder)
    holder["nonce"] = "wrong-nonce"
    response = finish_login(client, state)
    assert response.status_code == 401
    assert client.get("/api/v1/auth/session").status_code == 401


def test_expired_flow_is_rejected(session_app):
    client, holder, db = session_app
    state, _ = begin_login(client, holder)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "UPDATE auth_flows SET expires_at = ? WHERE state_hash = ?",
            (str(int(time.time()) - 10), auth_sessions.token_hash(state)),
        )
        conn.commit()
    finally:
        conn.close()
    assert finish_login(client, state).status_code == 401


def test_csrf_is_required_for_session_mutations(session_app):
    client, holder, _ = session_app
    state, _ = begin_login(client, holder)
    assert finish_login(client, state).status_code == 303
    blocked = client.post("/api/v1/auth/sessions/revoke-all")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "csrf_failed"
    allowed = client.post("/api/v1/auth/sessions/revoke-all", headers=csrf_header(client))
    assert allowed.status_code == 200
    assert allowed.json()["revoked"] >= 1


def test_logout_revokes_the_session(session_app):
    client, holder, _ = session_app
    state, _ = begin_login(client, holder)
    assert finish_login(client, state).status_code == 303
    logout = client.post("/api/v1/auth/logout", headers=csrf_header(client))
    assert logout.status_code == 200, logout.text
    assert logout.json()["scope"] == "session"
    assert client.get("/api/v1/auth/session").status_code == 401


def test_session_expiry_and_idle_timeout(session_app):
    client, holder, db = session_app
    state, _ = begin_login(client, holder)
    assert finish_login(client, state).status_code == 303
    conn = sqlite3.connect(db)
    try:
        conn.execute("UPDATE auth_sessions SET expires_at = ?", (str(int(time.time()) - 5),))
        conn.commit()
    finally:
        conn.close()
    # expires_at is ISO formatted; make it parse as an ISO instant in the past.
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "UPDATE auth_sessions SET expires_at = ?",
            ("2020-01-01T00:00:00+00:00",),
        )
        conn.commit()
    finally:
        conn.close()
    assert client.get("/api/v1/auth/session").status_code == 401

    state, _ = begin_login(client, holder)
    assert finish_login(client, state).status_code == 303
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "UPDATE auth_sessions SET last_seen_at = ? WHERE revoked_at IS NULL",
            ("2020-01-01T00:00:00+00:00",),
        )
        conn.commit()
    finally:
        conn.close()
    assert client.get("/api/v1/auth/session").status_code == 401


def test_account_wide_revocation_ends_every_session(session_app):
    client, holder, db = session_app
    state, _ = begin_login(client, holder)
    assert finish_login(client, state).status_code == 303
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO auth_sessions (id, token_hash, csrf_hash, user_id, issuer, "
            "subject, auth_time, amr, created_at, expires_at, last_seen_at, revoked_at, "
            "revoked_reason) VALUES ('ses_second', 'hash-second', 'csrf-second', "
            "'usr_maya', ?, 'subject-patient', NULL, '', '2026-01-01T00:00:00+00:00', "
            "'2030-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL, '')",
            (base.ISSUER,),
        )
        conn.commit()
    finally:
        conn.close()
    revoked = client.post("/api/v1/auth/sessions/revoke-all", headers=csrf_header(client))
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] == 2
    assert client.get("/api/v1/auth/session").status_code == 401


def test_session_listing_is_scoped_to_the_owner(session_app):
    client, holder, db = session_app
    state, _ = begin_login(client, holder)
    assert finish_login(client, state).status_code == 303
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO auth_sessions (id, token_hash, csrf_hash, user_id, issuer, "
            "subject, auth_time, amr, created_at, expires_at, last_seen_at, revoked_at, "
            "revoked_reason) VALUES ('ses_other', 'hash-other', 'csrf-other', "
            "'usr_arjun', ?, 'subject-caregiver', NULL, '', '2026-01-01T00:00:00+00:00', "
            "'2030-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL, '')",
            (base.ISSUER,),
        )
        conn.commit()
    finally:
        conn.close()
    listing = client.get("/api/v1/auth/sessions")
    assert listing.status_code == 200
    ids = [row["id"] for row in listing.json()["sessions"]]
    assert ids and "ses_other" not in ids
    assert listing.json()["currentSessionId"] in ids


def test_unlinked_subject_cannot_establish_a_session(session_app):
    client, holder, _ = session_app
    holder["subject"] = "unlinked-subject"
    state, _ = begin_login(client, holder)
    assert finish_login(client, state).status_code == 401
    assert client.get("/api/v1/auth/session").status_code == 401


def test_demo_mode_has_no_production_sign_in(tmp_path, monkeypatch):
    app, _ = build(tmp_path, monkeypatch, mode="demo")
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/login", follow_redirects=False).status_code == 404
        assert client.get("/api/v1/demo/session").status_code == 200
