# CareTwin AI — identity provider comparison

**Decision status: none selected.** No account has been created and no provider
credentials exist. This document compares options against the implemented,
provider-independent OIDC boundary (`apps/api/app/auth/`) and the FastAPI + Next.js
architecture. Choosing a provider is a product/security decision reserved for the owner.

Evaluation basis: the boundary already verifies asymmetric ID tokens (RS256/384/512,
ES256) against issuer, audience, JWKS, expiry and revocation, and now supports the
authorization-code flow with PKCE and server-side sessions. A provider must therefore
be a standard OIDC issuer with a JWKS endpoint.

| Criterion | Auth0 | Microsoft Entra ID | Keycloak |
| --- | --- | --- | --- |
| OIDC compatibility | Full, standards-based | Full (v2.0 endpoints) | Full, reference implementation |
| JWKS endpoint | Yes | Yes | Yes |
| Authorization Code + PKCE | Yes | Yes | Yes |
| MFA | Built-in (TOTP, WebAuthn, push) | Built-in + Conditional Access | Built-in (TOTP, WebAuthn) |
| Refresh tokens | Yes, rotation supported | Yes | Yes, rotation and offline tokens |
| Session revocation | Dashboard/Management API | Revoke sign-in sessions | Admin console/API, per-user session revocation |
| Account management | Hosted Universal Login, self-service | Entra admin center | Self-hosted, full control |
| Developer setup effort | Low (hosted tenant) | Medium (tenant + app registration + consent) | High (deploy, realm, client, database) |
| Deployment requirement | SaaS only | SaaS (Azure) | Self-hosted (container + database) or managed |
| Cost model | Per-MAU tiering; free tier limited | Per-user licensing tiers | Open source; infrastructure cost only |
| Data residency control | Vendor regions | Azure regions | Wherever you run it |
| Best fit here | Fastest managed path for a small team | Organisations already on Microsoft 365 | Teams that need self-hosting/data control |

## Recommendation

**Keycloak** is the best fit for this project's stated direction (self-hosted,
provider-independent, synthetic demo today, no vendor lock-in): open source, complete
OIDC/PKCE/MFA/refresh/revocation support, no per-user cost, and it exercises exactly the
issuer + JWKS + audience contract the boundary already implements.

**Choose Auth0 instead** if the priority is the fastest managed setup and per-MAU pricing
is acceptable. **Choose Entra ID** if CareTwin will live inside an existing Microsoft
estate and Conditional Access policies are mandatory.

## Required decision from the owner

1. Pick one provider (or a different OIDC issuer).
2. Create the application registration with:
   - Redirect URI exactly `https://<host>/api/v1/auth/callback` (plus the local
     development URI if used),
   - Authorization Code flow + PKCE (S256), public client unless a secret is stored
     server-side,
   - Scopes `openid profile email`,
   - Short access-token lifetime and refresh rotation if refresh is enabled,
   - MFA policy for clinician accounts.
3. Supply these server-only values (never in chat, never in source):
   `CARETWIN_AUTH_ISSUER`, `CARETWIN_AUTH_AUDIENCE`, `CARETWIN_AUTH_JWKS_URL`,
   `CARETWIN_AUTH_CLIENT_ID`, optionally `CARETWIN_AUTH_CLIENT_SECRET`, and
   `CARETWIN_AUTH_REDIRECT_URI`.
4. Link each provider subject to a local account through `identity_links` before first
   sign-in; unlinked identities are denied by design.

Everything up to and including the token exchange, ID-token verification, session
creation, CSRF protection and revocation is implemented and tested with a mocked
provider. A real round-trip is **not executed** until step 1–3 happen.
