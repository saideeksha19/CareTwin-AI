from __future__ import annotations

import json
from typing import Any

from app.domain.schemas import CreateCheckinRequest
from app.repositories.store import Store
from app.safety.engine import SafetyValidationEngine
from app.services import twin_service
from app.services.auth import require_patient_self
from app.services.monitoring import evaluate_checkin
from app.utils import iso, new_id, utc_now


def _feeling_label(value: str) -> str:
    return {"better": "better", "same": "about the same", "worse": "worse"}.get(
        value, value
    )


def create_checkin(
    store: Store,
    *,
    user: dict[str, Any],
    patient_id: str,
    payload: CreateCheckinRequest,
) -> dict[str, Any]:
    access = require_patient_self(store, user, patient_id)
    patient = access.patient
    engine = SafetyValidationEngine(store)
    raw = payload.model_dump()
    raw["symptoms"] = [symptom.model_dump() for symptom in payload.symptoms]
    decision = engine.validate_checkin_submission(
        patient=patient, user=user, payload=raw
    )

    now = iso(utc_now())
    prior_checkins = store.list_checkins(patient_id, limit=2)
    prior = prior_checkins[0] if prior_checkins else None

    symptom_summary = ", ".join(
        f"{symptom.label} {symptom.severity}/10" for symptom in payload.symptoms
    ) or "no selected symptoms"
    excerpt = (
        f"Overall feeling: {_feeling_label(payload.overall_feeling)}. "
        f"Pain {payload.pain_score}/10. Breathlessness "
        f"{payload.breathlessness_score}/10. "
        f"Temperature: "
        f"{f'{payload.temperature_c:.1f} C' if payload.temperature_c is not None else 'not recorded'}. "
        f"Adherence: {payload.adherence} ({payload.missed_doses} missed). "
        f"Reported symptoms: {symptom_summary}."
    )
    evidence_id = new_id("src")
    store.create_evidence(
        {
            "id": evidence_id,
            "patient_id": patient_id,
            "source_type": "patient_report",
            "title": f"Patient check-in · {now[:10]}",
            "document_name": "Structured patient check-in form",
            "page_ref": "Patient submission",
            "excerpt": excerpt[:1200],
            "synthetic": 1,
            "verification_status": "patient_reported",
            "extracted_by_ai": 0,
            "captured_at": now,
            "created_at": now,
        }
    )

    checkin_id = new_id("chk")
    checkin_row = {
        "id": checkin_id,
        "patient_id": patient_id,
        "submitted_by_user_id": user["id"],
        "submitted_at": now,
        "overall_feeling": payload.overall_feeling,
        "pain_score": payload.pain_score,
        "temperature_c": payload.temperature_c,
        "breathlessness_score": payload.breathlessness_score,
        "adherence": payload.adherence,
        "missed_doses": payload.missed_doses,
        "notes": payload.notes,
        "verification_status": "patient_reported",
        "evidence_id": evidence_id,
        "created_at": now,
    }
    symptoms = [
        {
            "id": new_id("sym"),
            "checkin_id": checkin_id,
            "patient_id": patient_id,
            "symptom_code": symptom.code,
            "label": symptom.label,
            "severity": symptom.severity,
            "notes": symptom.notes,
            "created_at": now,
        }
        for symptom in payload.symptoms
    ]
    store.create_checkin(checkin_row, symptoms)

    twin = store.get_twin(patient_id)
    assert twin is not None
    event_id = new_id("evt")
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "event_type": "checkin_submitted",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "source_type": "patient_report",
            "evidence_id": evidence_id,
            "verification_status": "patient_reported",
            "title": "Patient check-in recorded",
            "description": excerpt,
            "payload_json": json.dumps(
                {
                    "checkinId": checkin_id,
                    "overallFeeling": payload.overall_feeling,
                    "painScore": payload.pain_score,
                    "temperatureC": payload.temperature_c,
                    "breathlessnessScore": payload.breathlessness_score,
                    "adherence": payload.adherence,
                    "missedDoses": payload.missed_doses,
                    "symptomCodes": [symptom.code for symptom in payload.symptoms],
                },
                separators=(",", ":"),
            ),
            "review_status": "not_required",
            "created_at": now,
        }
    )

    checkin_for_rules = {
        "id": checkin_id,
        "pain_score": payload.pain_score,
        "temperature_c": payload.temperature_c,
        "missed_doses": payload.missed_doses,
        "symptoms": [
            {"symptom_code": symptom.code, "severity": symptom.severity}
            for symptom in payload.symptoms
        ],
    }
    deduplicated_alerts: list[dict[str, Any]] = []
    alerts = evaluate_checkin(
        store,
        patient=patient,
        checkin=checkin_for_rules,
        prior_checkin=prior,
        evidence_id=evidence_id,
        deduplicated=deduplicated_alerts,
    )

    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": user["id"],
            "actor_name": user["name"],
            "actor_role": user["role"],
            "action": "checkin.created",
            "entity_type": "patient_checkin",
            "entity_id": checkin_id,
            "outcome": "allowed",
            "details_json": json.dumps(
                {
                    "eventId": event_id,
                    "evidenceId": evidence_id,
                    "alertsCreated": len(alerts),
                    "alertsDeduplicated": len(deduplicated_alerts),
                },
                separators=(",", ":"),
            ),
            "created_at": now,
        }
    )

    all_alerts = store.list_alerts(patient_id)
    milestones = store.list_milestones(patient_id)
    status, status_reason = twin_service.compute_status(all_alerts, milestones)
    new_version = int(twin["version"]) + 1
    store.update_twin(
        twin["id"],
        version=new_version,
        status=status,
        reason=status_reason,
        updated_at=now,
    )
    twin["version"] = new_version
    twin["status"] = status
    twin["updated_at"] = now
    snapshot = twin_service.snapshot_payload(store, patient=patient, twin=twin)
    store.create_snapshot(
        {
            "id": new_id("snp"),
            "patient_id": patient_id,
            "twin_id": twin["id"],
            "version": new_version,
            "reason": "Patient check-in recorded",
            "snapshot_json": json.dumps(snapshot, separators=(",", ":")),
            "created_at": now,
        }
    )

    monitoring_check = {
        "code": "deterministic_monitoring",
        "label": "Clinician-configured rules were evaluated",
        "passed": True,
        "detail": (
            f"{len(alerts)} new rule-based alert(s) created; "
            f"{len(deduplicated_alerts)} existing unresolved alert(s) retained "
            "instead of creating duplicates."
        ),
    }
    decision["checks"].append(monitoring_check)
    decision["outcome"] = (
        "allowed_with_alerts" if alerts or deduplicated_alerts else "allowed"
    )
    store.update_safety_decision(
        decision["id"],
        checks=decision["checks"],
        outcome=decision["outcome"],
    )

    checkin_dto = twin_service._checkin_dto(
        store, patient_id, store.get_checkin(patient_id, checkin_id) or checkin_row
    )
    alert_dtos = [
        twin_service._alert_dto(store, patient_id, alert) for alert in alerts
    ]
    deduplicated_alert_dtos = [
        twin_service._alert_dto(store, patient_id, alert)
        for alert in deduplicated_alerts
    ]

    return {
        "checkIn": checkin_dto,
        "eventId": event_id,
        "alerts": alert_dtos,
        "deduplicatedAlerts": deduplicated_alert_dtos,
        "safetyDecision": decision,
        "twinVersion": new_version,
    }
