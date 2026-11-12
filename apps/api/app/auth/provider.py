"""Provider-independent OpenID Connect verification.

The provider is configuration, not a vendor choice: any OIDC issuer exposing a
JWKS endpoint and standard claims works. Tests inject a static key set; a real
deployment supplies the issuer, audience and JWKS URL.
"""

from __future__ import annotations

from typing import Any, Callable

from app.auth.jwks import JwksCache
from app.auth.tokens import VerifiedIdentity, verify_token


class OidcIdentityProvider:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: tuple[str, ...] = ("RS256", "RS384", "RS512", "ES256"),
        leeway_seconds: int = 60,
        keys: dict[str, Any] | None = None,
        jwks: JwksCache | None = None,
    ) -> None:
        if not issuer or not audience:
            raise ValueError("An OIDC issuer and audience are required.")
        self.issuer = issuer
        self.audience = audience
        self.algorithms = tuple(algorithms)
        self.leeway_seconds = leeway_seconds
        self._keys = keys
        self._jwks = jwks

    def verify(
        self, token: str, *, revoked: Callable[[str], bool] | None = None
    ) -> VerifiedIdentity:
        keys = self._keys if self._keys is not None else self._jwks.keys()  # type: ignore[union-attr]
        return verify_token(
            token,
            keys=keys,
            issuer=self.issuer,
            audience=self.audience,
            algorithms=self.algorithms,
            leeway_seconds=self.leeway_seconds,
            revoked=revoked,
        )
