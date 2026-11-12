# CareTwin AI — evidence-linked recovery twin

**Synthetic-data demo of a document-to-analysis-to-assistant-to-Digital-Twin recovery workflow.**

CareTwin AI connects three roles around one patient record:

- **Patient** — daily check-ins, rotating 3D recovery twin, timeline, medications, follow-ups, alerts, consent, medical documents.
- **Caregiver** — consent-scoped twin/records visibility and attributed observations; AI assistant is not available to caregivers.
- **Clinician** — alert review, extraction verification/rejection, monitoring thresholds, clinical summary and audit trail.

Every clinical fact is tied to a page-level source or shown as awaiting review. Deterministic safety rules, role/consent checks, upload validation and output validation all run on the server. The external model is optional: with no key the product is fully functional and honest about it.

> **Synthetic demo only.** No real patient data. Not a medical device, not regulatory-cleared, not clinically validated, and not for clinical use. Demo identity is a request header, not authentication. See [Security posture](docs/SECURITY.md).

---

## Quick start

### Prerequisites

- Node.js **20.9+** (verified on 22.22.3)
- npm 10+
- Python **3.11+** (verified on 3.14.4)
- Tesseract OCR (optional, only for scanned pages): `C:\Program Files\Tesseract-OCR\tesseract.exe`

### Install

```powershell
cd "C:\Users\ddsai\Downloads\CareTwin AI"
npm install

cd apps\api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\..
```

### Run

```powershell
# Terminal 1 — API on :8000 (creates and seeds data\demo\caretwin.db)
npm run dev:api

# Terminal 2 — web on :3000
npm run dev:web
```

Open <http://localhost:3000>, choose a role at `/demo`, and use the workspace.

Production-style run used by the browser suite:

```powershell
npm run build --workspace @caretwin/web
npm run start --workspace @caretwin/web -- -p 3000 -H 127.0.0.1
```

A full reproducible walkthrough, reset and shutdown instructions live in
**[docs/DEMO.md](docs/DEMO.md)**.

### Reset the demo

```powershell
# Stop the API first
Remove-Item "data\demo\caretwin.db*" -ErrorAction SilentlyContinue
npm run dev:api
```

## Environment configuration

Copy `.env.example` to `.env` in the project root (never commit it) and fill in only
what you need. `.env`, `.env.local`, databases and uploaded documents are gitignored.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Optional. Enables model-written explanations. Server-side only. |
| `CARETWIN_AI_MODEL` | Default `gemini-3.8-flash` (GA, structured outputs). |
| `CARETWIN_AI_REQUESTS_PER_HOUR` | Server-side provider budget (default 40). |
| `CARETWIN_AI_TIMEOUT_SECONDS` | Provider timeout (default 40). |
| `CARETWIN_UPLOAD_REQUESTS_PER_HOUR` | Upload abuse limit per account (default 200). |
| `CARETWIN_ASSISTANT_REQUESTS_PER_HOUR` | Assistant limit per account (default 120). |
| `CARETWIN_CORS_ORIGINS` | Allowed browser origins. |
| `CARETWIN_TESSERACT_CMD` | Explicit Tesseract binary for scanned pages. |

Without a key: `/api/v1/ai/status` reports `not_configured`, `/api/v1/ai/health`
reports `reachable:false`, explanation requests return `503 ai_not_configured`, and the
assistant/UI stay in honest deterministic mode while extraction and records remain
complete. **No genuine Gemini request has been run in this checkout** (key absent).

To enable genuine provider validation locally (never commit or share the key): create a
gitignored `.env` in the project root with `GEMINI_API_KEY=<your key>` and, if needed,
`CARETWIN_AI_MODEL=<a currently supported model>`, restart the API, and confirm only via
`/api/v1/ai/status` and `/api/v1/ai/health` (neither returns the key). See
`docs/AI_ARCHITECTURE.md` for the full validation steps and limitations.

## Demo roles

| Demo user | Role | Access |
| --- | --- | --- |
| Maya Rao (`usr_maya`) | Patient | Full own-twin access, check-ins, documents, consent, assistant |
| Arjun Rao (`usr_arjun`) | Caregiver, consent granted | Shared twin/timeline/schedule/alerts, observations; no assistant |
| Priya Rao (`usr_priya`) | Caregiver, consent revoked | Boundary test: server refuses access |
| Dr. Nandini Iyer (`usr_nandini`) | Clinician | Review, verification, monitoring rules, summary, audit |

Demo identity is sent as `X-Demo-User-Id`. Every route still enforces relationship,
role and consent scopes server-side; the header itself is **not** authentication.

## What is implemented

- **Documents** — PDF/PNG/JPEG/TIFF/WebP upload with signature validation, size limits, duplicate detection, pypdf text extraction, OCR fallback, page-level source viewer, extraction review (verify/reject with clinician attribution) and reprocessing.
- **Deterministic analysis** — values, units and printed reference ranges as written; missing units/ranges surfaced as review flags; unreadable pages stated explicitly; prescription parser (name, dose, frequency, timing, duration, clarifications).
- **Report comparison** — same test and same unit only; arithmetic difference with reasons when not comparable; duplicates and same-date readings excluded.
- **AI explanation panel** — saved/generate/regenerate, model and latency, cached vs fresh, citations with page links, validation failures explained, injection notice, honest unavailable state. Prescription explanations restate written instructions only.
- **AI assistant** — grounded retrieval over the patient's own records with citations, uncertainty and follow-ups; deterministic fallback with an explicit badge when no model is configured or the provider fails.
- **Digital Twin** — rotating 3D anatomical model (WebGL) with drag/zoom/reset/pause and system layers, schematic fallback when WebGL is unavailable; only clinician-verified findings appear as confirmed.
- **Safety & governance** — six deterministic monitoring rules, alert acknowledge/resolve, consent scopes and revocation, audit trail, security headers, per-account rate limits, structured errors.

## API surface

Base path `/api/v1`: health/meta/demo session, twin + snapshots, evidence, timeline,
audit, check-ins, observations, alerts, consent, labs, encounters, monitoring rules,
safety decisions, clinical summary, documents (upload/list/detail/extractions/review/
analysis/explanation/explain/file/reprocess), report comparison, assistant
ask/history, guidance, agents and AI status/health/explain. Interactive schema at
<http://127.0.0.1:8000/docs>.

## Verification

| Gate | Command | Last result (Phase 17.1, controlled local rerun) |
| --- | --- | --- |
| Backend suite | `python -m pytest apps/api/tests -q -p no:cacheprovider` | 101 passed, 3 skipped, 1 warning |
| Intelligence checks | `python scripts/verify_intelligence.py` (run twice) | 65/65 each run (isolated temp DB, demo DB unchanged) |
| TypeScript | `npm run typecheck --workspace @caretwin/web` | pass |
| ESLint | `npm run lint --workspace @caretwin/web` | no warnings/errors |
| Production build | `NODE_OPTIONS=--max-old-space-size=2048` + D: temp, `npm run build --workspace @caretwin/web` | pass (fresh build, exit 0) |
| Browser suite | `npx playwright test tests/e2e/caretwin.spec.ts tests/e2e/phase7.spec.ts --workers=1` | 7 passed |
| Frontend audit | `npm audit --omit=dev` | 2 unresolved vulns in bundled `postcss@8.4.31` via `next@15.5.29` (breaking Next 16 fix path) |
| Python deps | app venv / `requirements.txt` | `cryptography==50.0.0`, `pytest==9.0.3` remediated and verified; `pip-audit` path audit reported only `pip 26.0.1` tooling advisories |

AI provider behaviour (success, cache, 401, 429/quota, 503, timeout, budget, invalid
output) is covered with mocked HTTP transports. **No live Gemini call has been
recorded in this checkout** unless you add your own key; verification status is
reported honestly per run.

## Authentication modes

CareTwin ships two clearly separated identity modes. Neither is a compliance claim.

- **Demo (default).** Synthetic `X-Demo-User-Id` header for the seeded accounts, labelled
  as demo identity in the UI. It is rejected in production mode.
- **Production.** A verified OpenID Connect bearer token is required: signature,
  issuer, audience, expiry and revocation are checked server-side, and the demo header
  is ignored. Startup fails closed if the issuer, audience or JWKS URL is missing.

Enable production mode with `CARETWIN_AUTH_MODE=production`, `CARETWIN_AUTH_ISSUER`,
`CARETWIN_AUTH_AUDIENCE` and `CARETWIN_AUTH_JWKS_URL`. Verified subjects are linked to
local accounts through `identity_links`, so roles, relationships and consent always come
from server-side records — never from a token claim or the browser. See
[docs/AUTHENTICATION_ARCHITECTURE.md](docs/AUTHENTICATION_ARCHITECTURE.md) and
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

**No identity provider has been selected, and no real token has been verified in this
checkout.** The boundary is provider-independent and tested with an injected key set.

Browser sign-in uses Authorization Code + PKCE at `/api/v1/auth/login`. The callback
validates the state cookie, the single-use nonce and the PKCE verifier, then verifies the
ID token and creates a server-side session in an HttpOnly, Secure, SameSite=Lax cookie
with a double-submit CSRF token. Provider tokens are never stored in the browser or in
URLs. `/auth/sessions` lists active sessions and supports per-session and account-wide
revocation; `/auth/logout` invalidates the session and clears the cookies. Sign-in also
needs `CARETWIN_AUTH_CLIENT_ID` and `CARETWIN_AUTH_REDIRECT_URI` (optional
`CARETWIN_AUTH_CLIENT_SECRET` for confidential clients); tune
`CARETWIN_AUTH_SESSION_TTL_SECONDS`, `CARETWIN_AUTH_SESSION_IDLE_SECONDS`,
`CARETWIN_AUTH_COOKIE_SECURE` and `CARETWIN_AUTH_REQUIRED_AMR` as needed. Refresh tokens
are not stored or used — sessions end at their absolute or idle timeout.

## Limitations

- Synthetic data only; no real-person onboarding.
- Demo header identity, no sessions/MFA/tenant isolation.
- In-memory rate limits; single-process SQLite and local file storage.
- Frontend dependency advisories remain in `next@15.5.29`'s bundled `postcss@8.4.31`; no safe non-breaking fix applied (breaking Next 16 upgrade required).
- No malware scanning of uploads.
- OCR and extraction can misread digits; everything stays unverified until clinician review.
- Demo DB counts unchanged after Phase 17.1 verification; document storage currently has 2 orphan e2e-uploaded PDFs from a prior e2e isolation gap now fixed in `scripts/e2e-api-server.mjs` (not removed).
- Not a diagnosis, not prescribing, no medication changes, not clinically validated.
- Not HIPAA/GDPR certified — see [docs/SECURITY.md](docs/SECURITY.md) for the
  implemented/partial/required matrix.

## Publishing to GitHub (checklist)

This checkout has no `.git` directory and nothing is staged or published. When you publish:

1. Create the repository, then `git init -b main` and `git add -A`.
2. Run `git status --short` and confirm it lists **none** of: `.env*`, `data/demo/`,
   `data/documents/`, `data/e2e/`, `data/tmp/`, `.next/`, `*.db*`, `.venv/`,
   `test-results/`, `playwright-report/`, `*.log`.
3. Search the tracked files for credentials (`GEMINI_API_KEY=`, `AIza`, `x-goog-api-key`)
   and confirm the only matches are documentation that names the setting. Never commit a key.
4. Run the backend suite, the isolated intelligence checks, typecheck, lint, the production build
   and the Playwright suite before the first push.
5. Publish synthetic demo data only. Never commit real patient documents, keys or local databases.
6. State the limitations in the repository description: no clinical validation, no HIPAA/GDPR
   certification, synthetic demo identity only.

## Phase 15 production infrastructure foundation (local/demo)

- **Database:** SQLite remains the verified local/demo engine with additive migrations (`schema_migrations`) and operational indexes. PostgreSQL is the documented production target but **not live-verified** here. See [docs/DATABASE_ARCHITECTURE.md](docs/DATABASE_ARCHITECTURE.md).
- **Storage:** private local document storage with signature/MIME/extension/size/PDF-page validation, UUID keys, per-patient isolation, path containment, hash integrity checks, and authenticated retrieval (no public URLs). Private object-storage adapter strategy documented but **not live-verified**. See [docs/STORAGE_SECURITY.md](docs/STORAGE_SECURITY.md).
- **Backup/recovery:** `app.services.backup` supports consistent SQLite backup, document manifests/hashes, optional Fernet-encrypted artifacts, verification, and isolated restore; automated isolated backup/restore tests pass. External/off-host DR not live-verified. See [docs/BACKUP_AND_RECOVERY.md](docs/BACKUP_AND_RECOVERY.md).
- **Rate limiting/monitoring/config:** in-memory limiter with adapter-ready backend reporting (shared store **not** live-verified), health/readiness component reporting, production config guidance. See [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md).

## Documentation

- [Reproducible demo](docs/DEMO.md)
- [Authentication architecture](docs/AUTHENTICATION_ARCHITECTURE.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Security posture](docs/SECURITY.md)
- [Architecture](docs/architecture.md)
- [Safety model](docs/safety.md)
- [Product and UX](docs/product.md)
- [Current project state](PROJECT_STATE.md)
