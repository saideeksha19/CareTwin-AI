"""OpenID Connect Authorization Code flow with PKCE.

Provider-independent: the issuer, client id and redirect URI are configuration.
The flow stores a hashed state, a single-use nonce and the PKCE verifier server-side,
consumes the state atomically (replay protection), exchanges the code at the
provider's token endpoint, verifies the ID token with the existing verifier, and
compares the nonce. No provider token is ever stored in the browser session.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlencode

import httpx

from app.auth.tokens import TokenError


class OidcFlowError(Exception):
    """Short internal reason code; never returned to the browser verbatim."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class OidcFlowConfig:
    issuer: str
    client_id: str
    redirect_uri: str
    post_login_redirect: str = "/workspace"
    client_secret: str = ""
    scopes: tuple[str, ...] = ("openid", "profile", "email")
    flow_ttl_seconds: int = 600
    required_amr: tuple[str, ...] = ()


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class OidcFlow:
    def __init__(
        self,
        config: OidcFlowConfig,
        *,
        provider,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=15.0))
        self._metadata: dict[str, Any] | None = None
        self._metadata_at = 0.0

    # ------------------------------------------------------------ discovery
    def metadata(self) -> dict[str, Any]:
        if self._metadata and (time.monotonic() - self._metadata_at) < 900:
            return self._metadata
        url = self.config.issuer.rstrip("/") + "/.well-known/openid-configuration"
        try:
            with self._client_factory() as client:
                response = client.get(url)
            if response.status_code != 200:
                raise OidcFlowError("discovery_failed")
            body = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise OidcFlowError("discovery_failed") from exc
        if not isinstance(body, dict) or body.get("issuer") != self.config.issuer:
            raise OidcFlowError("discovery_failed")
        if not body.get("authorization_endpoint") or not body.get("token_endpoint"):
            raise OidcFlowError("discovery_failed")
        self._metadata = body
        self._metadata_at = time.monotonic()
        return body

    # ---------------------------------------------------------------- start
    def start(self, store) -> tuple[str, str]:
        if not self.config.client_id or not self.config.redirect_uri:
            raise OidcFlowError("not_configured")
        state = _b64url(os.urandom(24))
        nonce = _b64url(os.urandom(24))
        verifier = _b64url(os.urandom(48))
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
        now = int(time.time())
        store.create_auth_flow(
            {
                "state_hash": _token_hash(state),
                "nonce": nonce,
                "code_verifier": verifier,
                "redirect_uri": self.config.redirect_uri,
                "created_at": str(now),
                "expires_at": str(now + max(60, self.config.flow_ttl_seconds)),
                "used_at": None,
            }
        )
        store.conn.commit()
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        metadata = self.metadata()
        return state, f"{metadata['authorization_endpoint']}?{urlencode(params)}"

    # -------------------------------------------------------------- complete
    def complete(self, store, *, code: str, state: str):
        if not code or not state:
            raise OidcFlowError("invalid_response")
        flow = store.get_auth_flow(_token_hash(state))
        if not flow or flow.get("used_at"):
            raise OidcFlowError("invalid_state")
        if int(flow["expires_at"]) < int(time.time()):
            raise OidcFlowError("expired_state")
        if not store.consume_auth_flow(_token_hash(state), str(int(time.time()))):
            raise OidcFlowError("replayed_state")

        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": flow["redirect_uri"],
            "client_id": self.config.client_id,
            "code_verifier": flow["code_verifier"],
        }
        if self.config.client_secret:
            payload["client_secret"] = self.config.client_secret
        try:
            with self._client_factory() as client:
                response = client.post(self.metadata()["token_endpoint"], data=payload)
            if response.status_code != 200:
                raise OidcFlowError("token_exchange_failed")
            body = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise OidcFlowError("token_exchange_failed") from exc
        id_token = body.get("id_token") if isinstance(body, dict) else None
        if not isinstance(id_token, str) or not id_token:
            raise OidcFlowError("missing_id_token")

        try:
            identity = self.provider.verify(id_token)
        except TokenError as exc:
            raise OidcFlowError(f"invalid_id_token:{exc.reason}") from exc

        if identity.claims.get("nonce") != flow["nonce"]:
            raise OidcFlowError("nonce_mismatch")
        if self.config.required_amr:
            methods = set(str(identity.claims.get("amr") or "").split())
            if not set(self.config.required_amr) <= methods:
                raise OidcFlowError("mfa_required")
        return identity
