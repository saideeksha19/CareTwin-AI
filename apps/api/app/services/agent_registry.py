from __future__ import annotations

from typing import Any

AGENTS: list[dict[str, Any]] = [
    {
        "id": "document_intelligence",
        "name": "Document Intelligence Agent",
        "responsibility": (
            "Process discharge summaries and care documents into structured, page-linked "
            "evidence with explicit ambiguity and missing-field markers."
        ),
        "phase1Status": "architecturally_prepared",
        "statusLabel": "Contracts and seeded extraction exist; live PDF/OCR upload is not enabled.",
        "permissions": ["evidence_source.create", "extraction.candidate.create"],
        "boundaries": [
            "Cannot mark its own extraction as clinician verified.",
            "Cannot invent missing dose, diagnosis, or follow-up data.",
            "Every extracted field must cite a page or source span.",
        ],
        "interfaces": [
            "EvidenceSource model",
            "verification_status = awaiting_review",
            "clinician verification endpoint",
        ],
    },
    {
        "id": "recovery_planning",
        "name": "Recovery Planning Agent",
        "responsibility": (
            "Organize only clinician-provided instructions into milestones and follow-up tasks."
        ),
        "phase1Status": "architecturally_prepared",
        "statusLabel": "Structured plan and milestone data are live; generation endpoints are not.",
        "permissions": ["plan.candidate.create", "milestone.candidate.create"],
        "boundaries": [
            "Cannot prescribe treatment or create new clinical instructions.",
            "Plan candidates remain awaiting review until a clinician approves them.",
        ],
        "interfaces": ["RecoveryPlan", "RecoveryMilestone", "clinician milestone update"],
    },
    {
        "id": "recovery_monitoring",
        "name": "Recovery Monitoring Agent",
        "responsibility": (
            "Evaluate reported data against clinician-configured deterministic rules and "
            "create reviewable alerts with provenance."
        ),
        "phase1Status": "working_deterministic",
        "statusLabel": "Rule evaluation, alert provenance, check-in gap sweep, and ack workflow work.",
        "permissions": ["alert.create", "safety_event.create"],
        "boundaries": [
            "Cannot diagnose or change medication.",
            "Cannot acknowledge its own alert.",
            "Rules are clinician-configured and evaluated deterministically.",
        ],
        "interfaces": [
            "POST /patients/{id}/checkins",
            "POST /patients/{id}/monitoring/run",
            "GET /patients/{id}/alerts",
        ],
    },
    {
        "id": "patient_communication",
        "name": "Patient Communication Agent",
        "responsibility": (
            "Explain recorded recovery information in understandable language, including "
            "English, Kannada and Hindi, without diagnosing or changing treatment."
        ),
        "phase1Status": "requires_ai_configuration",
        "statusLabel": (
            "Deterministic guidance copy works. External multilingual model explanation "
            "requires server-side AI provider configuration."
        ),
        "permissions": ["explain.recorded_information"],
        "boundaries": [
            "Cannot diagnose or recommend medication changes.",
            "Cannot send data to an external model unless the patient is synthetic in Phase 1.",
            "Output is validated and can be rejected by the Safety Validation Engine.",
        ],
        "interfaces": ["GET /ai/status", "POST /ai/explain", "deterministic summary"],
    },
    {
        "id": "caregiver_coordination",
        "name": "Caregiver Coordination Agent",
        "responsibility": (
            "Support attributed caregiver observations and consent-scoped visibility."
        ),
        "phase1Status": "working_permissions",
        "statusLabel": "Consent-scoped caregiver access and attributed observations work end to end.",
        "permissions": ["observation.create", "shared_twin.read"],
        "boundaries": [
            "Reads only active consent scopes.",
            "Cannot author a patient check-in.",
            "Cannot verify clinical information.",
        ],
        "interfaces": [
            "POST /patients/{id}/observations",
            "PATCH /patients/{id}/consents/{consent_id}",
        ],
    },
    {
        "id": "clinical_summary",
        "name": "Clinical Summary Agent",
        "responsibility": (
            "Produce a concise, evidence-linked summary of changes, concerns and recent data "
            "for clinician review."
        ),
        "phase1Status": "working_deterministic",
        "statusLabel": "Deterministic evidence-linked summary is live; model-generated prose is optional.",
        "permissions": ["summary.draft.create"],
        "boundaries": [
            "Every section carries evidence references.",
            "No diagnosis or medication recommendation is generated.",
        ],
        "interfaces": ["GET /patients/{id}/clinical-summary"],
    },
    {
        "id": "safety_validation",
        "name": "Safety Validation Engine",
        "responsibility": (
            "Independently validate permissions, provenance, verification state, consent and "
            "model outputs before consequential operations are persisted."
        ),
        "phase1Status": "working_deterministic",
        "statusLabel": "Role, consent, provenance and AI-output checks run and are persisted.",
        "permissions": ["decision.allow", "decision.reject"],
        "boundaries": [
            "No model reasoning is allowed inside authorization decisions.",
            "A rejected operation is not persisted as a clinical change.",
            "Every decision is written to the safety decision log.",
        ],
        "interfaces": [
            "GET /patients/{id}/safety-decisions",
            "check-in, observation, consent, verification and acknowledgement services",
        ],
    },
]


def list_agents() -> list[dict[str, Any]]:
    return AGENTS
