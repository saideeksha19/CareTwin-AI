# CareTwin AI — authentication architecture

**Status:** a provider-independent OpenID Connect (OIDC) verification boundary is
implemented and tested with a static key set. **No identity provider has been
selected or configured.** Production mode fails closed until an issuer, audience and
JWKS URL are supplied, and no real token has ever been verified in this checkout.

Nothing here is a compliance claim. CareTwin is not HIPAA/GDPR certified and is not
clinically validated; see `SECURITY.md`.

## 1. What existed before Phase 12

- `X-Demo-User-Id` header resolved against the seeded `users` table (`deps.current_user`).
- Every route then enforced relationship + consent scoping in `services/auth.py`, so the
  header was a *demo identity*, not an authorization bypass — but anyone could assert any
  seeded identity, and there were no sessions, tokens or expiry.
- The frontend stored the chosen demo user id in `localStorage` and attached the header.

## 2. Implemented boundary

| Layer | Module | Behaviour |
| --- | --- | --- |
| Mode separation | `config.Settings.auth_mode`, `deps.current_user` | `demo` accepts the synthetic header; `production` **never** reads it. |
| Token verification | `app/auth/tokens.py` | RS256/RS384/RS512/ES256 only; rejects `none`, unknown `kid`, bad signature, wrong `iss`/`aud`, expired, not-yet-valid, missing `sub`. |
| Key source | `app/auth/jwks.py` | Server-configured JWKS URL, bounded in-memory cache; unreachable or malformed keys fail the request. |
| Provider | `app/auth/provider.py` | `OidcIdentityProvider` composes verification; no vendor-specific code. |
| Identity mapping | `identity_links` table, `app/auth/identity.py` | Verified `iss` + `sub` → local `users.id`; roles always come from local records. |
| Revocation | `auth_revocations` table, `POST /auth/logout` | `jti` revoked on sign-out; every subsequent verification fails. |
| Security events | `auth_events` table | Rejections and sign-outs recorded with a hashed subject, never the token or claims. |
| Introspection | `GET /auth/session` | Returns the resolved local role; demo mode returns `mode: "demo"`. |

### Trust boundaries

1. **Browser → API:** untrusted. Only a signed token is trusted, and only after
   signature and registered-claim checks.
2. **Token claims → local permissions:** untrusted by default. `sub` is a lookup key
   into `identity_links`; `role`, `scope`, patient ids or scopes inside the token are
   ignored (regression-tested).
3. **API → database:** trusted, but every patient-scoped query and route still runs
   `require_access` (relationship + consent + scope), so isolation does not depend on
   the token alone.
4. **API → identity provider JWKS:** trusted transport to the configured URL, cached.

### Token lifecycle

1. A client obtains a token from the (unselected) OIDC provider.
2. The API verifies signature, `iss`, `aud`, `exp`/`nbf`/`iat` (60 s leeway by default).
3. `jti` is checked against `auth_revocations`.
4. The subject is resolved through `identity_links`; no link means a generic 401.
5. Sign-out posts to `/auth/logout`, which stores the `jti` until its expiry.
6. Session expiry is the token `exp`; there is no server-side refresh flow.

## 2a. Browser sign-in: Authorization Code + PKCE

`GET /auth/login` starts a standard OIDC Authorization Code flow with PKCE:

1. A random `state`, single-use `nonce` and PKCE verifier are generated with `secrets`;
   only the SHA-256 hash of the state is stored (`auth_flows`).
2. The state is also set as an HttpOnly `caretwin_oauth_state` cookie, binding the
   response to the browser that started it.
3. The authorization URL carries `response_type=code`, `code_challenge_method=S256`,
   the exact configured `redirect_uri`, scopes and nonce.
4. `GET /auth/callback` rejects a missing/mismatched state cookie, then atomically marks
   the flow used (replay protection, 10-minute expiry), exchanges the code at the
   provider token endpoint with the verifier, verifies the ID token with the existing
   verifier, and compares the nonce.
5. The subject is linked to a local user, a server-side session is created, and the
   browser is redirected to a same-origin path only (open-redirect guarded).

No provider token is written to the browser: the access token response is discarded
and only the opaque session cookie is issued.

## 2b. Server-managed sessions

| Property | Implementation |
| --- | --- |
| Identifier | 32-byte `secrets.token_urlsafe` value; only SHA-256 stored |
| Cookie | HttpOnly, Secure in production, SameSite=Lax, `Path=/`, absolute max-age |
| Expiry | Absolute TTL plus idle timeout; expired rows are revoked on use |
| CSRF | Double-submit token in a readable cookie, required in `X-CSRF-Token` for POST/PUT/PATCH/DELETE on session requests |
| Rotation | A brand-new session id is issued on every sign-in; a pre-set cookie is never adopted |
| Logout | Session row revoked server-side and both cookies cleared |
| Revocation | Per-session (`DELETE /auth/sessions/{id}`) and account-wide (`POST /auth/sessions/revoke-all`) |
| Listing | `GET /auth/sessions` returns only the caller's sessions |
| Audit | `auth.login_succeeded`, `auth.login_failed`, `auth.logout`, `auth.session_revoked`, `auth.sessions_revoked_all` with hashed subject |

Bearer tokens from Phase 12 remain supported for non-browser API clients; CSRF applies
only to cookie-authenticated requests.

## 3. Configuration

| Variable | Meaning | Required |
| --- | --- | --- |
| `CARETWIN_AUTH_MODE` | `demo` (default) or `production` | no |
| `CARETWIN_AUTH_ISSUER` | Exact `iss` claim value | production |
| `CARETWIN_AUTH_AUDIENCE` | Required `aud` value | production |
| `CARETWIN_AUTH_JWKS_URL` | HTTPS JWKS endpoint | production |
| `CARETWIN_AUTH_ALGORITHMS` | Comma list, subset of RS256/384/512, ES256 | no |
| `CARETWIN_AUTH_LEEWAY_SECONDS` | Clock skew allowance (default 60) | no |
| `CARETWIN_AUTH_JWKS_CACHE_SECONDS` | Key cache TTL (default 900) | no |
| `CARETWIN_AUTH_REQUIRE_IDENTITY_LINK` | Must be true outside controlled tests | no |
| `CARETWIN_AUTH_CLIENT_ID` | OIDC client id (enables browser sign-in) | sign-in |
| `CARETWIN_AUTH_CLIENT_SECRET` | Only for a confidential client | no |
| `CARETWIN_AUTH_REDIRECT_URI` | Exact registered callback URL | sign-in |
| `CARETWIN_AUTH_POST_LOGIN_REDIRECT` | Same-origin path after sign-in (default `/workspace`) | no |
| `CARETWIN_AUTH_SESSION_TTL_SECONDS` | Absolute session lifetime (default 28800) | no |
| `CARETWIN_AUTH_SESSION_IDLE_SECONDS` | Idle timeout (default 3600) | no |
| `CARETWIN_AUTH_COOKIE_SECURE` | Secure cookie flag (default true in production) | no |
| `CARETWIN_AUTH_REQUIRED_AMR` | Required `amr` methods, e.g. `mfa` | no |
| `NEXT_PUBLIC_AUTH_MODE` | Frontend mirror of the mode (production uses cookie sessions) | no |

`create_app` raises at startup if production mode is missing issuer, audience or JWKS
URL. It never silently falls back to demo identity.

## 4. Identity linking (migration strategy)

`identity_links` is additive; no existing table is altered and no demo row is touched.

1. Provider administrator creates the account and supplies the stable `sub`.
2. An operator links it server-side, for example:
   `INSERT INTO identity_links (id, issuer, subject, user_id, created_at) VALUES ('idn_...', '<issuer>', '<sub>', 'usr_...', '<timestamp>');`
3. The user signs in and the API resolves their existing local role and relationships.

Until a link exists the request is rejected with a generic 401 — there is no
auto-provisioning and no self-service role assignment.

## 5. Provider decision still required

Choosing an identity provider is a product/security decision, not a code decision.
The boundary accepts any OIDC issuer that exposes a JWKS endpoint. Before going live:

1. Select the provider and register the application (authorization code + PKCE).
2. Set the four `CARETWIN_AUTH_*` values (production) in the server environment.
3. Add the provider's callback URL to the frontend sign-in page and store the token
   via `setAccessToken()` from `apps/web/src/lib/auth.ts`.
4. Decide token lifetime, refresh strategy and whether to move the token to an
   HttpOnly cookie with CSRF protection (recommended for browser sessions).
5. Verify one real sign-in, expiry and revocation against the chosen issuer.

## 6. MFA

MFA is enforced by the identity provider, not by a CareTwin screen. Set
`CARETWIN_AUTH_REQUIRED_AMR` (for example `mfa`) to reject any ID token whose `amr`
claim does not include the required method; the flow then fails with a generic sign-in
error. No decorative MFA UI exists, and no test claims MFA succeeded without a real
token that carries the claim.

## 7. Known limitations

- No live provider has been configured; only injected-key flows are exercised.
- No refresh-token flow: sessions end at the absolute/idle timeout; provider tokens are
  not stored, so there is nothing to rotate or reuse.
- No account self-service or auto-provisioning; linking is an operator action.
- Local account-wide revocation exists; provider-side session revocation is not called.
- `auth_events` is not yet surfaced in the UI or exported to a SIEM.
