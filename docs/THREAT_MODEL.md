# CareTwin AI — threat model

Scope: the demo worktree and the implemented authentication boundary. This is a
working document, not an audit. No regulatory compliance is claimed.

## Assets

- Synthetic patient records, documents, extractions, comparisons and assistant history.
- Clinician verification state and audit trail.
- The server-side AI provider key and any future identity-provider secrets.
- The integrity of role/consent decisions.

## Actors

| Actor | Trust |
| --- | --- |
| Patient (demo identity or verified token) | authenticated, scoped to their own record |
| Clinician | authenticated, scoped by care relationship |
| Caregiver | authenticated, scoped by relationship ∩ active consent |
| Anonymous browser | untrusted |
| Uploaded document text | hostile data (may contain instructions) |
| Identity provider | trusted for authenticity after signature checks |

## Threats and current controls

| # | Threat | Control | Verified by |
| --- | --- | --- | --- |
| T1 | Anonymous access to patient data | All patient routes require identity; production fails closed without a token | `test_auth_boundary.py`, `test_security.py` |
| T2 | Spoofing another user via a header | Production mode ignores `X-Demo-User-Id` entirely; demo mode is clearly labelled and disabled in production | `test_auth_boundary.py` |
| T3 | Forged or tampered token | Asymmetric signature verification only; `none` and unknown `kid` rejected | `test_auth_boundary.py` |
| T4 | Token replay after sign-out | `jti` revocation checked on every verification | `test_auth_boundary.py` |
| T5 | Expired token reuse | `exp`/`nbf`/`iat` validated with bounded leeway | `test_auth_boundary.py` |
| T6 | Token for another issuer/audience | Exact `iss` and `aud` match | `test_auth_boundary.py` |
| T7 | Cross-patient access by changing the URL | Route-level relationship + consent + scope checks | `test_security.py`, `test_auth_boundary.py` |
| T8 | Role escalation via a token claim | Roles come from `users`/`care_relationships`; token claims ignored | `test_auth_boundary.py` |
| T9 | Revoked caregiver keeps access | Active consent required per request | `test_auth_boundary.py`, `test_security.py` |
| T10 | Prompt injection in a document | Untrusted delimiters, redaction, injection audit, evidence validation | `test_ai_layer.py` |
| T11 | Fabricated medical claims | Numeric/citation/diagnosis/medication-change validation with deterministic fallback | `test_ai_layer.py`, `test_ai_verification_matrix.py` |
| T12 | Key exfiltration through the client | Key read only server-side; no env names or `configKey` in bundles/responses | `test_ai_layer.py` |
| T13 | Credential or PHI leakage in logs | Auth events store a hashed subject; no tokens, headers or medical text logged | `test_auth_boundary.py` |
| T14 | Disk abuse via uploads | Signature validation, size cap, per-account rate limit | `test_security.py` |
| T15 | Provider outage breaks the product | Deterministic paths never depend on the model | `test_ai_layer.py` |
| T16 | Path traversal in stored documents | Resolved-path containment under the storage root | `test_documents.py` |
| T17 | CSRF against a cookie session | Double-submit token required for unsafe methods | `test_auth_sessions.py` |
| T18 | Session fixation / pre-set cookie | Fresh session id on every sign-in; unknown or revoked ids rejected | `test_auth_sessions.py` |
| T19 | Authorization response replay | Single-use hashed state, atomic consume, expiry, nonce check | `test_auth_sessions.py` |
| T20 | Open redirect after sign-in | Post-login target must be a single-slash same-origin path | `test_auth_sessions.py` (flow constant) |
| T21 | Provider token leakage into browser | Access token discarded; only opaque HttpOnly session cookie issued | `test_auth_sessions.py` |

## Residual risks

1. **Demo identity is spoofable by design** — acceptable only for the synthetic demo;
   production mode rejects it.
2. **No live provider validation** — signature logic is exercised with injected keys,
   but a real issuer/JWKS round-trip has not run.
3. **Browser session storage** — HttpOnly cookie with CSRF double-submit; no provider
   token is ever exposed to JavaScript.
4. **Per-token revocation only** — no account-wide revocation or session list.
5. **In-memory rate limits** — reset on restart and not shared across workers.
6. **Single-node persistence** — SQLite and local files; no encryption at rest.
7. **No MFA enforcement** — must be enforced by the chosen provider and tested live.
8. **Clinical risk** — no clinical validation; every generated explanation is
   informational and unverified values remain visibly unverified.
