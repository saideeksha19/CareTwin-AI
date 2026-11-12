# CareTwin AI — intelligence architecture

This document describes the implemented AI boundary in this checkout, how grounded
explanations and assistant answers are produced, how deterministic fallback works,
and what has and has not been live-verified. It is an engineering description, not
a clinical or compliance claim.

## 1. Provider boundary

- **Service:** `apps/api/app/ai/service.py` (`AiService`). All provider calls are
  server-side; the browser never receives `GEMINI_API_KEY` and no `NEXT_PUBLIC_`
  variable carries a credential.
- **API:** Google Generative Language API `generateContent` at
  `CARETWIN_AI_API_BASE` (default `https://generativelanguage.googleapis.com/v1beta`)
  with the key sent in the `x-goog-api-key` header.
- **Model:** `CARETWIN_AI_MODEL` (default in this checkout `gemini-3.8-flash`). The
  model is operator-configurable and must be set to a model currently supported for
  structured JSON generation by the provider account; model compatibility is
  **not** live-verified in this checkout (no key configured).
- **Structured output:** requests set `responseMimeType: application/json` with an
  explicit `responseSchema` and bounded `maxOutputTokens`/temperature.
- **Resilience:** bounded timeout (`CARETWIN_AI_TIMEOUT_SECONDS`), limited retries
  for retryable transport/5xx cases, a per-hour server request budget, and mapped
  errors for invalid credentials, quota exhaustion, rate limits, unavailable models,
  timeouts and unreachable providers. Failures never fabricate an answer.

## 2. Grounding, validation and safety

- **Untrusted input:** uploaded text, OCR output and user questions are treated as
  hostile data (`prompt_guard.py`): sanitized/length-capped, wrapped in explicit
  `UNTRUSTED …` delimiters, and scanned for instruction-injection patterns. Detected
  injection is redacted in prompts where appropriate and recorded in the audit trail;
  the document is still processed as data.
- **Evidence corpus:** document explanations are built from the extracted pages and
  structured extractions (with citation ids), plus clinician-verified historical
  values where available. The system instruction forbids following document text as
  instructions, inventing values/units/ranges/diagnoses/medications, revealing
  secrets, or changing doses.
- **Output validation:** `validate_document_explanation` and the assistant checks
  reject unknown citations, unsupported numeric claims, diagnosis or medication-change
  advice, missing uncertainty/limitations, and missing escalation when emergency
  language is present. Rejected output is not shown or cached as a success.
- **Scope:** cross-patient access is enforced by server-side authorization
  (`require_access` / role and consent checks). The assistant is not available to
  caregivers.

## 3. Document explanations and assistant

- **Explanations:** `POST /patients/{id}/documents/{doc}/explain` (and stored
  retrieval) produces a grounded explanation with summary, per-result citations,
  interpretation, findings for review, missing/ambiguous items, questions for the
  clinician, general education, limitations and uncertainty. Prescriptions are
  explained only as written; no new prescription is produced.
- **Caching:** explanations are keyed by document, mode, model and an input hash of
  the evidence, so unchanged inputs reuse the validated result; regeneration bypasses
  the cache but only a passing result is stored.
- **Assistant:** `services/assistant_service.py` retrieves patient-owned facts and
  citations, returns a deterministic record answer when no model is configured or
  when the model answer is withheld/fails, and returns an AI-grounded answer only
  after citation/number/safety checks pass. Conversation history is persisted per
  patient and exposed through the history endpoint.

## 4. Frontend states and labelling

The UI surfaces: generation/regeneration with loading, saved vs fresh explanations,
provider-unavailable and deterministic-fallback states, AI-generated vs deterministic
vs clinician-verified/unverified labels, evidence citations (with page references),
assistant conversation history and follow-ups, error/retry handling, and safety
footers (not a diagnosis, no medication changes). Unverified extractions remain
unverified until clinician review.

## 5. Live validation status (this checkout)

- **Genuine Gemini provider calls:** **BLOCKED — no `GEMINI_API_KEY` configured** and
  no `.env` present. No live document explanation, no live assistant answer, and no
  live provider health check with valid credentials has been executed here.
- **Mocked provider behaviour:** **AUTOMATED TEST VERIFIED** — success/caching,
  regeneration, invalid-key/auth, quota/rate-limit, unavailable model/credit/network,
  timeout, content-blocked, invalid/empty JSON, rejected output (unsupported numbers,
  unknown/fabricated citations, diagnosis/medication advice, missing uncertainty),
  prompt-injection handling, request-budget enforcement and assistant
  grounding/fallback/history are covered with `MockTransport`.
- **Deterministic paths:** **LIVE VERIFIED LOCALLY** via the intelligence script,
  backend suite, Playwright and HTTP smoke tests; demo data is synthetic and
  unchanged.

## 6. Local configuration (exact steps)

To enable genuine provider validation locally, without exposing the key:

1. Obtain a Gemini API key from your Google AI account (do not share or paste it).
2. Create `./.env` in the project root (gitignored) with, for example:
   - `GEMINI_API_KEY=<your key>`
   - `CARETWIN_AI_MODEL=<a currently supported model id>`
   - optionally `CARETWIN_AI_API_BASE`, `CARETWIN_AI_TIMEOUT_SECONDS`,
     `CARETWIN_AI_REQUESTS_PER_HOUR`
3. Restart the API server so it reads the environment. Confirm configuration only
   via `GET /api/v1/ai/status` and `GET /api/v1/ai/health` (neither returns the key).
4. Run a genuine document explanation and one assistant question, record the
   returned provider/model metadata, latency, citations and validation outcome, then
   separately exercise invalid-key and quota/error handling with disposable
   settings — never log or report the key value.

Until this is done with real responses, genuine Gemini behaviour remains
**IMPLEMENTED BUT NOT LIVE-VERIFIED** / **BLOCKED** in reports.