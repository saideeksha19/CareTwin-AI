# Architecture

## System context

CareTwin AI is a local-first Phase 1 monorepo:

```text
Browser
  |
  |  Next.js 15 app (apps/web)
  |  X-Demo-User-Id demo identity
  v
FastAPI /api/v1 (apps/api)
  |
  |  deterministic services, consent checks, safety validation
  v
SQLite WAL database (data/demo/caretwin.db)

Optional:
FastAPI -> Gemini API (server-side only, synthetic patients, validated JSON)
```

The frontend never calls a model directly and never receives a provider key. The API is authoritative for identity, scope, role checks, clinical rules, persistence and AI validation.

## Design principles

1. **Server-authoritative access.** Hiding navigation is presentation only. Every route re-checks role, care relationship and consent scopes.
2. **One evidence chain.** Clinical facts reference an `evidence_sources` row; events reference evidence where applicable. Verification state is explicit.
3. **Deterministic safety.** Monitoring and safety validation use fixed rules, thresholds and bounded inputs. No probabilistic logic gates a consequential write.
4. **Human review before elevation.** Extracted medication instructions can be verified only by a clinician and only with a source. AI output cannot diagnose or change medication.
5. **Optional AI.** The product works with no model key. An unconfigured model is surfaced honestly, not simulated.
6. **Synthetic first.** Phase 1 rejects external model use for non-synthetic patients.

## Runtime components

| Component | Location | Responsibility |
|---|---|---|
| Next.js app | `apps/web` | App router pages, role navigation, client API calls, presentation |
| API app | `apps/api/app/main.py` | App factory, lifespan, CORS, request IDs, error envelopes |
| Routes | `apps/api/app/api/v1.py` | HTTP validation and service orchestration |
| Domain schemas | `apps/api/app/domain/schemas.py` | Pydantic request/response contracts and camelCase aliases |
| Store | `apps/api/app/repositories/store.py` | Parameterized SQLite access |
| Auth | `services/auth.py` | Demo identity resolution, role, relationship, consent intersection |
| Twin | `services/twin_service.py` | Role-scoped twin assembly, progress, alert DTOs |
| Monitoring | `services/monitoring.py` | Check-in rule evaluation and check-in-gap sweep |
| Safety engine | `safety/engine.py` | Independent pre-write validation and persisted decisions |
| Check-ins | `services/checkin_service.py` | Evidence, event, audit, alerts, twin snapshot |
| Observations | `services/observation_service.py` | Caregiver-attributed evidence and event |
| Alerts | `services/alert_service.py` | Listing and clinician acknowledgement |
| Consent | `services/consent_service.py` | Patient-controlled sharing changes |
| Clinical | `services/clinical_service.py` | Review actions, monitoring rules, sweep, summary |
| Records | `services/record_service.py` | Timeline, evidence, audit, snapshots |
| AI | `ai/service.py` | Optional provider call, grounded context, output validation |
| Seed | `seed.py` | Idempotent synthetic dataset |

## Data model

Core tables:

| Group | Tables |
|---|---|
| Identity and access | `users`, `patients`, `care_relationships`, `consent_records` |
| Recovery state | `recovery_twins`, `recovery_plans`, `milestones`, `twin_snapshots` |
| Care plan | `medication_instructions`, `follow_ups` |
| Patient-generated | `checkins`, `symptom_reports`, `caregiver_observations` |
| Evidence | `evidence_sources`, `recovery_events` |
| Safety | `safety_alerts`, `monitoring_rules`, `safety_decisions` |
| Governance | `audit_events` |

Important relationships:

```text
patient 1---1 recovery_twin
patient 1---* care_relationship
patient 1---* consent_record
patient 1---* evidence_source
patient 1---* recovery_event ---> evidence_source (optional)
patient 1---* checkin 1---* symptom_report
patient 1---* safety_alert ---> monitoring_rule, evidence_source
patient 1---* twin_snapshot
patient 1---* safety_decision, audit_event
```

The seed is idempotent: if `pat_maya` exists, seeding returns without duplicating data.

## Request flows

### Patient check-in

1. Web submits the structured form with the demo patient identity.
2. API resolves the user and requires a patient self relationship.
3. `SafetyValidationEngine.validate_checkin_submission` checks author role, synthetic label, attribution, bounded 0–10 scales and non-AI authorship; the decision is persisted.
4. Service creates an `evidence_sources` row, `checkins` row, symptom rows, a `checkin_submitted` event and an audit entry.
5. Monitoring evaluates enabled rules in order:
   - chest pain severity
   - breathlessness severity
   - fever threshold
   - adherence gap
   - pain escalation versus the previous check-in
6. Each triggered rule creates an open alert, a `safety_alert_raised` event and audit entry.
7. Twin status is recomputed, the version is incremented and a snapshot is written.
8. Response returns the check-in, created alerts, new twin version and status.

All records commit together. Missing data never implies a symptom conclusion; the check-in-gap rule only flags absence of contact.

### Monitoring sweep

1. Clinician-only route loads the patient and latest check-in.
2. `checkin_gap` is evaluated against the clinician-configured hours threshold.
3. Duplicate open gap alerts since the latest activity are suppressed.
4. A sweep event and audit entry are always written, including zero-result sweeps.
5. Response includes camelCase alert DTOs, evaluated rule count, gap hours and a message.

### Consent revocation

1. Patient calls `PATCH /patients/{id}/consents/{consentId}` with a reason and status.
2. Safety engine checks patient self-control, record ownership and attribution.
3. Consent status, timestamps and scopes are updated; event and audit are recorded.
4. Every later caregiver request intersects relationship scopes with active consent.
5. Revoked caregiver receives `403` with `consent_revoked_or_missing` before twin data is assembled. Priya is seeded for this boundary test.

### AI explanation

1. Patient or clinician requests `/ai/explain`.
2. API requires `summary:read`, synthetic patient and a configured key.
3. Grounded context is built from plan, milestones, medications, follow-ups, recent check-ins, open alerts and evidence.
4. Model is instructed to return structured JSON with citations and uncertainty.
5. `SafetyValidationEngine.validate_ai_output` rejects:
   - missing/unknown citations
   - medication-change advice
   - diagnosis claims
   - missing uncertainty
   - non-synthetic patients
6. Response includes the validated answer, citations and safety decision ID.

Without a key, the route returns `503 ai_not_configured`; no model request is attempted.

## Contracts and errors

- API and frontend use camelCase; Pydantic aliases map internal snake_case.
- All errors use:

```json
{
  "error": {
    "code": "forbidden",
    "message": "Human-readable message",
    "details": {},
    "requestId": "..."
  }
}
```

- Every response carries `X-Request-ID`; incoming IDs are preserved.
- Validation failures return `422 validation_failed` with field locations.

## Persistence and concurrency

- SQLite with WAL journaling, foreign keys and a 5-second busy timeout.
- One connection per request via dependencies; connections now use `check_same_thread=False` because FastAPI dependency and endpoint execution may occur on different threadpool threads.
- Suitable for a single local process. Not designed for multi-instance or high-write deployment.
- Demo DB path: `data/demo/caretwin.db`; test DBs are isolated per pytest run using a temporary path.

## Frontend architecture

- App Router routes under `apps/web/src/app`.
- Shared workspace shell owns demo identity, role switcher, navigation and mobile drawer.
- `useApi` handles load/error/retry; `apiRequest` wraps fetch and typed error parsing.
- `packages/contracts` is the single TypeScript source of API types.
- `packages/domain` holds labels, tones and role-aware navigation.
- `packages/safety` holds disclaimers and provenance display rules.
- Pages use client components because all data depends on the selected demo role and local API.
- Production build statically generates the route shells; data is fetched at runtime.

## Security boundaries

- Demo identity header is intentionally not authentication.
- CORS is limited to local ports by default.
- No secrets are sent to the browser.
- Model keys exist only in the API process environment.
- Parameterized SQL is used throughout.
- Audit and safety decisions are append-only through the service layer.

## Deployment shape for a future phase

A production system would need real authentication, tenant isolation, encrypted managed storage, background jobs, rate limits, observability, retention controls, browser E2E tests and clinical/regulatory review. None of those are claimed in Phase 1.
