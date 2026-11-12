from __future__ import annotations

import json
from typing import Any

from app.domain.schemas import ConsentUpdateRequest
from app.errors import not_found
from app.repositories.store import Store
from app.safety.engine import SafetyValidationEngine
from app.services.auth import require_access, require_patient_self
from app.utils import iso, new_id


def _consent_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "patientId": row["patient_id"],
        "granteeUserId": row["grantee_user_id"],
        "granteeName": row.get("grantee_name", ""),
        "granteeRelationship": row["grantee_relationship"],
        "scopes": row["scopes"],
        "status": row["status"],
        "grantedAt": row["granted_at"],
        "updatedAt": row["updated_at"],
    }


def list_consents(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "consents:read")
    return [_consent_dto(row) for row in store.list_consents(patient_id)]


def update_consent(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    consent_id: str,
    payload: ConsentUpdateRequest,
) -> dict[str, Any]:
    access = require_patient_self(store, user, patient_id)
    patient = access.patient
    consent = store.get_consent(patient_id, consent_id)
    if not consent:
        raise not_found("Consent record")
    engine = SafetyValidationEngine(store)
    decision = engine.validate_consent_update(
        patient=patient, user=user, consent=consent
    )

    now = iso()
    store.update_consent_status(consent_id, payload.status, now)
    twin = store.get_twin(patient_id)
    assert twin is not None
    event_id = new_id("evt")
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "consent_updated",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "system_demo",
            "evidence_id": None,
            "verification_status": "patient_reported",
            "title": f"Caregiver sharing {payload.status}",
            "description": (
                f"{user['name']} {payload.status} sharing with "
                f"{consent.get('grantee_name', 'caregiver')}."
                + (f" Reason: {payload.reason}" if payload.reason else "")
            ),
            "payload_json": json.dumps(
                {
                    "consentId": consent_id,
                    "status": payload.status,
                    "scopes": consent["scopes"],
                },
                separators=(",", ":"),
            ),
            "review_status": "not_required",
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
            "action": "consent.updated",
            "entity_type": "consent_record",
            "entity_id": consent_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {
                    "status": payload.status,
                    "granteeUserId": consent["grantee_user_id"],
                    "eventId": event_id,
                },
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )

    updated = store.get_consent(patient_id, consent_id)
    assert updated is not None
    return {
        "consent": _consent_dto(updated),
        "eventId": event_id,
        "safetyDecision": decision,
    }
