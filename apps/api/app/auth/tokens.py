"""JWT verification for OpenID Connect tokens.

Only asymmetric algorithms are accepted: nothing here trusts a browser-supplied
algorithm or a shared secret. Claim validation covers issuer, audience, expiry,
not-before, issued-at and revocation. Internal failure codes are intentionally
coarse and are never echoed to the client verbatim.
"""

from __future__ import annotations

import base64
import binascii
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding


class TokenError(Exception):
    """A verification failure described by a short internal reason code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    issuer: str
    audience: tuple[str, ...]
    expires_at: int
    issued_at: int | None
    jti: str | None
    claims: dict[str, Any]


_HASHES: dict[str, type[hashes.HashAlgorithm]] = {
    "RS256": hashes.SHA256,
    "RS384": hashes.SHA384,
    "RS512": hashes.SHA512,
}


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * ((-len(segment)) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError) as exc:
        raise TokenError("malformed") from exc


def _segment_json(segment: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_b64url_decode(segment))
    except (ValueError, TypeError) as exc:
        raise TokenError("malformed") from exc
    if not isinstance(parsed, dict):
        raise TokenError("malformed")
    return parsed


def split_token(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = (token or "").split(".")
    if len(parts) != 3 or not all(parts):
        raise TokenError("malformed")
    header = _segment_json(parts[0])
    payload = _segment_json(parts[1])
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    signature = _b64url_decode(parts[2])
    return header, payload, signing_input, signature


def _verify_signature(
    key: Any, alg: str, signing_input: bytes, signature: bytes
) -> None:
    try:
        if alg in _HASHES:
            key.verify(signature, signing_input, padding.PKCS1v15(), _HASHES[alg]())
        elif alg == "ES256":
            key.verify(signature, signing_input, ec.ECDSA(hashes.SHA256()))
        else:
            raise TokenError("unsupported_alg")
    except InvalidSignature as exc:
        raise TokenError("invalid_signature") from exc
    except (ValueError, TypeError) as exc:
        raise TokenError("invalid_signature") from exc


def verify_token(
    token: str,
    *,
    keys: dict[str, Any],
    issuer: str,
    audience: str,
    algorithms: tuple[str, ...],
    leeway_seconds: int = 60,
    revoked: Callable[[str], bool] | None = None,
    now: int | None = None,
) -> VerifiedIdentity:
    """Verify a JWT and return the trusted identity it carries."""
    header, payload, signing_input, signature = split_token(token)

    alg = header.get("alg")
    if not isinstance(alg, str) or alg not in algorithms:
        raise TokenError("unsupported_alg")

    kid = header.get("kid")
    key = keys.get(kid) if isinstance(kid, str) else None
    if key is None:
        raise TokenError("unknown_key")
    _verify_signature(key, alg, signing_input, signature)

    current = int(time.time()) if now is None else int(now)
    leeway = max(0, int(leeway_seconds))

    if payload.get("iss") != issuer:
        raise TokenError("wrong_issuer")

    aud_claim = payload.get("aud")
    audiences = tuple(aud_claim) if isinstance(aud_claim, list) else (aud_claim,)
    if audience not in [item for item in audiences if isinstance(item, str)]:
        raise TokenError("wrong_audience")

    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise TokenError("missing_expiry")
    if current > int(exp) + leeway:
        raise TokenError("expired")

    nbf = payload.get("nbf")
    if isinstance(nbf, (int, float)) and current + leeway < int(nbf):
        raise TokenError("not_yet_valid")
    iat = payload.get("iat")
    if isinstance(iat, (int, float)) and current + leeway < int(iat):
        raise TokenError("issued_in_future")

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise TokenError("missing_subject")

    jti = payload.get("jti") if isinstance(payload.get("jti"), str) else None
    if jti and revoked is not None and revoked(jti):
        raise TokenError("revoked")

    return VerifiedIdentity(
        subject=subject.strip(),
        issuer=issuer,
        audience=audiences,
        expires_at=int(exp),
        issued_at=int(iat) if isinstance(iat, (int, float)) else None,
        jti=jti,
        claims=payload,
    )
