from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.repositories.store import Store
from app.utils import iso, parse_iso

ROLE_LABELS = {"patient": "patient", "caregiver": "caregiver", "clinician": "clinician"}


def _age(date_of_birth: str) -> int:
    try:
        born = date.fromisoformat(date_of_birth)
    except ValueError:
        return 0
    today = datetime.now(timezone.utc).date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _post_discharge_day(discharged_on: str) -> int:
    try:
        discharged = date.fromisoformat(discharged_on)
    except ValueError:
        return 1
    today = datetime.now(timezone.utc).date()
    return max(1, (today - discharged).days + 1)


def evidence_dto(store: Store, patient_id: str, evidence_id: str | None) -> dict[str, Any] | None:
    if not evidence_id:
        return None
    row = store.get_evidence(patient_id, evidence_id)
    if not row:
        return None
    return {
        "id": row["id"],
        "sourceType": row["source_type"],
        "title": row["title"],
        "documentName": row["document_name"],
        "pageRef": row["page_ref"],
        "excerpt": row["excerpt"],
        "synthetic": bool(row["synthetic"]),
        "verificationStatus": row["verification_status"],
        "extractedByAi": bool(row["extracted_by_ai"]),
        "capturedAt": row["captured_at"],
    }


def _provenance(
    *,
    verification_status: str,
    evidence: dict[str, Any] | None,
    actor_name: str | None = None,
    actor_role: str | None = None,
) -> dict[str, Any]:
    if actor_name and actor_role:
        name, role = actor_name, actor_role
    elif verification_status == "clinician_verified":
        name, role = "Care team", "clinician"
    elif verification_status in {"document_extracted", "awaiting_review", "ai_generated"}:
        name, role = "Document Intelligence Agent", "system"
    elif verification_status == "patient_reported":
        name, role = "Patient", "patient"
    elif verification_status == "caregiver_reported":
        name, role = "Authorized caregiver", "caregiver"
    else:
        name, role = "Synthetic demo seed", "system"
    return {
        "verificationStatus": verification_status,
        "sourceType": evidence["sourceType"] if evidence else "system_demo",
        "sourceId": evidence["id"] if evidence else None,
        "sourceLabel": (
            f'{evidence["title"]} · {evidence["pageRef"]}' if evidence else "No linked source"
        ),
        "actorName": name,
        "actorRole": role,
        "recordedAt": evidence["capturedAt"] if evidence else None,
        "synthetic": True,
        "extractedByAi": bool(evidence["extractedByAi"]) if evidence else False,
        "reviewedBy": "Care team" if verification_status == "clinician_verified" else None,
        "reviewedAt": None,
    }


def patient_dto(patient: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patient["id"],
        "mrn": patient["mrn"],
        "fullName": patient["full_name"],
        "preferredName": patient["preferred_name"],
        "dateOfBirth": patient["date_of_birth"],
        "age": _age(patient["date_of_birth"]),
        "sex": patient["sex"],
        "primaryLanguage": patient["primary_language"],
        "condition": patient["condition"],
        "dischargedOn": patient["discharged_on"],
        "postDischargeDay": _post_discharge_day(patient["discharged_on"]),
        "synthetic": bool(patient["synthetic"]),
    }


def _milestone_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = evidence_dto(store, patient_id, row.get("evidence_id"))
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "dueDate": row["due_date"],
        "status": row["status"],
        "completedAt": row["completed_at"],
        "verificationStatus": row["verification_status"],
        "evidence": evidence,
        "provenance": _provenance(
            verification_status=row["verification_status"], evidence=evidence
        ),
    }


def _medication_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = evidence_dto(store, patient_id, row.get("evidence_id"))
    return {
        "id": row["id"],
        "name": row["name"],
        "dosage": row["dosage"],
        "route": row["route"],
        "frequency": row["frequency"],
        "duration": row["duration"],
        "instructions": row["instructions"],
        "status": row["status"],
        "verificationStatus": row["verification_status"],
        "prescribedBy": row["prescribed_by"],
        "evidence": evidence,
        "provenance": _provenance(
            verification_status=row["verification_status"], evidence=evidence
        ),
    }


def _follow_up_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = evidence_dto(store, patient_id, row.get("evidence_id"))
    return {
        "id": row["id"],
        "title": row["title"],
        "clinicianName": row["clinician_name"],
        "specialty": row["specialty"],
        "scheduledFor": row["scheduled_for"],
        "location": row["location"],
        "status": row["status"],
        "notes": row["notes"],
        "verificationStatus": row["verification_status"],
        "evidence": evidence,
        "provenance": _provenance(
            verification_status=row["verification_status"], evidence=evidence
        ),
    }


def _checkin_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = evidence_dto(store, patient_id, row.get("evidence_id"))
    return {
        "id": row["id"],
        "submittedAt": row["submitted_at"],
        "submittedBy": row.get("submitted_by_name", ""),
        "overallFeeling": row["overall_feeling"],
        "painScore": row["pain_score"],
        "temperatureC": row["temperature_c"],
        "breathlessnessScore": row["breathlessness_score"],
        "adherence": row["adherence"],
        "missedDoses": row["missed_doses"],
        "notes": row["notes"],
        "symptoms": [
            {
                "code": symptom["symptom_code"],
                "label": symptom["label"],
                "severity": symptom["severity"],
                "notes": symptom["notes"],
            }
            for symptom in row.get("symptoms", [])
        ],
        "verificationStatus": row["verification_status"],
        "evidenceId": row.get("evidence_id"),
        "evidence": evidence,
        "provenance": _provenance(
            verification_status=row["verification_status"],
            evidence=evidence,
            actor_name=row.get("submitted_by_name") or "Patient",
            actor_role="patient",
        ),
    }


def _observation_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = evidence_dto(store, patient_id, row.get("evidence_id"))
    return {
        "id": row["id"],
        "observedAt": row["observed_at"],
        "caregiverName": row.get("caregiver_name", ""),
        "category": row["category"],
        "note": row["note"],
        "verificationStatus": row["verification_status"],
        "evidenceId": row.get("evidence_id"),
        "evidence": evidence,
        "provenance": _provenance(
            verification_status=row["verification_status"],
            evidence=evidence,
            actor_name=row.get("caregiver_name") or "Caregiver",
            actor_role="caregiver",
        ),
    }


def _alert_dto(store: Store, patient_id: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = evidence_dto(store, patient_id, row.get("evidence_id"))
    return {
        "id": row["id"],
        "ruleId": row["rule_id"],
        "severity": row["severity"],
        "category": row["category"],
        "title": row["title"],
        "rationale": row["rationale"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "acknowledgedBy": row.get("acknowledged_by_name"),
        "acknowledgedAt": row.get("acknowledged_at"),
        "resolvedBy": row.get("resolved_by_name"),
        "resolvedAt": row.get("resolved_at"),
        "resolutionNote": row.get("resolution_note"),
        "evidenceId": row.get("evidence_id"),
        "evidence": evidence,
        "provenance": _provenance(
            verification_status="awaiting_review",
            evidence=evidence,
            actor_name="Deterministic monitoring engine",
            actor_role="system",
        ),
    }


def compute_status(
    alerts: list[dict[str, Any]], milestones: list[dict[str, Any]]
) -> tuple[str, str]:
    unresolved = [
        alert for alert in alerts if alert["status"] in {"open", "acknowledged"}
    ]
    open_alerts = [alert for alert in unresolved if alert["status"] == "open"]
    if any(alert["severity"] == "critical" for alert in unresolved):
        if any(alert["severity"] == "critical" for alert in open_alerts):
            reason = (
                "A critical deterministic alert is open and requires clinician review."
            )
        else:
            reason = (
                "A critical deterministic alert has been acknowledged but is not "
                "resolved. Clinician follow-up remains required."
            )
        return "urgent_review", reason
    if any(alert["severity"] in {"urgent", "moderate"} for alert in unresolved):
        if open_alerts:
            reason = "One or more open rule-based concerns require review."
        else:
            reason = (
                "Rule-based concerns have been acknowledged but not resolved. "
                "Review remains active until resolution is documented."
            )
        return "needs_attention", reason
    overdue = [m for m in milestones if m["status"] == "overdue"]
    if overdue:
        return (
            "needs_attention",
            f"{len(overdue)} recovery milestone(s) are overdue for review.",
        )
    return (
        "on_track",
        "No open rule-based concerns. Continue documented recovery plan and follow-ups.",
    )


def _visibility(role: str, scopes: tuple[str, ...]) -> dict[str, Any]:
    if role == "clinician":
        return {
            "role": role,
            "filtered": False,
            "note": "Full clinical view. Open alerts, provenance and review queues are visible.",
        }
    if role == "caregiver":
        scopes_set = set(scopes)
        missing = [
            scope
            for scope in ("schedule:read", "alerts:read")
            if scope not in scopes_set
        ]
        return {
            "role": role,
            "filtered": True,
            "note": (
                "Caregiver view is filtered by the patient's active consent scopes."
                + (f" Hidden scopes: {', '.join(missing)}." if missing else "")
            ),
        }
    return {
        "role": role,
        "filtered": False,
        "note": "This is your recovery twin. You control caregiver sharing in Consent.",
    }


def build_twin(
    store: Store,
    *,
    patient: dict[str, Any],
    twin: dict[str, Any],
    role: str,
    scopes: tuple[str, ...],
) -> dict[str, Any]:
    patient_id = patient["id"]
    scopes_set = set(scopes)
    hide_schedule = role == "caregiver" and "schedule:read" not in scopes_set
    hide_alerts = role == "caregiver" and "alerts:read" not in scopes_set

    plan = store.get_plan(patient_id)
    milestones = store.list_milestones(patient_id)
    medications = [] if hide_schedule else store.list_medications(patient_id)
    follow_ups = [] if hide_schedule else store.list_follow_ups(patient_id)
    checkins = store.list_checkins(patient_id, limit=6)
    observations = store.list_observations(patient_id)
    alerts = store.list_alerts(patient_id)
    open_alerts = [] if hide_alerts else [a for a in alerts if a["status"] == "open"]
    evidence = store.list_evidence(patient_id)

    if role == "caregiver":
        evidence = [
            item
            for item in evidence
            if item["source_type"] != "clinician_note"
        ]

    completed = len([m for m in milestones if m["status"] == "completed"])
    total = len([m for m in milestones if m["status"] != "not_applicable"])
    status, status_reason = compute_status(alerts, milestones)

    now = datetime.now(timezone.utc)
    follow_up_dtos = [_follow_up_dto(store, patient_id, row) for row in follow_ups]
    upcoming = [
        item
        for item in follow_up_dtos
        if item["status"] in {"scheduled", "upcoming"}
        and parse_iso(item["scheduledFor"]) >= now
    ]
    next_follow_up = upcoming[0] if upcoming else (follow_up_dtos[0] if follow_up_dtos else None)

    visible_evidence = evidence
    awaiting_review = len(
        [
            item
            for item in visible_evidence
            if item["verification_status"] in {"awaiting_review", "document_extracted"}
        ]
    )
    verified_evidence = len(
        [item for item in visible_evidence if item["verification_status"] == "clinician_verified"]
    )
    sources: dict[str, int] = {}
    for item in visible_evidence:
        sources[item["source_type"]] = sources.get(item["source_type"], 0) + 1

    med_dtos = [_medication_dto(store, patient_id, row) for row in medications]
    follow_up_for_ui = [_follow_up_dto(store, patient_id, row) for row in follow_ups]

    clinical_documents, document_findings = _document_layer(store, patient_id, role=role)

    return {
        "id": twin["id"],
        "patient": patient_dto(patient),
        "version": twin["version"],
        "status": status,
        "statusReason": status_reason,
        "updatedAt": twin["updated_at"],
        "progress": {
            "completed": completed,
            "total": total,
            "ratio": (completed / total) if total else 0,
        },
        "plan": (
            {
                "id": plan["id"],
                "title": plan["title"],
                "summary": plan["summary"],
                "startDate": plan["start_date"],
                "targetEndDate": plan["target_end_date"],
                "status": plan["status"],
            }
            if plan
            else {
                "id": "unavailable",
                "title": "No structured plan",
                "summary": "No recovery plan has been recorded.",
                "startDate": patient["discharged_on"],
                "targetEndDate": patient["discharged_on"],
                "status": "missing",
            }
        ),
        "milestones": [_milestone_dto(store, patient_id, row) for row in milestones],
        "medications": med_dtos,
        "followUps": follow_up_for_ui,
        "recentCheckIns": [_checkin_dto(store, patient_id, row) for row in checkins],
        "observations": [
            _observation_dto(store, patient_id, row) for row in observations
        ],
        "openAlerts": [_alert_dto(store, patient_id, row) for row in open_alerts],
        "evidence": [evidence_dto(store, patient_id, row["id"]) for row in visible_evidence],
        "nextFollowUp": next_follow_up,
        "dataQuality": {
            "totalEvidence": len(visible_evidence),
            "verifiedEvidence": verified_evidence,
            "awaitingReview": awaiting_review,
            "unverifiedMedicationInstructions": len(
                [
                    item
                    for item in med_dtos
                    if item["verificationStatus"] not in {"clinician_verified"}
                ]
            ),
            "sourcesByType": sources,
        },
        "visibility": _visibility(role, scopes),
        "syntheticDisclaimer": (
            "Synthetic demo patient. No real patient information. "
            "Not a medical device and not for clinical use."
        ),
        "clinicalDocuments": clinical_documents,
        "documentFindings": document_findings,
        "bodyRegionNote": (
            "The 3D twin is a visual model of the body, not a scan of this patient. "
            "CareTwin AI does not map a document to a body region unless the record itself names one, "
            "so no condition is inferred from selecting part of the model."
        ),
    }


def _document_layer(
    store: Store, patient_id: str, *, role: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Document-derived twin facts, keeping verified and pending review separate."""
    documents = store.list_documents(patient_id)
    summaries: list[dict[str, Any]] = []
    total_verified = 0
    pending_count = 0
    latest_verified: list[dict[str, Any]] = []
    for doc in documents:
        items = store.list_document_extractions(doc["id"])
        doc_verified = [i for i in items if i.get("verification_status") == "verified"]
        pending = len(items) - len(doc_verified)
        pending_count += pending
        total_verified += len(doc_verified)
        if len(summaries) < 12:
            summaries.append(
                {
                    "id": doc["id"],
                    "originalFilename": doc["original_filename"],
                    "documentType": doc["document_type"],
                    "extractionStatus": doc.get("extraction_status") or "pending",
                    "pageCount": doc.get("page_count"),
                    "uploadedAt": doc.get("uploaded_at"),
                    "verifiedCount": len(doc_verified),
                    "pendingReviewCount": pending,
                }
            )
        for item in doc_verified:
            if len(latest_verified) >= 24:
                continue
            if role == "caregiver" and doc.get("document_type") == "consultation_report":
                continue
            latest_verified.append(
                {
                    "id": item["id"],
                    "documentId": doc["id"],
                    "documentName": doc["original_filename"],
                    "label": item.get("label"),
                    "itemType": item.get("item_type"),
                    "valueText": item.get("corrected_value_text") or item.get("value_text"),
                    "unit": item.get("unit") or "",
                    "referenceRange": item.get("reference_range") or "",
                    "pageNumber": item.get("page_number"),
                    "verifiedBy": item.get("verified_by_name"),
                    "verifiedAt": item.get("verified_at"),
                    "verificationStatus": "verified",
                }
            )
    # Repeated uploads of the same report produce identical verified rows; the twin
    # shows each distinct verified finding once.
    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, ...]] = set()
    for row in latest_verified:
        key = (row["documentName"], row["label"], row["valueText"], row["pageNumber"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(row)

    document_findings = {
        "verified": deduped,
        "verifiedCount": total_verified,
        "pendingReviewCount": pending_count,
        "note": (
            "Only clinician-verified extractions appear above. Pending extractions are counted but never "
            "presented as twin facts."
        ),
    }
    return summaries, document_findings


def snapshot_payload(
    store: Store, *, patient: dict[str, Any], twin: dict[str, Any]
) -> dict[str, Any]:
    patient_id = patient["id"]
    milestones = store.list_milestones(patient_id)
    medications = store.list_medications(patient_id)
    alerts = store.list_alerts(patient_id)
    unresolved = [
        alert for alert in alerts if alert["status"] in {"open", "acknowledged"}
    ]
    completed = len([m for m in milestones if m["status"] == "completed"])
    total = len([m for m in milestones if m["status"] != "not_applicable"])
    return {
        "patientId": patient_id,
        "twinId": twin["id"],
        "version": twin["version"],
        "capturedAt": iso(),
        "status": twin["status"],
        "progress": {"completed": completed, "total": total},
        "milestones": [
            {"id": item["id"], "status": item["status"]} for item in milestones
        ],
        "medications": [
            {
                "id": item["id"],
                "name": item["name"],
                "verificationStatus": item["verification_status"],
            }
            for item in medications
        ],
        "openAlerts": [
            {
                "id": item["id"],
                "severity": item["severity"],
                "status": item["status"],
            }
            for item in unresolved
            if item["status"] == "open"
        ],
        "unresolvedAlerts": [
            {
                "id": item["id"],
                "severity": item["severity"],
                "status": item["status"],
            }
            for item in unresolved
        ],
    }
