"""JWKS retrieval and caching.

The key set URL is server configuration. Fetched keys are cached in memory for a
bounded time; an unreachable or malformed key set fails the authentication attempt
instead of falling back to an unverified path.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app.auth.tokens import TokenError


def _b64_int(value: str) -> int:
    import base64

    padded = value + "=" * ((-len(value)) % 4)
    try:
        return int.from_bytes(base64.urlsafe_b64decode(padded.encode("ascii")), "big")
    except (ValueError, TypeError) as exc:
        raise TokenError("malformed_jwks") from exc


def jwk_to_public_key(jwk: dict[str, Any]) -> Any:
    """Convert a supported JWK into a cryptography public key object."""
    kty = jwk.get("kty")
    try:
        if kty == "RSA" and jwk.get("n") and jwk.get("e"):
            return rsa.RSAPublicNumbers(_b64_int(jwk["e"]), _b64_int(jwk["n"])).public_key()
        if kty == "EC" and jwk.get("crv") == "P-256" and jwk.get("x") and jwk.get("y"):
            return ec.EllipticCurvePublicNumbers(
                _b64_int(jwk["x"]), _b64_int(jwk["y"]), ec.SECP256R1()
            ).public_key()
    except (ValueError, TypeError) as exc:
        raise TokenError("malformed_jwks") from exc
    raise TokenError("unsupported_jwk")


class JwksCache:
    """Cached, server-side JWKS client."""

    def __init__(
        self,
        url: str,
        *,
        ttl_seconds: int = 900,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.url = url
        self.ttl_seconds = max(30, int(ttl_seconds))
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=10.0))
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0

    def keys(self) -> dict[str, Any]:
        if self._keys and (time.monotonic() - self._fetched_at) < self.ttl_seconds:
            return self._keys
        try:
            with self._client_factory() as client:
                response = client.get(self.url)
            if response.status_code != 200:
                raise TokenError("jwks_unavailable")
            body = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise TokenError("jwks_unavailable") from exc

        entries = (body or {}).get("keys") if isinstance(body, dict) else None
        if not isinstance(entries, list) or not entries:
            raise TokenError("jwks_unavailable")
        keys: dict[str, Any] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            kid = entry.get("kid")
            if not isinstance(kid, str) or not kid:
                continue
            try:
                keys[kid] = jwk_to_public_key(entry)
            except TokenError:
                continue
        if not keys:
            raise TokenError("jwks_unavailable")
        self._keys = keys
        self._fetched_at = time.monotonic()
        return keys
