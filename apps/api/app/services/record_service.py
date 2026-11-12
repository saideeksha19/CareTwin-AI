from __future__ import annotations

from typing import Any

from app.errors import forbidden
from app.repositories.store import Store
from app.services import twin_service
from app.services.auth import require_access, require_clinician
from app.utils import iso


def list_checkins(
    store: Store, *, user: dict[str, Any], patient_id: str, limit: int
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    return [
        twin_service._checkin_dto(store, patient_id, row)
        for row in store.list_checkins(patient_id, limit=min(max(limit, 1), 50))
    ]


def list_observations(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    return [
        twin_service._observation_dto(store, patient_id, row)
        for row in store.list_observations(patient_id)
    ]


def list_evidence(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    rows = store.list_evidence(patient_id)
    if user["role"] == "caregiver":
        rows = [row for row in rows if row["source_type"] != "clinician_note"]
    return [twin_service.evidence_dto(store, patient_id, row["id"]) for row in rows]


def get_timeline(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    event_type: str | None,
    source_type: str | None,
    verification_status: str | None,
    limit: int,
) -> dict[str, Any]:
    require_access(store, user, patient_id, "timeline:read")
    rows = store.list_events(
        patient_id,
        event_type=event_type,
        source_type=source_type,
        verification_status=verification_status,
        limit=min(max(limit, 1), 500),
    )
    events: list[dict[str, Any]] = []
    for row in rows:
        evidence = twin_service.evidence_dto(store, patient_id, row.get("evidence_id"))
        if (
            user["role"] == "caregiver"
            and evidence
            and evidence["sourceType"] == "clinician_note"
        ):
            continue
        events.append(
            {
                "id": row["id"],
                "patientId": row["patient_id"],
                "eventType": row["event_type"],
                "occurredAt": row["occurred_at"],
                "recordedAt": row["recorded_at"],
                "actorName": row["actor_name"],
                "actorRole": row["actor_role"],
                "sourceType": row["source_type"],
                "evidenceId": row.get("evidence_id"),
                "verificationStatus": row["verification_status"],
                "title": row["title"],
                "description": row["description"],
                "payload": row["payload"],
                "reviewStatus": row["review_status"],
                "evidence": evidence,
            }
        )
    return {
        "patientId": patient_id,
        "generatedAt": iso(),
        "total": len(events),
        "events": events,
    }


def list_audit(
    store: Store, *, user: dict[str, Any], patient_id: str, limit: int
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    if user["role"] == "caregiver":
        raise forbidden("The audit trail is available to the patient and care team only.")
    rows = store.list_audit(patient_id, limit=min(max(limit, 1), 200))
    return [
        {
            "id": row["id"],
            "action": row["action"],
            "entityType": row["entity_type"],
            "entityId": row["entity_id"],
            "actorName": row["actor_name"],
            "actorRole": row["actor_role"],
            "outcome": row["outcome"],
            "details": row["details"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def list_snapshots(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    rows = store.list_snapshots(patient_id)
    return [
        {
            "id": row["id"],
            "version": row["version"],
            "reason": row["reason"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def get_snapshot(
    store: Store, *, user: dict[str, Any], patient_id: str, snapshot_id: str
) -> dict[str, Any] | None:
    require_access(store, user, patient_id, "twin:read")
    row = store.get_snapshot(patient_id, snapshot_id)
    if not row:
        return None
    return {
        "id": row["id"],
        "version": row["version"],
        "reason": row["reason"],
        "createdAt": row["created_at"],
        "snapshot": row["snapshot"],
    }


def list_safety_decisions(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    if user["role"] == "caregiver":
        raise forbidden("Safety decisions are available to the patient and care team only.")
    return [
        {
            "id": row["id"],
            "patientId": row["patient_id"],
            "operation": row["operation"],
            "outcome": row["outcome"],
            "checks": row["checks"],
            "actorName": row["actor_name"],
            "actorRole": row["actor_role"],
            "createdAt": row["created_at"],
        }
        for row in store.list_safety_decisions(patient_id)
    ]


def list_accessible_patients(
    store: Store, *, user: dict[str, Any]
) -> list[dict[str, Any]]:
    if user["role"] != "clinician":
        raise forbidden("The cohort view is clinician-only.")
    result: list[dict[str, Any]] = []
    for patient in store.list_patients():
        relationship = store.get_relationship(patient["id"], user["id"])
        if not relationship or relationship["status"] != "active":
            continue
        twin = store.get_twin(patient["id"])
        if not twin:
            continue
        twin_payload = twin_service.build_twin(
            store,
            patient=patient,
            twin=twin,
            role=user["role"],
            scopes=("*",),
        )
        result.append(
            {
                "id": patient["id"],
                "fullName": patient["full_name"],
                "preferredName": patient["preferred_name"],
                "condition": patient["condition"],
                "dischargedOn": patient["discharged_on"],
                "postDischargeDay": twin_payload["patient"]["postDischargeDay"],
                "status": twin_payload["status"],
                "statusReason": twin_payload["statusReason"],
                "progress": twin_payload["progress"],
                "openAlerts": len(twin_payload["openAlerts"]),
                "nextFollowUp": twin_payload["nextFollowUp"],
                "synthetic": twin_payload["patient"]["synthetic"],
            }
        )
    return result
