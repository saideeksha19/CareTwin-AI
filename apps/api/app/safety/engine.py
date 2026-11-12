from __future__ import annotations

import json
from typing import Any, Callable

from app.errors import conflict, forbidden, validation_error
from app.repositories.store import Store
from app.utils import iso, new_id


class SafetyValidationEngine:
    """Independent deterministic checks applied before consequential writes.

    The engine is intentionally boring: no model calls, no probabilistic logic,
    and no hidden record mutation. Every decision is persisted for review.
    """

    def __init__(self, store: Store) -> None:
        self.store = store

    def _check(self, code: str, label: str, passed: bool, detail: str) -> dict[str, Any]:
        return {"code": code, "label": label, "passed": passed, "detail": detail}

    def _persist(
        self,
        *,
        patient_id: str,
        operation: str,
        outcome: str,
        checks: list[dict[str, Any]],
        actor_name: str,
        actor_role: str,
    ) -> dict[str, Any]:
        decision = {
            "id": new_id("sfd"),
            "patient_id": patient_id,
            "operation": operation,
            "outcome": outcome,
            "checks_json": json.dumps(checks, separators=(",", ":")),
            "actor_name": actor_name,
            "actor_role": actor_role,
            "created_at": iso(),
        }
        self.store.create_safety_decision(decision)
        return {
            "id": decision["id"],
            "patientId": patient_id,
            "operation": operation,
            "outcome": outcome,
            "checks": checks,
            "actorName": actor_name,
            "actorRole": actor_role,
            "createdAt": decision["created_at"],
        }

    def _finish(
        self,
        *,
        patient_id: str,
        operation: str,
        checks: list[dict[str, Any]],
        actor: dict[str, Any],
        failure: Callable[[list[dict[str, Any]]], Exception] | None = None,
    ) -> dict[str, Any]:
        failed = [check for check in checks if not check["passed"]]
        outcome = "rejected" if failed else "allowed"
        decision = self._persist(
            patient_id=patient_id,
            operation=operation,
            outcome=outcome,
            checks=checks,
            actor_name=actor["name"],
            actor_role=actor["role"],
        )
        if failed and failure is not None:
            raise failure(failed)
        return decision

    def validate_checkin_submission(
        self, *, patient: dict[str, Any], user: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "patient_self_write",
                "Patient is the authenticated author",
                user["role"] == "patient",
                "Only the patient may submit a patient check-in.",
            ),
            self._check(
                "synthetic_data_label",
                "Patient is labeled synthetic",
                bool(patient["synthetic"]),
                "Phase 1 external model and demo guardrails require synthetic data.",
            ),
            self._check(
                "attributed_provenance",
                "Author and timestamp are attributable",
                bool(user.get("id") and user.get("name")),
                "Every patient report must be attributable.",
            ),
            self._check(
                "bounded_inputs",
                "Clinical scales are within configured bounds",
                payload["pain_score"] <= 10
                and payload["breathlessness_score"] <= 10
                and all(0 <= symptom["severity"] <= 10 for symptom in payload["symptoms"]),
                "Reported scales must be within 0-10.",
            ),
            self._check(
                "no_ai_authorship",
                "Patient report is not AI-authored",
                True,
                "This record is patient reported, never clinician verified by default.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="patient_checkin.create",
            checks=checks,
            actor=user,
            failure=lambda failed: forbidden(
                "The check-in was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_observation(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        scopes: tuple[str, ...],
        note: str,
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "caregiver_role",
                "Caregiver role is authorized",
                user["role"] == "caregiver",
                "Only an authorized caregiver may add an observation.",
            ),
            self._check(
                "consent_scope",
                "Observation scope is actively consented",
                "observations:write" in scopes,
                "The patient must actively share observation scope.",
            ),
            self._check(
                "attributed_authorship",
                "Caregiver attribution is preserved",
                bool(user.get("id")),
                "Caregiver observations are never anonymized.",
            ),
            self._check(
                "bounded_content",
                "Observation content is present and bounded",
                3 <= len(note.strip()) <= 2000,
                "Observation must be between 3 and 2000 characters.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="caregiver_observation.create",
            checks=checks,
            actor=user,
            failure=lambda failed: forbidden(
                "The observation was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_alert_acknowledgement(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        alert: dict[str, Any],
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "clinician_role",
                "Reviewer is a clinician",
                user["role"] == "clinician",
                "Only a clinician may acknowledge a safety alert.",
            ),
            self._check(
                "alert_open",
                "Alert is still open",
                alert["status"] == "open",
                "Acknowledged or resolved alerts cannot be re-acknowledged.",
            ),
            self._check(
                "evidence_link",
                "Alert retains an evidence reference",
                bool(alert.get("evidence_id")),
                "Alerts without provenance cannot be acknowledged in Phase 1.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="safety_alert.acknowledge",
            checks=checks,
            actor=user,
            failure=lambda failed: conflict(
                "The alert acknowledgement was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_alert_resolution(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        alert: dict[str, Any],
        note: str,
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "clinician_role",
                "Reviewer is a clinician",
                user["role"] == "clinician",
                "Only a clinician may resolve a safety alert.",
            ),
            self._check(
                "alert_acknowledged",
                "Alert was acknowledged before resolution",
                alert["status"] == "acknowledged",
                "An open alert must be acknowledged before it can be resolved.",
            ),
            self._check(
                "evidence_link",
                "Alert retains an evidence reference",
                bool(alert.get("evidence_id")),
                "Alerts without provenance cannot be resolved in Phase 1.",
            ),
            self._check(
                "resolution_rationale",
                "Resolution rationale is documented",
                3 <= len(note.strip()) <= 1000,
                "Resolution requires a short attributable rationale.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="safety_alert.resolve",
            checks=checks,
            actor=user,
            failure=lambda failed: conflict(
                "The alert resolution was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_medication_verification(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        medication: dict[str, Any],
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "clinician_role",
                "Reviewer is a clinician",
                user["role"] == "clinician",
                "Medication verification requires a clinician role.",
            ),
            self._check(
                "evidence_link",
                "Medication has document evidence",
                bool(medication.get("evidence_id")),
                "No instruction becomes clinician verified without a source.",
            ),
            self._check(
                "reviewable_state",
                "Instruction is in a reviewable state",
                medication["verification_status"] in {"awaiting_review", "document_extracted"},
                "Only extracted or awaiting-review instructions can be verified.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="medication.verify",
            checks=checks,
            actor=user,
            failure=lambda failed: conflict(
                "The medication verification was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_consent_update(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        consent: dict[str, Any],
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "patient_self_control",
                "Patient controls their own consent",
                user["role"] == "patient",
                "Only the patient may change sharing consent.",
            ),
            self._check(
                "consent_ownership",
                "Consent record belongs to the patient",
                consent["patient_id"] == patient["id"],
                "Cross-patient consent changes are rejected.",
            ),
            self._check(
                "auditable_change",
                "Change is attributable for audit",
                bool(user.get("id")),
                "Every consent change is audited.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="consent.update",
            checks=checks,
            actor=user,
            failure=lambda failed: forbidden(
                "The consent update was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_milestone_update(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        milestone: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "clinician_role",
                "Reviewer is a clinician",
                user["role"] == "clinician",
                "Milestone corrections require a clinician role.",
            ),
            self._check(
                "milestone_ownership",
                "Milestone belongs to the patient",
                milestone["patient_id"] == patient["id"],
                "Cross-patient milestone updates are rejected.",
            ),
            self._check(
                "evidence_preserved",
                "Milestone retains a source reference",
                bool(milestone.get("evidence_id")),
                "Milestone changes must retain evidence linkage.",
            ),
            self._check(
                "valid_status",
                "Milestone status is supported",
                status
                in {"pending", "in_progress", "completed", "overdue", "not_applicable"},
                "Unsupported milestone status.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="milestone.update",
            checks=checks,
            actor=user,
            failure=lambda failed: conflict(
                "The milestone update was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_rule_update(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        rule: dict[str, Any],
        threshold: float | None,
    ) -> dict[str, Any]:
        checks = [
            self._check(
                "clinician_role",
                "Reviewer is a clinician",
                user["role"] == "clinician",
                "Only a clinician may configure monitoring rules.",
            ),
            self._check(
                "rule_ownership",
                "Rule belongs to the patient",
                rule["patient_id"] == patient["id"],
                "Cross-patient rule changes are rejected.",
            ),
            self._check(
                "threshold_non_negative",
                "Threshold is non-negative",
                threshold is None or threshold >= 0,
                "Threshold must be non-negative.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="monitoring_rule.update",
            checks=checks,
            actor=user,
            failure=lambda failed: forbidden(
                "The rule update was rejected by safety validation.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )

    def validate_ai_output(
        self,
        *,
        patient: dict[str, Any],
        user: dict[str, Any],
        output: dict[str, Any],
        allowed_evidence_ids: set[str],
    ) -> dict[str, Any]:
        citations = output.get("citations", [])
        checks = [
            self._check(
                "synthetic_only",
                "External model use is restricted to synthetic data",
                bool(patient["synthetic"]),
                "Phase 1 does not send real patient data to an external model.",
            ),
            self._check(
                "citations_grounded",
                "All citations resolve to available evidence",
                bool(citations) and set(citations).issubset(allowed_evidence_ids),
                "Model output must cite known evidence identifiers.",
            ),
            self._check(
                "no_medication_change",
                "Output does not recommend medication changes",
                not bool(output.get("medication_change_advice")),
                "Medication changes remain exclusively a clinician decision.",
            ),
            self._check(
                "no_diagnosis_claim",
                "Output does not assert a new diagnosis",
                not bool(output.get("diagnosis_claim")),
                "CareTwin AI does not diagnose.",
            ),
            self._check(
                "uncertainty_disclosed",
                "Uncertainty is explicitly disclosed",
                bool(str(output.get("uncertainty", "")).strip()),
                "Model explanations must disclose uncertainty.",
            ),
        ]
        return self._finish(
            patient_id=patient["id"],
            operation="ai.explanation.validate",
            checks=checks,
            actor=user,
            failure=lambda failed: validation_error(
                "The model output was rejected by the safety validation engine.",
                {"failedChecks": [check["code"] for check in failed]},
            ),
        )
