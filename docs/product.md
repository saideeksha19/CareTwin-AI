# Product and UX — Phase 1

## Problem

After discharge, recovery information is fragmented across discharge documents, patient recollection, caregiver observations and clinician workflow. Patients are unsure what matters today. Caregivers lack bounded visibility. Clinicians lack a fast, source-linked view of what changed.

CareTwin AI tests one proposition: **a recovery digital twin is useful only when every changing fact is attributable, role-scoped and reviewable.**

## Product thesis

- A daily check-in should update a coherent recovery state, not create another disconnected form.
- A safety flag should be deterministic, explainable and linked to the report that triggered it.
- A caregiver should see only what the patient has actively shared.
- A clinician should review exceptions and sources, not re-read everything.
- AI should explain grounded records, never author clinical state.

## Users and jobs

### Maya — patient

- “Tell me what matters today.”
- “Record how I feel in under two minutes.”
- “Show me why the app thinks I need attention.”
- “Control who can see my recovery.”

### Arjun — caregiver with consent

- “Show me the shared recovery picture without exposing the clinician workspace.”
- “Record what I observed and keep my name attached.”
- “Tell me when sharing is no longer active.”

### Dr. Nandini — clinician

- “Show me unreviewed instructions and open safety flags.”
- “Let me verify against the source, acknowledge and adjust thresholds.”
- “Give me a concise summary with provenance.”
- “Keep an audit trail of consequential actions.”

## Page map

| Route | Audience | Purpose |
|---|---|---|
| `/` | Public | Product framing, safety positioning, entry |
| `/demo` | Public | Choose synthetic demo identity |
| `/workspace` | All roles | Role-aware recovery overview |
| `/workspace/twin` | Patient, consented caregiver, clinician | Full recovery twin and evidence graph |
| `/workspace/timeline` | Patient, consented caregiver, clinician | Filterable event history with payload/source |
| `/workspace/check-in` | Patient | Structured daily check-in |
| `/workspace/schedule` | Patient, consented caregiver, clinician | Medications and follow-ups |
| `/workspace/caregiver` | Caregiver | Shared overview and observation workflow |
| `/workspace/clinician` | Clinician | Review queue, rules, safety/audit, clinical summary |
| `/workspace/alerts` | All roles | Alert center; clinician acknowledgement |
| `/workspace/consent` | Patient | Scoped sharing control and revocation |
| `/workspace/intelligence` | All roles | Agents, evidence, AI boundary, snapshots, decisions, audit |

## Key journeys

### 1. Daily check-in

Patient opens overview → sees focus and next action → submits pain, temperature, breathlessness, adherence and symptoms → receives immediate rule-based alerts → twin version increases → timeline gains a source-linked event.

### 2. Caregiver observation

Caregiver opens shared overview → adds an attributed note → evidence and event are created → patient and clinician see who observed what and when.

### 3. Clinician review

Clinician opens review queue → acknowledges an evidence-linked alert → verifies an awaiting-review medication against page 2 of the discharge source → sees audit and safety decisions update.

### 4. Consent revocation

Patient opens consent → revokes Arjun’s sharing with a reason → Arjun’s next request is refused before twin assembly → patient can restore later. Priya demonstrates the revoked state from the seed.

### 5. AI boundary

Patient/clinician opens Intelligence → sees `not_configured` honestly → reads grounded deterministic summary instead → when configured, can request an explanation that must cite evidence and pass safety validation.

## UX principles

- **Clinical calm.** Navy, teal, mist and warm paper; no alarmist red surfaces beyond genuine critical flags.
- **Evidence adjacent.** Provenance is shown near claims, not buried in a settings page.
- **Explicit state.** “Awaiting review”, “patient reported” and “clinician verified” are distinct.
- **Role legibility.** Navigation, empty states and permission panels explain what the current role can and cannot do.
- **No fake intelligence.** No simulated streaming, fabricated model output or invented confidence scores.
- **Mobile-aware.** Responsive cards, collapsible navigation and touch-sized controls.

## Design system

- Display/body: Segoe UI with system fallbacks.
- Primary navy: `#041320`; teal care accent; warm paper cards; mist page background.
- Rounded 16–24 px cards, restrained borders and shadows, limited motion.
- Shared primitives: buttons, cards, badges, progress, fields, tabs, provenance, feedback.
- Lucide icons only; no emoji in product UI.
- Synthetic-demo labeling is persistent in access and safety surfaces.

## Phase 1 scope

Included:

- One synthetic patient, four demo users, three roles.
- End-to-end check-in → rule → alert → event → twin snapshot.
- Consent scoping and revocation boundary.
- Clinician review, verification, rules and sweep.
- Deterministic summary, audit and safety decisions.
- Optional grounded AI endpoint with validation and honest unconfigured state.
- Responsive frontend, API tests, lint, typecheck and production build.

Excluded:

- Real patient onboarding, production auth, tenancy or HIPAA/GDPR claims.
- Document upload/OCR; only seeded extraction contracts.
- Notifications, messaging, paging or emergency dispatch.
- Prescribing, medication changes, diagnosis or autonomous action.
- Live model evaluation, fine-tuning or model-authored records.
- Multi-patient clinician panel or scheduling integration.
- Native mobile apps and offline sync.

## Demo script

1. Start at `/`, choose **Maya Rao**.
2. Show overview, twin, source links and timeline.
3. Submit a worsening check-in (e.g. breathlessness 8/10) and show the new urgent alert, event and twin version.
4. Switch to **Dr. Nandini**, acknowledge the alert, verify the inhaler instruction, review rules and summary.
5. Switch to **Arjun**, add an observation and show consent-scoped visibility.
6. Switch to **Maya**, revoke Arjun’s consent with a reason.
7. Switch to **Arjun** and show the explicit 403 boundary.
8. Optionally switch to **Priya** to show the seeded revoked state.
9. Open Intelligence and show honest `not_configured` AI status, evidence map and safety decisions.

## Success criteria for Phase 1

- A new reviewer can run both apps from the README without guessing.
- Every displayed clinical claim can be traced to evidence or an explicit review state.
- Role and consent boundaries hold at the API, not only in navigation.
- A check-in produces alerts, events and a snapshot deterministically.
- The product remains coherent and honest with no AI key configured.
- Automated frontend checks and the API suite pass.

## Future roadmap

### Phase 2 — workflow depth

- Real authentication and tenant isolation.
- Document upload, OCR and human review queue.
- Alert resolution, assignment and escalation.
- Multi-patient clinician panel and richer summaries.
- Browser E2E, accessibility and usability testing.

### Phase 3 — clinical integration

- FHIR/EHR integration and terminology validation.
- Configurable rule packs reviewed by clinicians.
- Notification and on-call routing.
- Security review, privacy impact assessment and regulatory strategy.

### Phase 4 — validated intelligence

- Evaluated grounded model assistance with offline metrics.
- Multilingual patient communication with clinician review.
- Prospective safety and equity evaluation.
- Only then consider regulated clinical claims.
