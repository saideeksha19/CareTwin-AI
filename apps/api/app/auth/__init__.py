"""Provider-independent authentication boundary.

Nothing in this package chooses an identity provider. It verifies OpenID Connect
ID/access tokens against configured issuer, audience, keys and revocation state,
and resolves the verified subject to a local CareTwin user through a server-side
link. Demo identity is a separate mode and is never accepted in production mode.
"""

from app.auth.jwks import JwksCache
from app.auth.provider import OidcIdentityProvider
from app.auth.tokens import TokenError, VerifiedIdentity, verify_token

__all__ = [
    "JwksCache",
    "OidcIdentityProvider",
    "TokenError",
    "VerifiedIdentity",
    "verify_token",
]
