from __future__ import annotations

import json
from typing import Any

from app.domain.schemas import CreateObservationRequest
from app.repositories.store import Store
from app.safety.engine import SafetyValidationEngine
from app.services import twin_service
from app.services.auth import require_caregiver
from app.services.monitoring import evaluate_observation
from app.utils import iso, new_id


def create_observation(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    payload: CreateObservationRequest,
) -> dict[str, Any]:
    access = require_caregiver(store, user, patient_id, "observations:write")
    patient = access.patient
    engine = SafetyValidationEngine(store)
    decision = engine.validate_observation(
        patient=patient,
        user=user,
        scopes=access.scopes,
        note=payload.note,
    )

    now = iso()
    evidence_id = new_id("src")
    store.create_evidence(
        {
            "id": evidence_id,
            "patient_id": patient_id,
            "source_type": "caregiver_report",
            "title": f"Caregiver observation · {now[:10]}",
            "document_name": "Caregiver observation form",
            "page_ref": "Caregiver submission",
            "excerpt": payload.note[:1200],
            "synthetic": 1,
            "verification_status": "caregiver_reported",
            "extracted_by_ai": 0,
            "captured_at": now,
            "created_at": now,
        }
    )
    observation = {
        "id": new_id("obs"),
        "patient_id": patient_id,
        "caregiver_user_id": user["id"],
        "observed_at": now,
        "category": payload.category,
        "note": payload.note,
        "verification_status": "caregiver_reported",
        "evidence_id": evidence_id,
        "created_at": now,
    }
    store.create_observation(observation)

    twin = store.get_twin(patient_id)
    assert twin is not None
    event_id = new_id("evt")
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "observation_recorded",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "caregiver_report",
            "evidence_id": evidence_id,
            "verification_status": "caregiver_reported",
            "title": f"Caregiver observation · {payload.category.replace('_', ' ')}",
            "description": payload.note,
            "payload_json": json.dumps(
                {"observationId": observation["id"], "category": payload.category},
                separators=(",", ":"),
            ),
            "review_status": "not_required",
            "created_at": now,
        }
    )

    deduplicated_alerts: list[dict[str, Any]] = []
    alerts = evaluate_observation(
        store,
        patient=patient,
        observation={
            "id": observation["id"],
            "category": payload.category,
            "note": payload.note,
        },
        evidence_id=evidence_id,
        event_id=event_id,
        now=now,
        deduplicated=deduplicated_alerts,
    )

    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "action": "caregiver_observation.created",
            "entity_type": "caregiver_observation",
            "entity_id": observation["id"],
            "outcome": "allowed",
            "details_json": json.dumps(
                {
                    "eventId": event_id,
                    "category": payload.category,
                    "alertsCreated": len(alerts),
                    "alertsDeduplicated": len(deduplicated_alerts),
                },
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )

    milestones = store.list_milestones(patient_id)
    alerts = store.list_alerts(patient_id)
    status, reason = twin_service.compute_status(alerts, milestones)
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
            "reason": "Caregiver observation recorded",
            "snapshot_json": json.dumps(snapshot, separators=(",", ":")),
            "created_at": now,
        }
    )

    row = next(
        item
        for item in store.list_observations(patient_id)
        if item["id"] == observation["id"]
    )
    return {
        "observation": twin_service._observation_dto(store, patient_id, row),
        "eventId": event_id,
        "safetyDecision": decision,
        "alerts": [twin_service._alert_dto(store, patient_id, alert) for alert in alerts],
        "deduplicatedAlerts": [
            twin_service._alert_dto(store, patient_id, alert) for alert in deduplicated_alerts
        ],
    }
