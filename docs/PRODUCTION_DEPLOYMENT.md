# Production Deployment (Phase 15)

## Status
This document describes production configuration and operational expectations. CareTwin is **not deployed to an external production environment** in this phase; no cloud accounts were created and no external services were provisioned. Items depending on external infrastructure are explicitly marked as not live-verified.

## Runtime and architecture
- **API:** FastAPI app (`app.main:create_app`), SQLite local/demo runtime verified; PostgreSQL recommended for production (see `docs/DATABASE_ARCHITECTURE.md`) but not live-verified here.
- **Web:** Next.js frontend (`apps/web`). Production hosting, TLS termination, CDN, and trusted proxy configuration are infrastructure responsibilities.
- **State:** Database + private document storage + optional AI provider. Keep backups encrypted and access-controlled.

## Environment and configuration validation
- Configuration loads from process environment (optional local `.env` supported for development; `.env` must never be committed and is ignored by frontend builds).
- `CARETWIN_AUTH_MODE=production` fails closed without required OIDC settings (`CARETWIN_AUTH_ISSUER`, `CARETWIN_AUTH_AUDIENCE`, `CARETWIN_AUTH_JWKS_URL`) and never accepts demo identity headers.
- Production cookie/session hardening: `CARETWIN_AUTH_COOKIE_SECURE` defaults to true in production mode; use HTTPS-only cookies, `SameSite` as configured, HttpOnly session cookies, and CSRF protection for state-changing browser requests.
- `Settings.production_config_issues()` reports locally detectable production concerns (e.g. required document encryption key missing when `CARETWIN_REQUIRE_DOCUMENT_ENCRYPTION=true`). PostgreSQL/object storage/shared stores/monitoring backends require external validation and are documented as dependencies, not silently assumed.
- Startup errors for missing mandatory auth settings are explicit and fail closed; do not weaken them for convenience.

## HTTPS, trusted proxies, and CORS
- **HTTPS:** required in production for all browser and API traffic; terminate TLS at a trusted ingress/load balancer or the app server. Secure cookies require HTTPS.
- **Trusted proxies:** if running behind a proxy, configure trusted proxy headers/forwarded IP handling at the deployment layer; do not trust arbitrary `X-Forwarded-*` headers from the public internet.
- **CORS:** restrict `CARETWIN_CORS_ORIGINS` to exact trusted frontend origins. Credentials/cookies are enabled only in production auth mode as configured; do not use wildcard origins with credentials.

## Database, storage, encryption, backups
- **Database:** set `CARETWIN_DATABASE_BACKEND`/`CARETWIN_DATABASE_URL` for the target environment; SQLite is for local/dev/demo only. Use managed PostgreSQL, migrations, pooling, TLS, least privilege, and PITR in production (external, not live-verified).
- **Storage:** `CARETWIN_STORAGE_BACKEND=local` with private filesystem is implemented locally. Production object storage must be **private** (no public buckets/URLs), use least-privilege credentials, server-side or application-level encryption as appropriate, and short-lived authorized access only (adapter strategy documented; not live-verified).
- **Encryption:** configure `CARETWIN_DOCUMENT_ENCRYPTION_KEY`/`CARETWIN_REQUIRE_DOCUMENT_ENCRYPTION` and `CARETWIN_BACKUP_ENCRYPTION_KEY` via secret management; never hardcode or log keys. See `docs/STORAGE_SECURITY.md`.
- **Backups:** schedule encrypted, verified backups of DB and documents with tested restore drills; configure retention (`CARETWIN_BACKUP_RETENTION_COUNT`) operationally. See `docs/BACKUP_AND_RECOVERY.md`.

## Health, readiness, and monitoring
- `GET /api/v1/health`: liveness-oriented status with safe component summaries (database/storage/auth/AI state). No credentials, internal filesystem paths, patient data, or secrets.
- `GET /api/v1/ready`: readiness-style checks including DB/storage reachability and configuration issue reporting; AI/auth provider live availability is reported but external provider reachability depends on environment.
- Structured logging includes request correlation IDs (`X-Request-ID` middleware) and application events; avoid logging PHI, tokens, secrets, or raw document contents. External log aggregation/metrics/alerting/SIEM are deployment concerns (**not live-verified**).

## Rate limiting and abuse protection
- In-memory sliding-window limits are enforced per process for uploads, assistant requests, and AI-sensitive flows. **Distributed rate limiting** requires a shared store (e.g. Redis) and is adapter-ready in configuration but **not operational/live-verified** without a real shared store.
- Apply edge/WAF/rate limits for authentication and upload endpoints in production.

## Graceful startup and shutdown
- FastAPI lifespan initializes paths/DB and seeds demo data only when configured; production auth configuration fails fast on missing mandatory issuer/audience/JWKS.
- Shutdown closes resources cleanly; ensure in-flight requests complete per platform settings. Use readiness probes to drain traffic before termination.

## Example deployment checklist (non-exhaustive)
- [ ] HTTPS everywhere; HSTS at edge as appropriate.
- [ ] Real OIDC provider configured and tested (owner action).
- [ ] PostgreSQL provisioned, migrated, backed up, and monitored.
- [ ] Private object storage configured; no public document access.
- [ ] Encryption keys in secret manager; rotation plan documented.
- [ ] Encrypted backups verified with restore drills.
- [ ] Shared rate-limit store deployed and tested.
- [ ] Log/metric/alert pipeline configured without PHI leakage.
- [ ] CORS restricted; demo mode disabled in production.
- [ ] Incident/runbook and on-call procedures defined.

No real credentials are included in this repository or its example configuration files.

## Phase 17.1 closure note (local)

- Local release gates re-verified in a controlled pass: backend 101 passed/3 skipped, intelligence 65/65 twice, typecheck/lint pass, fresh production build pass, Playwright 7/7 pass (`--workers=1`, sequential).
- Python app/test deps remediated (`cryptography 50.0.0`, `pytest 9.0.3`); frontend `next/postcss` advisory remains unresolved without breaking Next 16 upgrade.
- Run gates sequentially on constrained machines with D: temp/caches and no parallel builds/tests. `scripts/e2e-api-server.mjs` isolates e2e DB and document storage.
- Production deployment remains blocked on external configuration/validation (IdP, secrets, HTTPS/ingress, managed DB/object storage, monitoring, DR, dependency upgrade validation).
