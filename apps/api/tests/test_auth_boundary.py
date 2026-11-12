"""Phase 12 authentication and authorization boundary tests.

A static RSA key set is injected, so the real signature, issuer, audience, expiry
and revocation checks run here without contacting any provider. No test claims a
live identity provider exists: the provider choice is still open.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.provider import OidcIdentityProvider
from app.main import create_app

ISSUER = "https://idp.example.test"
AUDIENCE = "caretwin-api"
KID = "test-key-1"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY = _PRIVATE_KEY.public_key()
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

DEMO_DB = Path(__file__).resolve().parents[3] / "data" / "demo" / "caretwin.db"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_token(
    subject: str = "subject-patient",
    *,
    kid: str = KID,
    alg: str = "RS256",
    exp_delta: int = 600,
    signer=None,
    **claim_overrides,
) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": subject,
        "exp": now + exp_delta,
        "iat": now,
        "jti": f"jti-{subject}-{now}",
    }
    claims.update(claim_overrides)
    header = {"alg": alg, "typ": "JWT", "kid": kid}
    signing_input = (
        f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    ).encode()
    if alg == "none":
        return f"{signing_input.decode()}."
    signature = (signer or _PRIVATE_KEY).sign(
        signing_input, padding.PKCS1v15(), hashes.SHA256()
    )
    return f"{signing_input.decode()}.{_b64(signature)}"


def configure_env(tmp_path: Path, monkeypatch, *, mode: str) -> None:
    monkeypatch.setenv("CARETWIN_ENV", "test")
    monkeypatch.setenv("CARETWIN_DEMO_MODE", "true")
    monkeypatch.setenv("CARETWIN_SEED_DEMO", "true")
    monkeypatch.setenv("CARETWIN_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("CARETWIN_DOCUMENT_STORAGE_PATH", str(tmp_path / "docs"))
    monkeypatch.setenv("CARETWIN_AUTH_MODE", mode)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    if mode == "production":
        monkeypatch.setenv("CARETWIN_AUTH_ISSUER", ISSUER)
        monkeypatch.setenv("CARETWIN_AUTH_AUDIENCE", AUDIENCE)
        monkeypatch.setenv("CARETWIN_AUTH_JWKS_URL", "https://idp.example.test/jwks")
    else:
        for key in (
            "CARETWIN_AUTH_ISSUER",
            "CARETWIN_AUTH_AUDIENCE",
            "CARETWIN_AUTH_JWKS_URL",
        ):
            monkeypatch.delenv(key, raising=False)


def build_app(tmp_path, monkeypatch, *, mode="production"):
    configure_env(tmp_path, monkeypatch, mode=mode)
    app = create_app()
    if mode == "production":
        app.state.identity_provider = OidcIdentityProvider(
            issuer=ISSUER,
            audience=AUDIENCE,
            keys={KID: PUBLIC_KEY},
        )
    return app


def link(db_path: Path, issuer: str, subject: str, user_id: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO identity_links (id, issuer, subject, user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"idn_{subject}", issuer, subject, user_id, "2026-01-01T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()


def add_outsider(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, name, role, title, organization, initials, created_at) "
            "VALUES ('usr_outsider', 'Outside Clinician', 'clinician', 'Consultant', "
            "'Other Hospital', 'OC', '2026-01-01T00:00:00Z')"
        )
        conn.commit()
    finally:
        conn.close()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def prod(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch, mode="production")
    with TestClient(app) as client:
        db = Path(os.environ["CARETWIN_DB_PATH"])
        link(db, ISSUER, "subject-patient", "usr_maya")
        link(db, ISSUER, "subject-clinician", "usr_nandini")
        link(db, ISSUER, "subject-caregiver", "usr_arjun")
        link(db, ISSUER, "subject-revoked", "usr_priya")
        add_outsider(db)
        link(db, ISSUER, "subject-outsider", "usr_outsider")
        yield client, db


@pytest.fixture()
def demo(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch, mode="demo")
    with TestClient(app) as client:
        yield client


def test_demo_mode_keeps_the_synthetic_identity(demo):
    session = demo.get("/api/v1/auth/session", headers={"X-Demo-User-Id": "usr_maya"})
    assert session.status_code == 200
    body = session.json()
    assert body["mode"] == "demo"
    assert body["user"]["id"] == "usr_maya"
    assert demo.get("/api/v1/demo/session").status_code == 200


def test_production_rejects_demo_identity_and_anonymous_access(prod):
    client, _ = prod
    demo_header = client.get(
        "/api/v1/patients/pat_maya/twin", headers={"X-Demo-User-Id": "usr_maya"}
    )
    anonymous = client.get("/api/v1/patients/pat_maya/twin")
    demo_session = client.get("/api/v1/demo/session")
    demo_switch = client.post(
        "/api/v1/demo/session/switch", json={"userId": "usr_maya"}
    )
    assert demo_header.status_code == 401
    assert anonymous.status_code == 401
    assert demo_header.json()["error"]["code"] == "authentication_required"
    assert demo_session.status_code in {401, 404}
    assert demo_switch.status_code in {401, 404}


def test_valid_token_resolves_role_from_local_records(prod):
    client, _ = prod
    response = client.get("/api/v1/auth/session", headers=bearer(make_token()))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "production"
    assert body["providerDependent"] is True
    assert body["user"] == {
        "id": "usr_maya",
        "name": body["user"]["name"],
        "role": "patient",
        "title": body["user"]["title"],
        "organization": body["user"]["organization"],
        "initials": body["user"]["initials"],
    }
    assert client.get("/api/v1/patients/pat_maya/twin", headers=bearer(make_token())).status_code == 200


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: make_token(exp_delta=-3600),
        lambda: make_token(iss="https://attacker.example"),
        lambda: make_token(aud="another-api"),
        lambda: make_token(alg="none"),
        lambda: make_token(kid="unknown-key"),
        lambda: make_token(signer=_OTHER_KEY),
        lambda: make_token(sub=""),
        lambda: make_token(sub="unlinked-subject"),
    ],
)
def test_invalid_or_unlinked_tokens_are_rejected(prod, token_factory):
    client, _ = prod
    response = client.get("/api/v1/patients/pat_maya/twin", headers=bearer(token_factory()))
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "authentication_required"


def test_bearer_scheme_is_required(prod):
    client, _ = prod
    token = make_token()
    for header in ({"Authorization": token}, {"Authorization": f"Basic {token}"}, {}):
        response = client.get("/api/v1/patients/pat_maya/twin", headers=header)
        assert response.status_code == 401


def test_logout_revokes_the_token(prod):
    client, _ = prod
    token = make_token(subject="subject-patient", jti="jti-logout")
    assert client.get("/api/v1/auth/session", headers=bearer(token)).status_code == 200
    logout = client.post("/api/v1/auth/logout", headers=bearer(token))
    assert logout.status_code == 200, logout.text
    assert logout.json()["revoked"] is True
    assert client.get("/api/v1/auth/session", headers=bearer(token)).status_code == 401


def test_patient_isolation_and_caregiver_consent(prod):
    client, _ = prod
    patient = make_token(subject="subject-patient")
    assert client.get("/api/v1/patients/pat_maya/twin", headers=bearer(patient)).status_code == 200
    # A clinician account with no care relationship cannot read this patient.
    outsider = make_token(subject="subject-outsider")
    denied = client.get("/api/v1/patients/pat_maya/twin", headers=bearer(outsider))
    assert denied.status_code == 403
    # Active caregiver consent allows access; revoked consent does not.
    caregiver = make_token(subject="subject-caregiver")
    assert client.get("/api/v1/patients/pat_maya/twin", headers=bearer(caregiver)).status_code == 200
    revoked = make_token(subject="subject-revoked")
    assert client.get("/api/v1/patients/pat_maya/twin", headers=bearer(revoked)).status_code == 403
    # Changing the patient id in the URL does not grant anything.
    assert (
        client.get("/api/v1/patients/pat_unknown/twin", headers=bearer(patient)).status_code
        == 404
    )


def test_role_claims_from_the_token_cannot_escalate(prod):
    client, _ = prod
    escalated = make_token(
        subject="subject-patient", role="clinician", scopes=["*"], scope="admin"
    )
    response = client.post(
        "/api/v1/patients/pat_maya/monitoring/run", headers=bearer(escalated)
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"


def test_auth_events_are_recorded_without_tokens(prod):
    client, db = prod
    token = make_token(exp_delta=-3600, jti="jti-expired-event")
    client.get("/api/v1/patients/pat_maya/twin", headers=bearer(token))
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT * FROM auth_events").fetchall()
        columns = [description[0] for description in conn.execute("SELECT * FROM auth_events").description]
    finally:
        conn.close()
    assert rows, "a rejected token must be recorded as a security event"
    serialized = json.dumps([dict(zip(columns, row)) for row in rows])
    assert token not in serialized
    assert "Authorization" not in serialized
    assert any("token_rejected" in str(row) for row in rows)


def test_identity_tables_and_isolation_from_the_demo_database(prod):
    client, db = prod
    assert db.resolve() != DEMO_DB.resolve()
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        conn.close()
    assert {"identity_links", "auth_revocations", "auth_events"} <= tables
    assert foreign_keys == 1
    demo_documents = sqlite3.connect(f"file:{DEMO_DB.as_posix()}?mode=ro", uri=True)
    try:
        count = demo_documents.execute("SELECT COUNT(*) FROM medical_documents").fetchone()[0]
    finally:
        demo_documents.close()
    assert count == 246, "tests must never modify the persistent demo database"
