from __future__ import annotations

import json
from typing import Any

from app.domain.schemas import AlertAcknowledgeRequest, AlertResolveRequest
from app.errors import not_found
from app.repositories.store import Store
from app.safety.engine import SafetyValidationEngine
from app.services import twin_service
from app.services.auth import require_access, require_clinician
from app.utils import iso, new_id


def list_alerts(store: Store, *, user: dict[str, Any], patient_id: str) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "alerts:read")
    return [
        twin_service._alert_dto(store, patient_id, row)
        for row in store.list_alerts(patient_id)
    ]


def acknowledge_alert(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    alert_id: str,
    payload: AlertAcknowledgeRequest,
) -> dict[str, Any]:
    access = require_clinician(store, user, patient_id, "alerts:read")
    patient = access.patient
    alert = store.get_alert(patient_id, alert_id)
    if not alert:
        raise not_found("Safety alert")
    engine = SafetyValidationEngine(store)
    decision = engine.validate_alert_acknowledgement(
        patient=patient, user=user, alert=alert
    )

    now = iso()
    store.acknowledge_alert(
        alert_id,
        user_id=user["id"],
        name=user["name"],
        acknowledged_at=now,
        note=payload.note,
    )
    twin = store.get_twin(patient_id)
    assert twin is not None
    event_id = new_id("evt")
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "alert_acknowledged",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "clinician_note",
            "evidence_id": alert.get("evidence_id"),
            "verification_status": "clinician_verified",
            "title": "Safety alert acknowledged",
            "description": (
                f"{user['name']} acknowledged the rule-based alert: {alert['title']}."
                + (f" Note: {payload.note}" if payload.note else "")
            ),
            "payload_json": json.dumps(
                {"alertId": alert_id, "ruleId": alert["rule_id"]},
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
            "action": "safety_alert.acknowledged",
            "entity_type": "safety_alert",
            "entity_id": alert_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {"eventId": event_id, "note": payload.note},
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )

    milestones = store.list_milestones(patient_id)
    all_alerts = store.list_alerts(patient_id)
    status, reason = twin_service.compute_status(all_alerts, milestones)
    version = int(twin["version"]) + 1
    store.update_twin(
        twin["id"], version=version, status=status, reason=reason, updated_at=now
    )
    twin["version"] = version
    twin["status"] = status
    twin["updated_at"] = now
    snapshot = twin_service.snapshot_payload(store, patient=patient, twin=twin)
    store.create_snapshot(
        {
            "id": new_id("snp"),
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "version": version,
            "reason": "Safety alert acknowledged",
            "snapshot_json": json.dumps(snapshot, separators=(",", ":")),
            "created_at": now,
        }
    )

    updated = store.get_alert(patient_id, alert_id)
    assert updated is not None
    return {
        "alert": twin_service._alert_dto(store, patient_id, updated),
        "eventId": event_id,
        "safetyDecision": decision,
    }


def resolve_alert(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    alert_id: str,
    payload: AlertResolveRequest,
) -> dict[str, Any]:
    access = require_clinician(store, user, patient_id, "alerts:read")
    patient = access.patient
    alert = store.get_alert(patient_id, alert_id)
    if not alert:
        raise not_found("Safety alert")
    engine = SafetyValidationEngine(store)
    decision = engine.validate_alert_resolution(
        patient=patient, user=user, alert=alert, note=payload.note
    )

    now = iso()
    store.resolve_alert(
        alert_id,
        user_id=user["id"],
        name=user["name"],
        resolved_at=now,
        note=payload.note,
    )
    twin = store.get_twin(patient_id)
    assert twin is not None
    event_id = new_id("evt")
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "alert_resolved",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "clinician_note",
            "evidence_id": alert.get("evidence_id"),
            "verification_status": "clinician_verified",
            "title": "Safety alert resolved",
            "description": (
                f"{user['name']} resolved the rule-based alert: {alert['title']}. "
                f"Rationale: {payload.note}"
            ),
            "payload_json": json.dumps(
                {"alertId": alert_id, "ruleId": alert["rule_id"]},
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
            "action": "safety_alert.resolved",
            "entity_type": "safety_alert",
            "entity_id": alert_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {"eventId": event_id, "note": payload.note},
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )

    milestones = store.list_milestones(patient_id)
    all_alerts = store.list_alerts(patient_id)
    status, reason = twin_service.compute_status(all_alerts, milestones)
    version = int(twin["version"]) + 1
    store.update_twin(
        twin["id"], version=version, status=status, reason=reason, updated_at=now
    )
    twin["version"] = version
    twin["status"] = status
    twin["updated_at"] = now
    snapshot = twin_service.snapshot_payload(store, patient=patient, twin=twin)
    store.create_snapshot(
        {
            "id": new_id("snp"),
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "version": version,
            "reason": "Safety alert resolved",
            "snapshot_json": json.dumps(snapshot, separators=(",", ":")),
            "created_at": now,
        }
    )

    updated = store.get_alert(patient_id, alert_id)
    assert updated is not None
    return {
        "alert": twin_service._alert_dto(store, patient_id, updated),
        "eventId": event_id,
        "safetyDecision": decision,
        "twinVersion": version,
    }
