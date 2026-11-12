# Project State — CareTwin AI

**As of:** 2026-11-11 (Phase 17.1 release-gate closure, local)
**Status:** Locally release-verified demo candidate with documented blockers/limitations.
**Data:** Synthetic only.
**Repository:** `C:\Users\ddsai\Downloads\CareTwin AI` — **no `.git` directory exists**. Git operations are unavailable until a repository is restored or created deliberately.

## What the application is

An evidence-linked recovery twin demo with patient, caregiver and clinician roles;
document upload with pypdf/OCR extraction; deterministic analysis and report
comparison; optional Gemini explanations with server-side grounding validation; a
grounded assistant with deterministic fallback; a rotating 3D Digital Twin; consent
scopes, model-based alert rules and an audit trail.

## Verified in this state (controlled local rerun, Phase 17.1)

| Gate | Result |
| --- | --- |
| Python dependency audit (`pip-audit --path apps/api/.venv/Lib/site-packages`, isolated tool on D:) | **App deps remediated:** `cryptography==50.0.0`, `pytest==9.0.3` (from 45.0.7 / 8.4.2). Tool reported 8 known vulns in **`pip 26.0.1`** (venv tooling, fix 26.2.0) only; no remaining findings reported for remediated app deps in this path audit. Prior isolated `-r requirements.txt` audit completed for app deps before pytest bump but later failed due tool-internal pip-upgrade error — see below. |
| `pytest apps/api/tests -q -p no:cacheprovider` | **101 passed, 3 skipped, 1 warning** |
| `scripts/verify_intelligence.py` (run 1) | **65/65 checks passed**, demo DB unchanged (`246/938/674`) |
| `scripts/verify_intelligence.py` (run 2) | **65/65 checks passed**, demo DB unchanged (`246/938/674`) |
| Web typecheck (`npm run typecheck --workspace @caretwin/web`) | **pass** |
| Web ESLint (`npm run lint --workspace @caretwin/web`) | **no warnings/errors** (`next lint` deprecation notice only) |
| Production build (`npm run build --workspace @caretwin/web`, `NODE_OPTIONS=--max-old-space-size=2048`, temp/caches on D:) | **pass, exit 0** (fresh controlled build, 21/21 static pages; BUILD_ID `D-rscBwNk5_xuEnvMOnms`) |
| Playwright (`npx playwright test tests/e2e/caretwin.spec.ts tests/e2e/phase7.spec.ts --workers=1`) | **7 passed** (1.1m) |
| Frontend dependency audit (`npm audit --omit=dev`) | **2 vulnerabilities remain** (1 high, 1 moderate): bundled `postcss@8.4.31` in `next@15.5.29` (GHSA-qx2v-qp2m-jg93, GHSA-6g55-p6wh-862q, GHSA-fxqj-rqcc-2cmp, GHSA-r28c-9q8g-f849). npm fix path requires breaking `next@16.4.6`; latest 15.5.x still bundles vulnerable postcss. **Unresolved (no safe non-breaking remediation applied).** |
| Local HTTP smoke (demo-safe, isolated uvicorn) | `/health` 200, `/ready` 200 with security headers/CSP/no-store/request-id; anonymous patient access 401 structured/non-leaky; foreign-origin CORS preflight not allowed. |

Coverage highlights (existing): deterministic extraction and citation/page traceability; missing
ranges and unreadable pages stated rather than invented; duplicate detection;
unit-mismatch comparison refusal; conflicting-value arithmetic; assistant gap
admission; prompt-injection detection/redaction and audit; model-output rejection of
unsupported numbers, unknown citations, diagnoses, medication changes and missing
uncertainty; upload signature/size/rate-limit controls; security headers and no-store
caching; role, consent and patient-isolation boundaries.

## Dependency remediation (Phase 17/17.1)

- **Python (applied, verified):** `cryptography` upgraded to `50.0.0` and `pytest` to `9.0.3`; `apps/api/requirements.txt` updated to `cryptography>=46.0.7,<51`, `pytest>=9.0.3,<10`. Targeted and full backend suites pass.
- **Python audit tooling note:** isolated `pip-audit -r apps/api/requirements.txt` initially confirmed app vulns before remediation and later failed in this session with an internal pip-upgrade error in its temp environment (exit 1), so a final clean requirements-file audit run was not completed; venv path audit shows only `pip 26.0.1` tooling advisories.
- **Frontend (unresolved):** `next@15.5.29` bundles `postcss@8.4.31` (vulnerable). `npm audit fix --force` implies breaking Next 16 upgrade; no verified compatible non-breaking fix identified in 15.5.x. No override/major upgrade applied to preserve working app.

## AI provider status

- Model setting: `CARETWIN_AI_MODEL` (default `gemini-3.8-flash`, operator-configurable).
  **Not live-verified in this checkout** (no credentials).
- `GEMINI_API_KEY`: **unset** in the environment and no `.env` file present.
- **Genuine Gemini requests executed: 0.** Provider behaviour is **AUTOMATED TEST VERIFIED**
  with mocked HTTP transports. Deterministic extraction, comparison, records, assistant
  retrieval and the Digital Twin remain fully functional without a key.

## Data state

- Demo database: `data/demo/caretwin.db` (synthetic; gitignored). **Unchanged after Phase 17.1 gates:** documents 246, extractions 938, audit events 674, assistant messages 72, AI explanations 0, users 4, patients 1, auth sessions/flows/events 0.
- Uploaded files: `data/documents/` (synthetic; gitignored). **83 files present** (previously 81). During Phase 17.1 Playwright, the e2e server used an isolated DB but (before fix) the default document storage path, adding 2 orphan PDF files in `data/documents/pat_maya/` (`43b51d41230147969f7802427b5a90b8.pdf`, `4b749d509c15472597b767b922390507.pdf`) with no corresponding demo DB rows. `scripts/e2e-api-server.mjs` was fixed to isolate `CARETWIN_DOCUMENT_STORAGE_PATH` to `data/e2e/documents` and clean it between runs. Existing orphan files were **not deleted** (no destructive cleanup authorized).
- Cleanup tool: `scripts/cleanup_synthetic.py` — dry run only; requires explicit `--confirm`.

## Known limitations / blockers

- Demo header identity in demo mode; no real IdP/session SSO round-trip verified, no MFA/tenant isolation, no live external provider validation.
- In-memory per-process rate limits; SQLite and local files are single-node. PostgreSQL/cloud storage/Redis/shared monitoring/HTTPS/KMS/DR not live-verified.
- Universal primary document-at-rest encryption/migration not fully implemented/verified.
- No malware scanning, no secret manager, no automated backups infrastructure beyond local design/tests.
- Frontend `next/postcss` advisories unresolved without breaking upgrade.
- Extraction/OCR can misread values; nothing is auto-verified. No clinical validation or regulatory clearance; no HIPAA/GDPR certification (see `docs/SECURITY.md`).
- Local verification can be sensitive to C:/memory pressure; gates were rerun sequentially with D: temp/caches.

## Next work (Phase 18 handoff, external/operational)

1. Resolve frontend `next/postcss` advisories via a carefully scoped, fully tested Next upgrade or verified compatible fix.
2. Restore or deliberately create version control.
3. Configure/validate a real identity provider and production auth/session flows.
4. Run genuine Gemini validation with owner-supplied key (never committed/shared).
5. Provision and validate PostgreSQL/object storage/shared rate limiting/monitoring/HTTPS/secret management/DR as required.
6. Independent clinical safety review and formal security assessment as appropriate.
