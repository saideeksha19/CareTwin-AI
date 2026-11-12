"""Identity resolution and security-event recording.

A verified token subject is not a CareTwin account by itself. It is linked to a
local user through the server-side ``identity_links`` table, so roles always come
from trusted local records and never from a browser-supplied claim.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.auth.tokens import VerifiedIdentity
from app.errors import unauthorized
from app.repositories.store import Store
from app.utils import iso, new_id

AUTHENTICATION_REQUIRED = "A valid access token is required."


def bearer_token(authorization: str | None) -> str:
    """Extract a bearer token without ever echoing it back to the caller."""
    scheme, _, credentials = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise unauthorized(AUTHENTICATION_REQUIRED)
    return credentials.strip()


def _subject_hash(identity: VerifiedIdentity) -> str:
    return hashlib.sha256(f"{identity.issuer}|{identity.subject}".encode()).hexdigest()[:24]


def record_auth_event(
    store: Store,
    *,
    event: str,
    outcome: str,
    identity: VerifiedIdentity | None = None,
    user_id: str | None = None,
    reason: str = "",
) -> None:
    """Persist an authentication event without tokens, claims or medical data."""
    store.record_auth_event(
        {
            "id": new_id("aev"),
            "event": event,
            "outcome": outcome,
            "user_id": user_id,
            "issuer": identity.issuer if identity else "",
            "subject_hash": _subject_hash(identity) if identity else "",
            "reason": reason[:120],
            "occurred_at": iso(),
        }
    )
    store.conn.commit()


def resolve_identity(
    store: Store,
    identity: VerifiedIdentity,
    *,
    require_link: bool = True,
) -> dict[str, Any]:
    """Resolve a verified subject to a local user using server-side records."""
    link = store.get_identity_link(identity.issuer, identity.subject)
    if link:
        user = store.get_user(link["user_id"])
    elif not require_link:
        # Explicit opt-out for controlled environments; never browser-controlled.
        user = store.get_user(identity.subject)
    else:
        user = None
    if not user:
        record_auth_event(
            store,
            event="auth.identity_rejected",
            outcome="denied",
            identity=identity,
            reason="no_linked_account",
        )
        raise unauthorized("This identity is not linked to a CareTwin account.")
    return user
