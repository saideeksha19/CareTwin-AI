from __future__ import annotations

import json
from typing import Any

from app.domain.schemas import CreateEncounterRequest, CreateLabResultRequest
from app.errors import not_found, validation_error
from app.repositories.store import Store
from app.services import twin_service
from app.services.auth import require_access, require_clinician
from app.utils import iso, new_id, parse_iso


def _validate_iso(value: str, field: str) -> str:
    try:
        parse_iso(value)
    except Exception as exc:
        raise validation_error(f"{field} must be a valid ISO datetime.") from exc
    return value


def _bump_twin(store: Store, *, patient: dict[str, Any], now: str, reason: str) -> int:
    twin = store.get_twin(patient["id"])
    assert twin is not None
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


def _lab_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = twin_service.evidence_dto(store, patient_id, row.get("evidence_id"))
    return {
        "id": row["id"],
        "testCode": row["test_code"],
        "testName": row["test_name"],
        "panel": row.get("panel") or "",
        "specimen": row.get("specimen") or "",
        "collectedAt": row["collected_at"],
        "resultedAt": row.get("resulted_at"),
        "valueNumeric": row.get("value_numeric"),
        "valueText": row.get("value_text") or "",
        "unit": row.get("unit") or "",
        "sourceRangeLow": row.get("source_range_low"),
        "sourceRangeHigh": row.get("source_range_high"),
        "sourceRangeText": row.get("source_range_text") or "",
        "clinicianRangeLow": row.get("clinician_range_low"),
        "clinicianRangeHigh": row.get("clinician_range_high"),
        "clinicianRangeText": row.get("clinician_range_text") or "",
        "comparisonStatus": row.get("comparison_status") or "unavailable",
        "comparisonNote": row.get("comparison_note") or "",
        "ambiguityNote": row.get("ambiguity_note") or "",
        "verificationStatus": row.get("verification_status") or "document_extracted",
        "encounterId": row.get("encounter_id"),
        "evidenceId": row.get("evidence_id"),
        "evidence": evidence,
        "provenance": twin_service._provenance(
            verification_status=row.get("verification_status") or "document_extracted",
            evidence=evidence,
            actor_name=row.get("verified_by_name") or "Clinical team",
            actor_role="clinician" if row.get("verification_status") == "clinician_verified" else "system",
        ),
    }


def _encounter_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = twin_service.evidence_dto(store, patient_id, row.get("evidence_id"))
    links = store.list_encounter_links(row["id"])
    return {
        "id": row["id"],
        "encounterType": row.get("encounter_type") or "",
        "occurredAt": row["occurred_at"],
        "endedAt": row.get("ended_at"),
        "facility": row.get("facility") or "",
        "providerName": row.get("provider_name") or "",
        "providerSpecialty": row.get("provider_specialty") or "",
        "reason": row.get("reason") or "",
        "summary": row.get("summary") or "",
        "dischargeInstructions": row.get("discharge_instructions") or "",
        "followUpPlan": row.get("follow_up_plan") or "",
        "sourceDocument": row.get("source_document") or "",
        "verificationStatus": row.get("verification_status") or "document_extracted",
        "evidenceId": row.get("evidence_id"),
        "evidence": evidence,
        "links": [
            {
                "id": link["id"],
                "entityType": link.get("target_type") or link.get("entity_type"),
                "entityId": link.get("target_id") or link.get("entity_id"),
                "label": link.get("label") or "",
            }
            for link in links
        ],
        "provenance": twin_service._provenance(
            verification_status=row.get("verification_status") or "document_extracted",
            evidence=evidence,
            actor_name=row.get("provider_name") or "Clinical team",
            actor_role="clinician" if row.get("verification_status") == "clinician_verified" else "system",
        ),
    }


def list_lab_results(store: Store, *, user: dict[str, Any], patient_id: str) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    return [_lab_dto(store, patient_id, row) for row in store.list_lab_results(patient_id)]


def create_lab_result(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    payload: CreateLabResultRequest,
) -> dict[str, Any]:
    access = require_access(store, user, patient_id, "clinical:write")
    if user.get("role") != "clinician":
        from app.errors import forbidden as _forbidden
        raise _forbidden("Only a clinician can perform this action.")
    patient = access.patient
    collected_at = _validate_iso(payload.collected_at, "collected_at")
    resulted_at = _validate_iso(payload.resulted_at, "resulted_at") if payload.resulted_at else None
    if payload.encounter_id and not store.get_encounter(patient_id, payload.encounter_id):
        raise not_found("Clinical encounter")
    now = iso()
    lab_id = new_id("lab")
    evidence_id = new_id("src")
    event_id = new_id("evt")
    twin = store.get_twin(patient_id)
    assert twin is not None
    value_display = (
        f"{payload.value_numeric}{(' ' + payload.unit) if payload.unit else ''}".strip()
        if payload.value_numeric is not None
        else payload.value_text.strip()
    )
    store.create_evidence(
        {
            "id": evidence_id,
            "patient_id": patient_id,
            "source_type": payload.source_type,
            "title": payload.evidence_title or f"Lab result · {payload.test_name}",
            "excerpt": payload.evidence_excerpt
            or f"{payload.test_name}: {value_display or 'value recorded'} (exact supplied value).",
            "document_name": payload.evidence_document_name,
            "page_ref": payload.evidence_page_ref,
            "synthetic": 1 if patient.get("synthetic") else 0,
            "verification_status": payload.verification_status,
            "extracted_by_ai": 0,
            "captured_at": resulted_at or collected_at,
            "created_at": now,
        }
    )
    range_source = "provided" if any([
        payload.source_range_low is not None,
        payload.source_range_high is not None,
        payload.source_range_text.strip(),
        payload.clinician_range_low is not None,
        payload.clinician_range_high is not None,
        payload.clinician_range_text.strip(),
    ]) else "none"
    store.create_lab_result(
        {
            "id": lab_id,
            "patient_id": patient_id,
            "encounter_id": payload.encounter_id,
            "panel": payload.panel.strip(),
            "test_code": payload.test_code.strip(),
            "test_name": payload.test_name.strip(),
            "specimen": payload.specimen.strip(),
            "collected_at": collected_at,
            "resulted_at": resulted_at,
            "value_numeric": payload.value_numeric,
            "value_text": payload.value_text.strip(),
            "unit": payload.unit.strip(),
            "source_range_low": payload.source_range_low,
            "source_range_high": payload.source_range_high,
            "source_range_text": payload.source_range_text.strip(),
            "clinician_range_low": payload.clinician_range_low,
            "clinician_range_high": payload.clinician_range_high,
            "clinician_range_text": payload.clinician_range_text.strip(),
            "range_source": range_source,
            "comparison_status": payload.comparison_status,
            "comparison_note": payload.comparison_note.strip(),
            "ambiguity_note": payload.ambiguity_note.strip(),
            "verification_status": payload.verification_status,
            "evidence_id": evidence_id,
            "synthetic": 1 if patient.get("synthetic") else 0,
            "created_by_user_id": user["id"],
            "verified_by_user_id": user["id"] if payload.verification_status == "clinician_verified" else None,
            "verified_by_name": user["name"] if payload.verification_status == "clinician_verified" else None,
            "verified_at": now if payload.verification_status == "clinician_verified" else None,
            "created_at": now,
            "updated_at": now,
        }
    )
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "lab_result_recorded",
            "occurred_at": collected_at,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": payload.source_type,
            "evidence_id": evidence_id,
            "verification_status": payload.verification_status,
            "title": f"Lab result recorded · {payload.test_name}",
            "description": (
                f"{payload.test_name}: {value_display or 'recorded'}"
                + (f" (unit: {payload.unit})" if payload.unit else "")
                + ". Source/reference ranges and units are stored exactly as supplied; none inferred."
            ),
            "payload_json": json.dumps(
                {
                    "labResultId": lab_id,
                    "testCode": payload.test_code,
                    "comparisonStatus": payload.comparison_status,
                    "valueNumeric": payload.value_numeric,
                    "unit": payload.unit,
                },
                separators=(",", ":"),
            ),
            "review_status": "reviewed" if payload.verification_status == "clinician_verified" else "recorded",
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
            "action": "lab_result.created",
            "entity_type": "lab_result",
            "entity_id": lab_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {"evidenceId": evidence_id, "eventId": event_id, "testName": payload.test_name},
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )
    version = _bump_twin(store, patient=patient, now=now, reason="Lab result recorded")
    store.conn.commit()
    row = store.get_lab_result(patient_id, lab_id)
    assert row
    return {"labResult": _lab_dto(store, patient_id, row), "eventId": event_id, "twinVersion": version}


def list_encounters(store: Store, *, user: dict[str, Any], patient_id: str) -> list[dict[str, Any]]:
    require_access(store, user, patient_id, "twin:read")
    return [_encounter_dto(store, patient_id, row) for row in store.list_encounters(patient_id)]


def create_encounter(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    payload: CreateEncounterRequest,
) -> dict[str, Any]:
    access = require_access(store, user, patient_id, "clinical:write")
    if user.get("role") != "clinician":
        from app.errors import forbidden as _forbidden
        raise _forbidden("Only a clinician can perform this action.")
    patient = access.patient
    occurred_at = _validate_iso(payload.occurred_at, "occurred_at")
    ended_at = _validate_iso(payload.ended_at, "ended_at") if payload.ended_at else None
    now = iso()
    encounter_id = new_id("enc")
    evidence_id = new_id("src")
    event_id = new_id("evt")
    twin = store.get_twin(patient_id)
    assert twin is not None
    store.create_evidence(
        {
            "id": evidence_id,
            "patient_id": patient_id,
            "source_type": payload.source_type,
            "title": payload.evidence_title or f"Clinical encounter · {payload.encounter_type}",
            "excerpt": payload.evidence_excerpt or payload.summary[:500],
            "document_name": payload.evidence_document_name,
            "page_ref": payload.evidence_page_ref,
            "synthetic": 1 if patient.get("synthetic") else 0,
            "verification_status": payload.verification_status,
            "extracted_by_ai": 0,
            "captured_at": occurred_at,
            "created_at": now,
        }
    )
    store.create_encounter(
        {
            "id": encounter_id,
            "patient_id": patient_id,
            "encounter_type": payload.encounter_type.strip(),
            "occurred_at": occurred_at,
            "ended_at": ended_at,
            "facility": payload.facility.strip(),
            "provider_name": payload.provider_name.strip() or user["name"],
            "provider_specialty": payload.provider_specialty.strip(),
            "clinician_user_id": user["id"],
            "reason": payload.reason.strip(),
            "summary": payload.summary.strip(),
            "discharge_instructions": payload.discharge_instructions.strip(),
            "follow_up_plan": payload.follow_up_plan.strip(),
            "source_document": payload.source_document.strip(),
            "evidence_id": evidence_id,
            "verification_status": payload.verification_status,
            "review_status": "reviewed" if payload.verification_status == "clinician_verified" else "pending",
            "created_by_user_id": user["id"],
            "created_at": now,
            "updated_at": now,
        }
    )
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "clinical_encounter_recorded",
            "occurred_at": occurred_at,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": payload.source_type,
            "evidence_id": evidence_id,
            "verification_status": payload.verification_status,
            "title": f"Clinical encounter · {payload.encounter_type}",
            "description": payload.summary.strip(),
            "payload_json": json.dumps(
                {
                    "encounterId": encounter_id,
                    "facility": payload.facility,
                    "provider": payload.provider_name or user["name"],
                },
                separators=(",", ":"),
            ),
            "review_status": "reviewed" if payload.verification_status == "clinician_verified" else "recorded",
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
            "action": "encounter.created",
            "entity_type": "clinical_encounter",
            "entity_id": encounter_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {"evidenceId": evidence_id, "eventId": event_id, "encounterType": payload.encounter_type},
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )
    version = _bump_twin(store, patient=patient, now=now, reason="Clinical encounter recorded")
    store.conn.commit()
    row = store.get_encounter(patient_id, encounter_id)
    assert row
    return {"encounter": _encounter_dto(store, patient_id, row), "eventId": event_id, "twinVersion": version}
