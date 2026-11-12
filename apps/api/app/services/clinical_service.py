from __future__ import annotations

import json
from typing import Any

from app.domain.schemas import (
    MedicationVerifyRequest,
    MilestoneUpdateRequest,
    MonitoringRuleUpdateRequest,
)
from app.errors import not_found
from app.repositories.store import Store
from app.safety.engine import SafetyValidationEngine
from app.services import twin_service
from app.services.auth import require_clinician
from app.utils import iso, new_id


def _rule_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "description": row["description"],
        "kind": row["kind"],
        "threshold": row["threshold"],
        "severity": row["severity"],
        "enabled": bool(row["enabled"]),
        "updatedAt": row["updated_at"],
        "configuredBy": row["configured_by_user_id"] or "Care team",
    }


def _bump_twin(
    store: Store,
    *,
    patient: dict[str, Any],
    twin: dict[str, Any],
    now: str,
    reason: str,
) -> int:
    milestones = store.list_milestones(patient["id"])
    alerts = store.list_alerts(patient["id"])
    status, status_reason = twin_service.compute_status(alerts, milestones)
    version = int(twin["version"]) + 1
    store.update_twin(
        twin["id"],
        version=version,
        status=status,
        reason=status_reason,
        updated_at=now,
    )
    twin["version"] = version
    twin["status"] = status
    twin["updated_at"] = now
    snapshot = twin_service.snapshot_payload(store, patient=patient, twin=twin)
    store.create_snapshot(
        {
            "id": new_id("snp"),
            "patient_id": patient["id"],
            "twin_id": twin["id"],
            "version": version,
            "reason": reason,
            "snapshot_json": json.dumps(snapshot, separators=(",", ":")),
            "created_at": now,
        }
    )
    return version


def verify_medication(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    medication_id: str,
    payload: MedicationVerifyRequest,
) -> dict[str, Any]:
    access = require_clinician(store, user, patient_id, "medications:verify")
    patient = access.patient
    medication = store.get_medication(patient_id, medication_id)
    if not medication:
        raise not_found("Medication instruction")
    engine = SafetyValidationEngine(store)
    decision = engine.validate_medication_verification(
        patient=patient, user=user, medication=medication
    )

    now = iso()
    store.verify_medication(medication_id, user["id"], now)
    if medication.get("evidence_id"):
        store.update_evidence_verification(medication["evidence_id"], "clinician_verified")

    twin = store.get_twin(patient_id)
    assert twin is not None
    event_id = new_id("evt")
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "medication_verified",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "discharge_document",
            "evidence_id": medication.get("evidence_id"),
            "verification_status": "clinician_verified",
            "title": f"Medication instruction verified · {medication['name']}",
            "description": (
                f"{user['name']} reviewed the extracted instruction against its source."
                + (f" Note: {payload.note}" if payload.note else "")
            ),
            "payload_json": json.dumps(
                {"medicationId": medication_id, "evidenceId": medication.get("evidence_id")},
                separators=(",", ":"),
            ),
            "review_status": "reviewed",
            "created_at": now,
        }
    )
    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "action": "medication.verified",
            "entity_type": "medication_instruction",
            "entity_id": medication_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {"eventId": event_id, "note": payload.note},
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )
    version = _bump_twin(
        store, patient=patient, twin=twin, now=now, reason="Medication verified"
    )
    updated = store.get_medication(patient_id, medication_id)
    assert updated is not None
    return {
        "medication": twin_service._medication_dto(store, patient_id, updated),
        "eventId": event_id,
        "safetyDecision": decision,
        "twinVersion": version,
    }


def update_milestone(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    milestone_id: str,
    payload: MilestoneUpdateRequest,
) -> dict[str, Any]:
    access = require_clinician(store, user, patient_id, "twin:read")
    patient = access.patient
    milestone = store.get_milestone(patient_id, milestone_id)
    if not milestone:
        raise not_found("Recovery milestone")
    engine = SafetyValidationEngine(store)
    decision = engine.validate_milestone_update(
        patient=patient, user=user, milestone=milestone, status=payload.status
    )

    now = iso()
    completed_at = now if payload.status == "completed" else None
    store.update_milestone(milestone_id, payload.status, completed_at, now)
    twin = store.get_twin(patient_id)
    assert twin is not None
    event_id = new_id("evt")
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "milestone_completed",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "clinician_note",
            "evidence_id": milestone.get("evidence_id"),
            "verification_status": "clinician_verified",
            "title": f"Milestone updated · {milestone['title']}",
            "description": (
                f"{user['name']} changed milestone status to {payload.status}."
                + (f" Note: {payload.note}" if payload.note else "")
            ),
            "payload_json": json.dumps(
                {"milestoneId": milestone_id, "status": payload.status},
                separators=(",", ":"),
            ),
            "review_status": "reviewed",
            "created_at": now,
        }
    )
    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "action": "milestone.updated",
            "entity_type": "recovery_milestone",
            "entity_id": milestone_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {"status": payload.status, "eventId": event_id},
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )
    version = _bump_twin(
        store, patient=patient, twin=twin, now=now, reason="Milestone updated"
    )
    updated = store.get_milestone(patient_id, milestone_id)
    assert updated is not None
    return {
        "milestone": twin_service._milestone_dto(store, patient_id, updated),
        "eventId": event_id,
        "safetyDecision": decision,
        "twinVersion": version,
    }


def run_monitoring_sweep_for_clinician(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> dict[str, Any]:
    from app.services.monitoring import run_monitoring_sweep

    access = require_clinician(store, user, patient_id, "alerts:read")
    patient = access.patient
    result = run_monitoring_sweep(store, patient=patient, clinician=user)
    if result["alertsCreated"]:
        twin = store.get_twin(patient_id)
        assert twin is not None
        version = _bump_twin(
            store,
            patient=patient,
            twin=twin,
            now=result["evaluatedAt"],
            reason="Deterministic monitoring sweep",
        )
        result["twinVersion"] = version
    result["alertsCreated"] = [
        twin_service._alert_dto(store, patient_id, alert)
        for alert in result["alertsCreated"]
    ]
    return result


def list_rules(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> list[dict[str, Any]]:
    from app.services.auth import require_access

    require_access(store, user, patient_id, "alerts:read")
    return [_rule_dto(row) for row in store.list_rules(patient_id)]


def update_rule(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    rule_id: str,
    payload: MonitoringRuleUpdateRequest,
) -> dict[str, Any]:
    access = require_clinician(store, user, patient_id, "rules:write")
    patient = access.patient
    rule = store.get_rule(patient_id, rule_id)
    if not rule:
        raise not_found("Monitoring rule")
    engine = SafetyValidationEngine(store)
    decision = engine.validate_rule_update(
        patient=patient,
        user=user,
        rule=rule,
        threshold=payload.threshold,
    )
    now = iso()
    store.update_rule(
        rule_id,
        threshold=payload.threshold,
        enabled=payload.enabled,
        configured_by_user_id=user["id"],
        updated_at=now,
    )
    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "action": "monitoring_rule.updated",
            "entity_type": "monitoring_rule",
            "entity_id": rule_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {
                    "threshold": payload.threshold,
                    "enabled": payload.enabled,
                    "previousThreshold": rule["threshold"],
                    "previousEnabled": bool(rule["enabled"]),
                },
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )
    updated = store.get_rule(patient_id, rule_id)
    assert updated is not None
    return {
        "rule": _rule_dto(updated),
        "safetyDecision": decision,
    }
