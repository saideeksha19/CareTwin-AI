# CareTwin AI — security posture

This file separates what is **implemented and tested in this worktree** from what is
**partially implemented** and what is still required for a real clinical deployment.
Nothing here is a certification claim. CareTwin is not HIPAA compliant, not
GDPR certified, and not clinically validated without qualified review.

## 1. Implemented and tested

| Control | Where | Test |
| --- | --- | --- |
| Per-request identity resolution | `app/deps.py`, `app/services/auth.py` | `test_security.py` |
| OIDC token verification (signature, issuer, audience, expiry, revocation) | `app/auth/` | `test_auth_boundary.py` |
| Demo/production separation (demo header rejected in production) | `app/deps.py`, `app/config.py` | `test_auth_boundary.py` |
| Server-side identity linking, roles never read from token claims | `identity_links`, `app/auth/identity.py` | `test_auth_boundary.py` |
| Authorization Code + PKCE with state, nonce and replay protection | `app/auth/oidc_flow.py` | `test_auth_sessions.py` |
| HttpOnly server sessions, idle/absolute expiry, CSRF double-submit | `app/auth/sessions.py` | `test_auth_sessions.py` |
| Session listing and per-session/account-wide revocation | `auth_sessions`, `api/v1.py` | `test_auth_sessions.py` |
| Role + relationship + consent scoping | `app/services/auth.py` | `test_security.py`, `verify_intelligence.py` |
| Patient isolation / cross-patient denial | repository queries keyed by `patient_id` | `test_security.py`, e2e |
| Revoked caregiver denial (403) | `auth.effective_scopes` | `test_security.py`, `verify_intelligence.py` |
| Clinician-only verification paths | `require_clinician` | `verify_intelligence.py` |
| Assistant restricted to patient/clinician | `api/v1.py` | `test_security.py` |
| Document signature (magic byte) validation | `document_storage.validate_upload` | `test_security.py` |
| Upload size cap + extension/MIME consistency | `document_storage.validate_upload` | `test_security.py` |
| Upload rate limit per account | `app/safety/rate_limit.py` | `test_security.py` |
| Assistant rate limit per account | `app/safety/rate_limit.py` | `test_security.py` |
| AI provider request budget | `AiService._check_rate_limit` | `test_ai_layer.py` |
| Untrusted-document prompt containment + redaction | `prompt_guard.py` | `test_ai_layer.py` |
| Model-output evidence validation | `validate_document_explanation` | `test_ai_layer.py` |
| Server-side API key only | `config.py`, never serialized | `test_ai_layer.py`, `test_security.py` |
| No provider env-var names or `configKey` hints in client code or API responses | `web/src`, `ai/service.py` | `test_ai_layer.py` |
| Security headers (nosniff, DENY framing, CSP, referrer, permissions) | `main.py` middleware | `test_security.py` |
| `Cache-Control: no-store` on personalised API data | `main.py` middleware | `test_security.py` |
| CORS origin allow-list | `main.py` | `test_security.py` |
| Structured errors without stack traces | `main.py` handlers | `test_security.py` |
| Audit trail for AI, injection, review, access to originals | `audit_events` | `test_ai_layer.py`, `verify_intelligence.py` |
| Original-file responses marked `private, no-store` | `api/v1.py` | manual/e2e |
| Database file gitignored, tests use isolated temp DBs | `.gitignore`, test helpers | `test_documents.py` |

## 2. Partially implemented

- **Identity**: `X-Demo-User-Id` is a demonstration header. It is resolved against the
  seeded user table and every route still enforces relationship + consent, so it is not
  a bypass, but it is **not authentication** — anyone can assert any seeded identity.
- **Session handling**: there are no sessions, cookies, tokens, expiry or revocation.
- **Rate limiting**: in-memory and per-process. A multi-worker deployment needs a shared
  store or an edge limiter.
- **Secrets**: `GEMINI_API_KEY` is read from the server environment/`.env`; there is no
  secret manager or rotation policy.
- **Backups**: SQLite file backups are possible but not automated or verified.
- **Upload scanning**: file type is validated by signature, but there is no malware
  scanning and PDF/OCR parsing runs in-process.
- **Model governance**: the model id is operator-configurable; **no genuine Gemini
  request has been live-verified in this checkout** (no key). Provider data retention,
  training opt-outs and audit export require a configured account and agreement.

## 3. Required before any production/clinical use

1. Replace the demo header with an OIDC/SAML identity provider, server-side sessions
   (HttpOnly, Secure, SameSite), MFA for clinician accounts, session expiry and
   revocation, and a password policy (or no passwords at all).
2. Add patient-level authorization checks tied to the authenticated subject rather than
   to a header, and audit every read of PHI.
3. Add consent enforcement at the storage layer, including time-bound consent and
   revocation propagation to open sessions.
4. Move rate limiting, upload scanning (AV/CDR), and WAF rules to shared infrastructure.
5. Encrypt the database at rest and in transit, add key management/rotation, and
   implement tested backup + restore with an RPO/RTO target.
6. Add breach detection, centralized audit retention, and log redaction review.
7. Complete a HIPAA/GDPR assessment, DPIA, and a security review/pen test.
8. Obtain clinical safety review of any generated explanation before it is shown to
   patients, and keep the deterministic path as the default.
9. Configure provider data retention/training opt-outs and a zero-retention agreement.
10. Pin dependencies, add SBOM generation, and run dependency scanning in CI.

Do not describe this application as compliant with any regulation until the items above
have been completed and independently verified.

## Phase 17.1 closure note (local)

- **Python dependencies (remediated, verified):** `cryptography==50.0.0`, `pytest==9.0.3` in app environment; `apps/api/requirements.txt` updated (`cryptography>=46.0.7,<51`, `pytest>=9.0.3,<10`). Backend 101 passed/3 skipped; intelligence 65/65 twice.
- **Frontend dependencies (unresolved):** `npm audit --omit=dev` reports bundled `postcss@8.4.31` in `next@15.5.29` (GHSA-qx2v-qp2m-jg93, GHSA-6g55-p6wh-862q, GHSA-fxqj-rqcc-2cmp, GHSA-r28c-9q8g-f849). Fix path requires breaking `next@16.4.6`; no safe non-breaking remediation applied.
- **E2E isolation fix:** `scripts/e2e-api-server.mjs` now isolates `CARETWIN_DOCUMENT_STORAGE_PATH` to `data/e2e/documents` to prevent demo storage leakage.
- **Gates (controlled rerun):** typecheck/lint pass, fresh production build pass, Playwright 7/7 pass. Demo DB unchanged (246/938/674/72/0/4/1); storage 83 files including 2 orphan e2e PDFs from pre-fix run (not removed).
- **Still external/blocked:** real IdP SSO, genuine Gemini, shared stores/cloud infra/HTTPS/KMS/DR, universal primary doc-at-rest encryption, formal pentest/compliance validation.
