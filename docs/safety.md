# Safety Model

> CareTwin AI Phase 1 is a synthetic demo, not a medical device. It does not diagnose, prescribe, change medication or replace clinical judgement.

## Principles

1. **Deterministic before generative.** Rules, thresholds and role checks are fixed code. No model decides whether an alert is raised or whether a write is allowed.
2. **Evidence before elevation.** A record can be clinician-verified only when it has a source reference.
3. **Least privilege.** Patient, caregiver and clinician capabilities are separate. Caregiver access is the intersection of relationship scopes and active patient consent.
4. **Attribution.** Check-ins, observations, acknowledgements, verifications, rule changes and consent changes retain an actor and timestamp.
5. **No silent mutation.** Consequential writes also create events, audit records and/or safety decisions.
6. **Missing data is not a diagnosis.** The check-in-gap rule flags lack of contact; it does not infer deterioration.
7. **Honest AI.** An unconfigured model is reported as unconfigured. The deterministic product remains functional.

## Authorization matrix

| Capability | Patient | Caregiver | Clinician |
|---|---|---|---|
| View own/shared twin | Own only | Active consent + `twin:read` | `*` |
| View timeline | Own only | `timeline:read` | `*` |
| Submit check-in | Own only | No | No |
| Add observation | No | `observations:write` | No |
| View alerts | Own only | `alerts:read` | `*` |
| Acknowledge alert | No | No | Yes |
| View schedule | Own only | `schedule:read` | `*` |
| View consent records | Own only | `consents:read` | `*` |
| Change consent | Own only | No | No |
| Verify medication | No | No | Yes |
| Change monitoring rule | No | No | Yes |
| Run monitoring sweep | No | No | Yes |
| View clinical summary | Own only | No | Yes |
| View safety decisions | Own only | No | Yes |
| View audit trail | Own only | No | Yes |
| Request AI explanation | Own only | No | Yes |

Clinicians and patients resolve to `*` only after the role-specific relationship check. A caregiver whose consent is revoked receives `403` before the twin is assembled. Hiding a control in the UI is not treated as authorization.

## Deterministic monitoring rules

Seeded defaults, editable by a clinician:

| Code | Kind | Default threshold | Severity | Trigger |
|---|---|---:|---|---|
| `chest_pain_severity` | symptom severity | 7 | critical | Reported chest pain ≥ 7/10 |
| `breathlessness_severity` | symptom severity | 7 | urgent | Reported breathlessness ≥ 7/10 |
| `fever_threshold` | temperature | 38.5 °C | urgent | Recorded temperature ≥ 38.5 °C |
| `adherence_gap` | missed doses | 2 | moderate | ≥ 2 missed doses reported |
| `pain_escalation` | pain delta | 3 | moderate | Pain up ≥ 3 points from prior check-in **and** current pain ≥ 6/10 |
| `checkin_gap` | hours | 24 | moderate | Latest check-in older than threshold; sweep-only |

Rules can be enabled/disabled by a clinician. A disabled rule emits nothing.

### Alert output

Every triggered alert records:

- rule ID, severity and category
- patient, optional check-in, optional evidence source
- human-readable rationale ending in a non-diagnostic disclaimer
- open status and timestamps
- linked `safety_alert_raised` event and audit entry

Acknowledgement is clinician-only, requires an open alert with evidence, and records reviewer/time. It does not resolve the underlying clinical issue.

## Safety Validation Engine

`apps/api/app/safety/engine.py` applies deterministic checks before consequential writes and persists each decision in `safety_decisions`.

| Operation | Checks |
|---|---|
| `patient_checkin.create` | patient author, synthetic label, attributable author, bounded 0–10 scales, not AI-authored |
| `caregiver_observation.create` | caregiver role, `observations:write` consent, attribution, 3–2000 characters |
| `safety_alert.acknowledge` | clinician role, alert still open, evidence link exists |
| `medication.verify` | clinician role, evidence link exists, instruction reviewable |
| `consent.update` | patient self-control, record ownership, attributable change |
| `milestone.update` | clinician role, ownership, evidence preserved, supported status |
| `monitoring_rule.update` | clinician role, ownership, non-negative threshold |
| `ai.explanation.validate` | synthetic patient, citations grounded, no medication-change advice, no diagnosis claim, uncertainty disclosed |

A failed check records a rejected decision and returns a structured error such as `forbidden`, `conflict` or `validation_failed`.

## AI guardrails

- Server-side only; the browser never sees `GEMINI_API_KEY`.
- Off by default. Without a key, `/ai/status` is `not_configured` and `/ai/explain` is `503`.
- Restricted to recorded synthetic patients in Phase 1.
- Allowed only for patient/clinician with `summary:read`.
- Prompt is grounded in stored plan/evidence and asks for JSON with citations and uncertainty.
- Output must cite known evidence IDs; unknown or empty citations fail validation.
- Output cannot recommend medication changes or assert a new diagnosis.
- Every accepted or rejected AI output produces a safety decision.
- AI never writes clinical records, alerts or twin state.

## Emergency and escalation UX

The UI consistently states that CareTwin does not provide emergency care. Emergency symptoms require local emergency services. Alert acknowledgement is a workflow action, not treatment. There is no paging, on-call routing or emergency dispatch in Phase 1.

## Audit trail

Recorded actions include check-in creation, observation creation, alert creation/acknowledgement, medication verification, milestone updates, rule changes, monitoring sweeps, consent changes and AI validation decisions. Audit entries include actor, role, action, entity, outcome, details and timestamp. Clinician summaries and audit are not available to caregivers.

## Verification status vocabulary

| Status | Meaning |
|---|---|
| `document_extracted` | Extracted from a source; may still need review |
| `awaiting_review` | Explicitly pending human review |
| `clinician_verified` | Reviewed against a source by a clinician |
| `patient_reported` | Authored by the patient; not clinician verified |
| `caregiver_reported` | Attributed caregiver observation; not clinician verified |

The UI must not present patient/caregiver reports or AI extraction as clinician-verified facts.

## Known safety limitations

- No real clinical validation, usability study or regulatory review.
- Rules are simple thresholds and trends, not a validated deterioration model.
- No duplicate suppression for symptom alerts across repeated check-ins, except the check-in-gap sweep.
- No alert resolution workflow beyond acknowledgement in Phase 1.
- No real-time notifications, paging or emergency escalation.
- No production authentication, authorization server or tenant isolation.
- AI path has not been exercised with a live key in this repository.
- SQlite and a single process are not a production reliability boundary.
