from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.repositories.store import Store
from app.services import twin_service
from app.services.monitoring import evaluate_checkin
from app.utils import iso, new_id, utc_now

PATIENT_ID = "pat_maya"
TWIN_ID = "tw_maya"
PATIENT_USER_ID = "usr_maya"
CAREGIVER_USER_ID = "usr_arjun"
CLINICIAN_USER_ID = "usr_nandini"
SECOND_CAREGIVER_USER_ID = "usr_priya"

SYNTHETIC_NOTE = "Synthetic demo patient. No real patient information."


def _event(
    store: Store,
    *,
    event_id: str,
    patient_id: str,
    event_type: str,
    occurred_at: str,
    actor_name: str,
    actor_role: str,
    source_type: str,
    evidence_id: str | None,
    verification_status: str,
    title: str,
    description: str,
    payload: dict[str, Any],
    review_status: str = "not_required",
    actor_user_id: str | None = None,
) -> None:
    store.create_event(
        {
            "id": event_id,
            "patient_id": patient_id,
            "twin_id": TWIN_ID,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "recorded_at": occurred_at,
            "actor_user_id": actor_user_id,
            "actor_name": actor_name,
            "actor_role": actor_role,
            "source_type": source_type,
            "evidence_id": evidence_id,
            "verification_status": verification_status,
            "title": title,
            "description": description,
            "payload_json": json.dumps(payload, separators=(",", ":")),
            "review_status": review_status,
            "created_at": occurred_at,
        }
    )


def _audit(
    store: Store,
    *,
    patient_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_name: str,
    actor_role: str,
    created_at: str,
    actor_user_id: str | None = None,
    details: dict[str, Any] | None = None,
    outcome: str = "allowed",
) -> None:
    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient_id,
            "actor_user_id": actor_user_id,
            "actor_name": actor_name,
            "actor_role": actor_role,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "outcome": outcome,
            "details_json": json.dumps(details or {}, separators=(",", ":")),
            "created_at": created_at,
        }
    )


def _evidence(
    store: Store,
    *,
    evidence_id: str,
    patient_id: str,
    source_type: str,
    title: str,
    document_name: str,
    page_ref: str,
    excerpt: str,
    verification_status: str,
    extracted_by_ai: bool,
    captured_at: str,
) -> None:
    store.create_evidence(
        {
            "id": evidence_id,
            "patient_id": patient_id,
            "source_type": source_type,
            "title": title,
            "document_name": document_name,
            "page_ref": page_ref,
            "excerpt": excerpt,
            "synthetic": 1,
            "verification_status": verification_status,
            "extracted_by_ai": 1 if extracted_by_ai else 0,
            "captured_at": captured_at,
            "created_at": captured_at,
        }
    )


def _snapshot(
    store: Store,
    *,
    patient: dict[str, Any],
    twin: dict[str, Any],
    version: int,
    reason: str,
    created_at: str,
) -> None:
    twin["version"] = version
    payload = twin_service.snapshot_payload(store, patient=patient, twin=twin)
    store.create_snapshot(
        {
            "id": new_id("snp"),
            "patient_id": patient["id"],
            "twin_id": twin["id"],
            "version": version,
            "reason": reason,
            "snapshot_json": json.dumps(payload, separators=(",", ":")),
            "created_at": created_at,
        }
    )


def _bump(
    store: Store,
    *,
    patient: dict[str, Any],
    twin: dict[str, Any],
    version: int,
    reason: str,
    at: str,
) -> tuple[int, str]:
    milestones = store.list_milestones(patient["id"])
    alerts = store.list_alerts(patient["id"])
    status, status_reason = twin_service.compute_status(alerts, milestones)
    store.update_twin(
        twin["id"],
        version=version,
        status=status,
        reason=status_reason,
        updated_at=at,
    )
    twin["version"] = version
    twin["status"] = status
    twin["updated_at"] = at
    _snapshot(
        store,
        patient=patient,
        twin=twin,
        version=version,
        reason=reason,
        created_at=at,
    )
    return version, status


def _seed_checkin(
    store: Store,
    *,
    patient: dict[str, Any],
    user: dict[str, Any],
    submitted_at: str,
    overall_feeling: str,
    pain_score: int,
    temperature_c: float | None,
    breathlessness_score: int,
    adherence: str,
    missed_doses: int,
    notes: str,
    symptoms: list[tuple[str, str, int]],
    evidence_id: str,
    event_id: str,
    checkin_id: str,
) -> list[dict[str, Any]]:
    prior = store.list_checkins(patient["id"], limit=1)
    prior_checkin = prior[0] if prior else None
    symptom_summary = ", ".join(f"{label} {severity}/10" for _, label, severity in symptoms)
    excerpt = (
        f"Overall feeling: {overall_feeling}. Pain {pain_score}/10. "
        f"Breathlessness {breathlessness_score}/10. "
        f"Temperature: {f'{temperature_c:.1f} C' if temperature_c is not None else 'not recorded'}. "
        f"Adherence: {adherence} ({missed_doses} missed). Symptoms: {symptom_summary or 'none'}."
    )
    _evidence(
        store,
        evidence_id=evidence_id,
        patient_id=patient["id"],
        source_type="patient_report",
        title=f"Patient check-in · {submitted_at[:10]}",
        document_name="Structured patient check-in form",
        page_ref="Patient submission",
        excerpt=excerpt,
        verification_status="patient_reported",
        extracted_by_ai=False,
        captured_at=submitted_at,
    )
    symptom_rows = [
        {
            "id": new_id("sym"),
            "checkin_id": checkin_id,
            "patient_id": patient["id"],
            "symptom_code": code,
            "label": label,
            "severity": severity,
            "notes": "",
            "created_at": submitted_at,
        }
        for code, label, severity in symptoms
    ]
    store.create_checkin(
        {
            "id": checkin_id,
            "patient_id": patient["id"],
            "submitted_by_user_id": user["id"],
            "submitted_at": submitted_at,
            "overall_feeling": overall_feeling,
            "pain_score": pain_score,
            "temperature_c": temperature_c,
            "breathlessness_score": breathlessness_score,
            "adherence": adherence,
            "missed_doses": missed_doses,
            "notes": notes,
            "verification_status": "patient_reported",
            "evidence_id": evidence_id,
            "created_at": submitted_at,
        },
        symptom_rows,
    )
    _event(
        store,
        event_id=event_id,
        patient_id=patient["id"],
        event_type="checkin_submitted",
        occurred_at=submitted_at,
        actor_name=user["name"],
        actor_role="patient",
        actor_user_id=user["id"],
        source_type="patient_report",
        evidence_id=evidence_id,
        verification_status="patient_reported",
        title="Patient check-in recorded",
        description=excerpt,
        payload={
            "checkinId": checkin_id,
            "painScore": pain_score,
            "temperatureC": temperature_c,
            "breathlessnessScore": breathlessness_score,
            "adherence": adherence,
            "missedDoses": missed_doses,
            "symptomCodes": [code for code, _, _ in symptoms],
        },
    )
    _audit(
        store,
        patient_id=patient["id"],
        action="checkin.created",
        entity_type="patient_checkin",
        entity_id=checkin_id,
        actor_name=user["name"],
        actor_role="patient",
        actor_user_id=user["id"],
        created_at=submitted_at,
        details={"evidenceId": evidence_id, "eventId": event_id},
    )
    return evaluate_checkin(
        store,
        patient=patient,
        checkin={
            "id": checkin_id,
            "pain_score": pain_score,
            "temperature_c": temperature_c,
            "missed_doses": missed_doses,
            "symptoms": [
                {"symptom_code": code, "severity": severity}
                for code, _, severity in symptoms
            ],
        },
        prior_checkin=prior_checkin,
        evidence_id=evidence_id,
    )


def _backfill_demo_clinical_records(store: Store) -> None:
    """Idempotently add synthetic demo lab/encounter records to an existing demo DB.
    Never deletes or overwrites existing records; inserts only missing seed rows."""
    patient = store.get_patient(PATIENT_ID)
    twin = store.get_twin(PATIENT_ID)
    if not patient or not twin:
        return
    # encounter
    if not any(e.get("id") == "enc_seed_1" for e in store.list_encounters(PATIENT_ID)):
        if store.get_evidence(PATIENT_ID, "src_encounter_1") is None:
            _evidence(
                store,
                evidence_id="src_encounter_1",
                patient_id=PATIENT_ID,
                source_type="discharge_document",
                title="Discharge encounter summary",
                excerpt="Synthetic discharge encounter record for post-infectious respiratory recovery follow-up.",
                document_name="discharge_summary_maya_rao.pdf",
                page_ref="Encounter summary",
                verification_status="document_extracted",
                extracted_by_ai=False,
                captured_at="2026-11-07T05:45:00+00:00",
            )
        try:
            store.insert_demo_row(
                "clinical_encounters",
                {
                    "id": "enc_seed_1",
                    "patient_id": PATIENT_ID,
                    "encounter_type": "Inpatient discharge",
                    "occurred_at": "2026-11-07T05:00:00+00:00",
                    "ended_at": "2026-11-07T05:30:00+00:00",
                    "facility": "St. Lakeside Hospital",
                    "provider_name": "Dr. Nandini Iyer",
                    "provider_specialty": "Pulmonology",
                    "clinician_user_id": CLINICIAN_USER_ID,
                    "reason": "Post-infectious respiratory recovery",
                    "summary": "Discharged after stabilization with home recovery plan, medication instructions, and follow-up schedule. Synthetic demonstration record.",
                    "discharge_instructions": "Continue prescribed medications, monitor symptoms, complete follow-up appointments, and seek urgent care for worsening breathing or chest pain.",
                    "follow_up_plan": "Primary care in 7 days and respiratory clinic in 14 days.",
                    "source_document": "discharge_summary_maya_rao.pdf",
                    "evidence_id": "src_encounter_1",
                    "verification_status": "document_extracted",
                    "review_status": "pending",
                    "created_by_user_id": CLINICIAN_USER_ID,
                    "created_at": "2026-11-07T05:45:00+00:00",
                    "updated_at": "2026-11-07T05:45:00+00:00",
                },
            )
        except Exception:
            pass
        try:
            store.create_event(
                {
                    "id": "evt_encounter_1",
                    "patient_id": PATIENT_ID,
                    "twin_id": TWIN_ID,
                    "event_type": "clinical_encounter_recorded",
                    "occurred_at": "2026-11-07T05:00:00+00:00",
                    "recorded_at": "2026-11-07T05:45:00+00:00",
                    "actor_user_id": CLINICIAN_USER_ID,
                    "actor_name": "Dr. Nandini Iyer",
                    "actor_role": "clinician",
                    "source_type": "discharge_document",
                    "evidence_id": "src_encounter_1",
                    "verification_status": "document_extracted",
                    "title": "Clinical encounter · Inpatient discharge",
                    "description": "Discharged after stabilization with documented recovery plan and follow-up. Synthetic demonstration record.",
                    "payload_json": '{"encounterId":"enc_seed_1","facility":"St. Lakeside Hospital"}',
                    "review_status": "not_required",
                    "created_at": "2026-11-07T05:45:00+00:00",
                }
            )
        except Exception:
            pass

    seed_labs = [
        {
            "id": "lab_seed_crp",
            "evidence_id": "src_lab_crp",
            "event_id": "evt_lab_seed_crp",
            "link_id": "elnk_lab_seed_crp",
            "code": "CRP",
            "name": "C-reactive protein",
            "panel": "Inflammation",
            "specimen": "Blood",
            "collected_at": "2026-11-08T03:00:00+00:00",
            "resulted_at": "2026-11-08T04:00:00+00:00",
            "value_numeric": 12.0,
            "value_text": "",
            "unit": "mg/L",
            "source_range_low": 0.0,
            "source_range_high": 5.0,
            "source_range_text": "0-5 mg/L (source document)",
            "comparison_status": "above_range",
            "comparison_note": "Above source-provided reference range as documented; clinician review advised.",
            "verification_status": "document_extracted",
            "excerpt": "CRP 12.0 mg/L. Source reference range 0-5 mg/L provided in synthetic lab report.",
        },
        {
            "id": "lab_seed_wbc",
            "evidence_id": "src_lab_wbc",
            "event_id": "evt_lab_seed_wbc",
            "link_id": "elnk_lab_seed_wbc",
            "code": "WBC",
            "name": "White blood cell count",
            "panel": "CBC",
            "specimen": "Blood",
            "collected_at": "2026-11-08T03:00:00+00:00",
            "resulted_at": "2026-11-08T04:00:00+00:00",
            "value_numeric": 9.8,
            "value_text": "",
            "unit": "10^3/uL",
            "source_range_low": 4.0,
            "source_range_high": 11.0,
            "source_range_text": "4.0-11.0 10^3/uL (source document)",
            "comparison_status": "in_range",
            "comparison_note": "Within source-provided reference range.",
            "verification_status": "clinician_verified",
            "excerpt": "WBC 9.8 10^3/uL. Source reference range 4.0-11.0 10^3/uL provided in synthetic lab report.",
        },
    ]
    existing_labs = {r.get("id") for r in store.list_lab_results(PATIENT_ID)}
    for lab in seed_labs:
        if lab["id"] in existing_labs:
            continue
        if store.get_evidence(PATIENT_ID, lab["evidence_id"]) is None:
            _evidence(
                store,
                evidence_id=lab["evidence_id"],
                patient_id=PATIENT_ID,
                source_type="clinician_note",
                title=f"Lab result · {lab['name']}",
                excerpt=lab["excerpt"],
                document_name="synthetic_lab_report.pdf",
                page_ref="Lab panel",
                verification_status=lab["verification_status"],
                extracted_by_ai=False,
                captured_at=lab["resulted_at"],
            )
        try:
            store.insert_demo_row(
                "lab_results",
                {
                    "id": lab["id"],
                    "patient_id": PATIENT_ID,
                    "encounter_id": "enc_seed_1",
                    "panel": lab["panel"],
                    "test_code": lab["code"],
                    "test_name": lab["name"],
                    "specimen": lab["specimen"],
                    "collected_at": lab["collected_at"],
                    "resulted_at": lab["resulted_at"],
                    "value_numeric": lab["value_numeric"],
                    "value_text": lab["value_text"],
                    "unit": lab["unit"],
                    "source_range_low": lab["source_range_low"],
                    "source_range_high": lab["source_range_high"],
                    "source_range_text": lab["source_range_text"],
                    "clinician_range_low": None,
                    "clinician_range_high": None,
                    "clinician_range_text": "",
                    "range_source": "provided",
                    "comparison_status": lab["comparison_status"],
                    "comparison_note": lab["comparison_note"],
                    "ambiguity_note": "",
                    "verification_status": lab["verification_status"],
                    "evidence_id": lab["evidence_id"],
                    "synthetic": 1,
                    "created_by_user_id": CLINICIAN_USER_ID,
                    "verified_by_user_id": CLINICIAN_USER_ID if lab["verification_status"] == "clinician_verified" else None,
                    "verified_by_name": "Dr. Nandini Iyer" if lab["verification_status"] == "clinician_verified" else None,
                    "verified_at": lab["resulted_at"] if lab["verification_status"] == "clinician_verified" else None,
                    "created_at": lab["resulted_at"],
                    "updated_at": lab["resulted_at"],
                },
            )
        except Exception:
            pass
        try:
            store.insert_demo_row(
                "encounter_links",
                {
                    "id": lab["link_id"],
                    "patient_id": PATIENT_ID,
                    "encounter_id": "enc_seed_1",
                    "target_type": "lab_result",
                    "target_id": lab["id"],
                    "created_at": lab["resulted_at"],
                },
            )
        except Exception:
            pass
        try:
            store.create_event(
                {
                    "id": lab["event_id"],
                    "patient_id": PATIENT_ID,
                    "twin_id": TWIN_ID,
                    "event_type": "lab_result_recorded",
                    "occurred_at": lab["collected_at"],
                    "recorded_at": lab["resulted_at"],
                    "actor_user_id": CLINICIAN_USER_ID,
                    "actor_name": "Dr. Nandini Iyer",
                    "actor_role": "clinician",
                    "source_type": "clinician_note",
                    "evidence_id": lab["evidence_id"],
                    "verification_status": lab["verification_status"],
                    "title": f"Lab result recorded · {lab['name']}",
                    "description": f"{lab['name']}: {lab['value_numeric']} {lab['unit']}. Reference range and unit stored exactly as supplied; none inferred.",
                    "payload_json": json.dumps({"labResultId": lab["id"], "testCode": lab["code"], "comparisonStatus": lab["comparison_status"]}, separators=(",", ":")),
                    "review_status": "not_required",
                    "created_at": lab["resulted_at"],
                }
            )
        except Exception:
            pass


def seed_demo_data(store: Store, *, include_clinical_records: bool = True) -> None:
    if store.get_patient(PATIENT_ID):
        if include_clinical_records:
            _backfill_demo_clinical_records(store)
        return

    now = utc_now()
    today = now.date()

    def at(days: float = 0, hours: float = 0) -> str:
        return iso(now + timedelta(days=days, hours=hours))

    discharged_on = (today - timedelta(days=3)).isoformat()
    created_at = at(days=-3, hours=-1)

    # ---------------------------------------------------------------- users
    users = [
        {
            "id": PATIENT_USER_ID,
            "name": "Maya Rao",
            "role": "patient",
            "title": "Patient",
            "organization": "CareTwin synthetic demo",
            "initials": "MR",
            "created_at": created_at,
        },
        {
            "id": CAREGIVER_USER_ID,
            "name": "Arjun Rao",
            "role": "caregiver",
            "title": "Son · Primary caregiver",
            "organization": "CareTwin synthetic demo",
            "initials": "AR",
            "created_at": created_at,
        },
        {
            "id": CLINICIAN_USER_ID,
            "name": "Dr. Nandini Iyer",
            "role": "clinician",
            "title": "Consultant Pulmonologist",
            "organization": "St. Lakeside Hospital",
            "initials": "NI",
            "created_at": created_at,
        },
        {
            "id": SECOND_CAREGIVER_USER_ID,
            "name": "Priya Rao",
            "role": "caregiver",
            "title": "Daughter · Sharing revoked",
            "organization": "CareTwin synthetic demo",
            "initials": "PR",
            "created_at": created_at,
        },
    ]
    for user in users:
        store.insert_demo_row("users", user)

    store.insert_demo_row(
        "patients",
        {
            "id": PATIENT_ID,
            "mrn": "SYN-2041",
            "full_name": "Maya Rao",
            "preferred_name": "Maya",
            "date_of_birth": "1968-03-14",
            "sex": "Female",
            "primary_language": "English (Kannada)",
            "condition": "Community-acquired pneumonia",
            "discharged_on": discharged_on,
            "synthetic": 1,
            "created_at": created_at,
        },
    )
    patient = store.get_patient(PATIENT_ID)
    assert patient is not None

    caregiver_scopes = [
        "twin:read",
        "timeline:read",
        "schedule:read",
        "observations:write",
        "alerts:read",
        "consents:read",
    ]
    store.insert_demo_row(
        "care_relationships",
        {
            "id": "rel_maya_self",
            "patient_id": PATIENT_ID,
            "user_id": PATIENT_USER_ID,
            "relationship": "self",
            "scopes_json": json.dumps(["*"]),
            "status": "active",
            "created_at": created_at,
        },
    )
    store.insert_demo_row(
        "care_relationships",
        {
            "id": "rel_maya_arjun",
            "patient_id": PATIENT_ID,
            "user_id": CAREGIVER_USER_ID,
            "relationship": "son",
            "scopes_json": json.dumps(caregiver_scopes),
            "status": "active",
            "created_at": created_at,
        },
    )
    store.insert_demo_row(
        "care_relationships",
        {
            "id": "rel_maya_priya",
            "patient_id": PATIENT_ID,
            "user_id": SECOND_CAREGIVER_USER_ID,
            "relationship": "daughter",
            "scopes_json": json.dumps(caregiver_scopes),
            "status": "active",
            "created_at": created_at,
        },
    )
    store.insert_demo_row(
        "care_relationships",
        {
            "id": "rel_maya_nandini",
            "patient_id": PATIENT_ID,
            "user_id": CLINICIAN_USER_ID,
            "relationship": "care_team",
            "scopes_json": json.dumps(["*"]),
            "status": "active",
            "created_at": created_at,
        },
    )
    store.insert_demo_row(
        "consent_records",
        {
            "id": "con_maya_arjun",
            "patient_id": PATIENT_ID,
            "grantee_user_id": CAREGIVER_USER_ID,
            "grantee_relationship": "son",
            "scopes_json": json.dumps(caregiver_scopes),
            "status": "granted",
            "granted_at": at(days=-2.5),
            "updated_at": at(days=-2.5),
        },
    )
    store.insert_demo_row(
        "consent_records",
        {
            "id": "con_maya_priya",
            "patient_id": PATIENT_ID,
            "grantee_user_id": SECOND_CAREGIVER_USER_ID,
            "grantee_relationship": "daughter",
            "scopes_json": json.dumps(caregiver_scopes),
            "status": "revoked",
            "granted_at": at(days=-3),
            "updated_at": at(days=-1.5),
        },
    )

    # -------------------------------------------------------- twin and plan
    store.insert_demo_row(
        "recovery_twins",
        {
            "id": TWIN_ID,
            "patient_id": PATIENT_ID,
            "version": 1,
            "status": "on_track",
            "status_reason": "Structured recovery plan recorded.",
            "created_at": created_at,
            "updated_at": at(days=-3, hours=1.5),
        },
    )
    twin = store.get_twin(PATIENT_ID)
    assert twin is not None

    # ------------------------------------------------------------ evidence
    _evidence(
        store,
        evidence_id="src_discharge_p1",
        patient_id=PATIENT_ID,
        source_type="discharge_document",
        title="Discharge summary · diagnosis & recovery plan",
        document_name="discharge_summary_maya_rao.pdf",
        page_ref="Page 1",
        excerpt=(
            "Admitted with community-acquired pneumonia. Discharged after clinical "
            "improvement. Plan: complete antibiotics, graded activity, review of red-flag "
            "symptoms, primary care follow-up in 5 days."
        ),
        verification_status="document_extracted",
        extracted_by_ai=True,
        captured_at=at(days=-3, hours=0.5),
    )
    _evidence(
        store,
        evidence_id="src_discharge_p2",
        patient_id=PATIENT_ID,
        source_type="discharge_document",
        title="Discharge summary · medication instructions",
        document_name="discharge_summary_maya_rao.pdf",
        page_ref="Page 2",
        excerpt=(
            "Amoxicillin-clavulanate 625 mg oral three times daily for 7 days, take with "
            "food. Paracetamol 500 mg oral up to four times daily as needed, maximum 4 g/day."
        ),
        verification_status="clinician_verified",
        extracted_by_ai=True,
        captured_at=at(days=-3, hours=0.5),
    )
    _evidence(
        store,
        evidence_id="src_discharge_p3",
        patient_id=PATIENT_ID,
        source_type="discharge_document",
        title="Discharge summary · inhaler and return precautions",
        document_name="discharge_summary_maya_rao.pdf",
        page_ref="Page 3",
        excerpt=(
            "Salbutamol 100 mcg inhaler, 2 puffs as needed for breathlessness. Spacer use "
            "was noted but delivery technique was not specified. Seek urgent review for "
            "worsening breathlessness, chest pain, or persistent fever."
        ),
        verification_status="awaiting_review",
        extracted_by_ai=True,
        captured_at=at(days=-3, hours=0.5),
    )
    _evidence(
        store,
        evidence_id="src_discharge_p4",
        patient_id=PATIENT_ID,
        source_type="discharge_document",
        title="Discharge summary · follow-up plan",
        document_name="discharge_summary_maya_rao.pdf",
        page_ref="Page 4",
        excerpt=(
            "Primary care review in 5 days. Respiratory clinic review in 2 weeks with "
            "repeat assessment of breathlessness and inhaler technique."
        ),
        verification_status="clinician_verified",
        extracted_by_ai=True,
        captured_at=at(days=-3, hours=0.5),
    )

    store.insert_demo_row(
        "recovery_plans",
        {
            "id": "plan_maya_pneumonia",
            "twin_id": TWIN_ID,
            "patient_id": PATIENT_ID,
            "title": "Post-pneumonia recovery plan",
            "summary": (
                "Complete the prescribed antibiotic course, maintain hydration and graded "
                "activity, monitor for return precautions, and attend primary care and "
                "respiratory follow-up."
            ),
            "start_date": discharged_on,
            "target_end_date": (today + timedelta(days=11)).isoformat(),
            "status": "active",
            "created_by_user_id": CLINICIAN_USER_ID,
            "evidence_id": "src_discharge_p1",
            "created_at": at(days=-3, hours=1.5),
        },
    )

    milestones = [
        (
            "msl_48h",
            "Complete first 48 hours of antibiotics",
            "Take every scheduled dose for the first 48 hours after discharge.",
            (today - timedelta(days=1)).isoformat(),
            "completed",
            at(days=-1, hours=-2),
        ),
        (
            "msl_antibiotics",
            "Complete the 7-day antibiotic course",
            "Finish all prescribed doses unless a clinician advises otherwise.",
            (today + timedelta(days=4)).isoformat(),
            "in_progress",
            None,
        ),
        (
            "msl_walking",
            "Return to 10-minute daily walking",
            "Build activity gradually and stop for breathlessness or chest pain.",
            (today + timedelta(days=7)).isoformat(),
            "in_progress",
            None,
        ),
        (
            "msl_gp",
            "Attend primary care follow-up",
            "Review recovery, medication tolerance and return precautions.",
            (today + timedelta(days=2)).isoformat(),
            "pending",
            None,
        ),
        (
            "msl_resp",
            "Attend respiratory clinic review",
            "Repeat symptom assessment and inhaler technique review.",
            (today + timedelta(days=11)).isoformat(),
            "pending",
            None,
        ),
    ]
    for milestone_id, title, description, due_date, status, completed_at in milestones:
        store.insert_demo_row(
            "milestones",
            {
                "id": milestone_id,
                "patient_id": PATIENT_ID,
                "title": title,
                "description": description,
                "due_date": due_date,
                "status": status,
                "completed_at": completed_at,
                "verification_status": "clinician_verified",
                "evidence_id": "src_discharge_p1",
                "created_at": at(days=-3, hours=1.4),
                "updated_at": completed_at or at(days=-3, hours=1.4),
            },
        )

    medications = [
        (
            "med_amox",
            "Amoxicillin-clavulanate",
            "625 mg",
            "Oral",
            "Three times daily",
            "7 days",
            "Take with food. Complete the full course.",
            "clinician_verified",
            "src_discharge_p2",
        ),
        (
            "med_paracetamol",
            "Paracetamol",
            "500 mg",
            "Oral",
            "Up to four times daily as needed",
            "As needed",
            "Maximum 4 g in 24 hours. Record doses taken.",
            "clinician_verified",
            "src_discharge_p2",
        ),
        (
            "med_salbutamol",
            "Salbutamol inhaler",
            "100 mcg per puff",
            "Inhaled",
            "2 puffs as needed",
            "As needed",
            "Use for breathlessness. Spacer technique is ambiguous in the source and requires clinician review.",
            "awaiting_review",
            "src_discharge_p3",
        ),
    ]
    for med_id, name, dosage, route, frequency, duration, instructions, verification, evidence_id in medications:
        store.insert_demo_row(
            "medication_instructions",
            {
                "id": med_id,
                "patient_id": PATIENT_ID,
                "name": name,
                "dosage": dosage,
                "route": route,
                "frequency": frequency,
                "duration": duration,
                "instructions": instructions,
                "status": "active",
                "verification_status": verification,
                "prescribed_by": "Dr. Nandini Iyer",
                "evidence_id": evidence_id,
                "created_at": at(days=-3, hours=1.3),
                "updated_at": at(days=-3, hours=1.3),
            },
        )

    followups = [
        (
            "fu_gp",
            "Primary care recovery review",
            "Dr. Kavya Menon",
            "Family Medicine",
            datetime.combine(today + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc)
            + timedelta(hours=10, minutes=30),
            "Lakeside Family Clinic · Room 4",
            "Review recovery, antibiotic tolerance and return precautions.",
            "clinician_verified",
            "src_discharge_p4",
        ),
        (
            "fu_resp",
            "Respiratory clinic review",
            "Dr. Nandini Iyer",
            "Pulmonology",
            datetime.combine(today + timedelta(days=11), datetime.min.time(), tzinfo=timezone.utc)
            + timedelta(hours=14),
            "St. Lakeside Hospital · Respiratory OPD",
            "Repeat symptom assessment and review inhaler technique.",
            "clinician_verified",
            "src_discharge_p4",
        ),
    ]
    for fu_id, title, clinician_name, specialty, scheduled, location, notes, verification, evidence_id in followups:
        store.insert_demo_row(
            "follow_ups",
            {
                "id": fu_id,
                "patient_id": PATIENT_ID,
                "title": title,
                "clinician_name": clinician_name,
                "specialty": specialty,
                "scheduled_for": iso(scheduled),
                "location": location,
                "status": "scheduled",
                "notes": notes,
                "verification_status": verification,
                "evidence_id": evidence_id,
                "created_at": at(days=-3, hours=1.2),
            },
        )

    rules = [
        ("rule_chest", "chest_pain_severity", "Chest pain severity", "Flag reported chest pain at or above threshold.", "symptom_severity", "checkin", "symptom_severity", "chest_pain", "greater_than_or_equal", 7, "critical"),
        ("rule_breath", "breathlessness_severity", "Breathlessness severity", "Flag reported breathlessness at or above threshold.", "symptom_severity", "checkin", "symptom_severity", "breathlessness", "greater_than_or_equal", 7, "urgent"),
        ("rule_fever", "fever_threshold", "Fever threshold", "Flag recorded temperature at or above threshold.", "temperature", "checkin", "temperature", "temperature_c", "greater_than_or_equal", 38.5, "urgent"),
        ("rule_adherence", "adherence_gap", "Medication adherence gap", "Flag missed doses at or above threshold.", "missed_doses", "checkin", "missed_doses", "missed_doses", "greater_than_or_equal", 2, "moderate"),
        ("rule_pain", "pain_escalation", "Pain escalation", "Flag a pain-score increase at or above threshold.", "pain_delta", "checkin", "pain_delta", "pain_score", "greater_than_or_equal", 3, "moderate"),
        ("rule_gap", "checkin_gap", "Check-in gap", "Flag when the latest check-in is older than the configured number of hours.", "checkin_gap_hours", "checkin", "checkin_gap_hours", "submitted_at", "greater_than_or_equal", 24, "moderate"),
    ]
    for (
        rule_id,
        code,
        name,
        description,
        kind,
        source_type,
        input_type,
        input_key,
        operator,
        threshold,
        severity,
    ) in rules:
        store.insert_demo_row(
            "monitoring_rules",
            {
                "id": rule_id,
                "patient_id": PATIENT_ID,
                "code": code,
                "name": name,
                "description": description,
                "kind": kind,
                "source_type": source_type,
                "input_type": input_type,
                "input_key": input_key,
                "operator": operator,
                "threshold": threshold,
                "comparison_value": None,
                "window_hours": None,
                "cooldown_hours": 0,
                "requires_human_review": 1,
                "version": 1,
                "severity": severity,
                "enabled": 1,
                "configured_by_user_id": CLINICIAN_USER_ID,
                "created_at": at(days=-3, hours=1.1),
                "updated_at": at(days=-3, hours=1.1),
            },
        )
        # keep a version snapshot for clinician-configured rule provenance
        try:
            store._insert(
                "monitoring_rule_versions",
                {
                    "id": new_id("rvr"),
                    "rule_id": rule_id,
                    "patient_id": PATIENT_ID,
                    "version": 1,
                    "snapshot_json": json.dumps(
                        {
                            "id": rule_id,
                            "code": code,
                            "name": name,
                            "kind": kind,
                            "sourceType": source_type,
                            "inputType": input_type,
                            "inputKey": input_key,
                            "operator": operator,
                            "threshold": threshold,
                            "severity": severity,
                            "enabled": True,
                        },
                        separators=(",", ":"),
                    ),
                    "changed_by_user_id": CLINICIAN_USER_ID,
                    "change_reason": "Seeded clinician-configured deterministic rule",
                    "created_at": at(days=-3, hours=1.1),
                },
            )
        except Exception:
            pass

    # -------------------------------------------------- initial event trail
    _event(
        store,
        event_id="evt_discharge_doc",
        patient_id=PATIENT_ID,
        event_type="discharge_recorded",
        occurred_at=at(days=-3, hours=0.4),
        actor_name="Lakeside Hospital discharge system",
        actor_role="system",
        source_type="discharge_document",
        evidence_id="src_discharge_p1",
        verification_status="document_extracted",
        title="Discharge summary received",
        description="A synthetic 4-page discharge summary was received for document processing.",
        payload={"pages": 4, "document": "discharge_summary_maya_rao.pdf"},
    )
    _event(
        store,
        event_id="evt_doc_processed",
        patient_id=PATIENT_ID,
        event_type="document_processed",
        occurred_at=at(days=-3, hours=0.3),
        actor_name="Document Intelligence Agent",
        actor_role="system",
        source_type="discharge_document",
        evidence_id="src_discharge_p3",
        verification_status="awaiting_review",
        title="Document extraction completed",
        description=(
            "Extracted 3 medication instructions, 2 follow-ups and 5 milestones. "
            "Inhaler spacer technique flagged ambiguous and left awaiting review."
        ),
        payload={
            "medications": 3,
            "followUps": 2,
            "milestones": 5,
            "ambiguities": ["Inhaler spacer technique"],
            "requiresHumanReview": True,
        },
        review_status="pending",
    )
    _event(
        store,
        event_id="evt_instruction_verified",
        patient_id=PATIENT_ID,
        event_type="instruction_verified",
        occurred_at=at(days=-3, hours=0.1),
        actor_name="Dr. Nandini Iyer",
        actor_role="clinician",
        actor_user_id=CLINICIAN_USER_ID,
        source_type="discharge_document",
        evidence_id="src_discharge_p2",
        verification_status="clinician_verified",
        title="Medication instructions verified against source",
        description=(
            "Two medication instructions were reviewed against page 2. The inhaler "
            "instruction remains awaiting review due to missing spacer technique."
        ),
        payload={"verified": ["med_amox", "med_paracetamol"], "awaiting": ["med_salbutamol"]},
        review_status="reviewed",
    )
    _event(
        store,
        event_id="evt_plan_created",
        patient_id=PATIENT_ID,
        event_type="plan_created",
        occurred_at=at(days=-3, hours=0.0),
        actor_name="Dr. Nandini Iyer",
        actor_role="clinician",
        actor_user_id=CLINICIAN_USER_ID,
        source_type="clinician_note",
        evidence_id="src_discharge_p1",
        verification_status="clinician_verified",
        title="Recovery plan structured",
        description="Five milestones and two follow-up reviews were organized from documented instructions.",
        payload={"milestones": 5, "followUps": 2, "planId": "plan_maya_pneumonia"},
    )
    _event(
        store,
        event_id="evt_followup",
        patient_id=PATIENT_ID,
        event_type="follow_up_scheduled",
        occurred_at=at(days=-3, hours=0.0),
        actor_name="Care coordination",
        actor_role="system",
        source_type="discharge_document",
        evidence_id="src_discharge_p4",
        verification_status="clinician_verified",
        title="Follow-up appointments added",
        description="Primary care and respiratory clinic reviews were added from the discharge plan.",
        payload={"followUps": ["fu_gp", "fu_resp"]},
    )
    _event(
        store,
        event_id="evt_consent_granted",
        patient_id=PATIENT_ID,
        event_type="consent_updated",
        occurred_at=at(days=-2.5),
        actor_name="Maya Rao",
        actor_role="patient",
        actor_user_id=PATIENT_USER_ID,
        source_type="system_demo",
        evidence_id=None,
        verification_status="patient_reported",
        title="Caregiver sharing granted",
        description="Maya granted Arjun Rao access to the recovery twin, schedule, alerts and observation workflow.",
        payload={"consentId": "con_maya_arjun", "status": "granted"},
    )
    _audit(
        store,
        patient_id=PATIENT_ID,
        action="discharge.extracted",
        entity_type="evidence_source",
        entity_id="src_discharge_p3",
        actor_name="Document Intelligence Agent",
        actor_role="system",
        created_at=at(days=-3, hours=0.3),
        details={"requiresHumanReview": True, "ambiguities": 1},
    )
    _audit(
        store,
        patient_id=PATIENT_ID,
        action="medication.verified",
        entity_type="medication_instruction",
        entity_id="med_amox",
        actor_name="Dr. Nandini Iyer",
        actor_role="clinician",
        actor_user_id=CLINICIAN_USER_ID,
        created_at=at(days=-3, hours=0.1),
        details={"evidenceId": "src_discharge_p2"},
    )
    _audit(
        store,
        patient_id=PATIENT_ID,
        action="consent.updated",
        entity_type="consent_record",
        entity_id="con_maya_arjun",
        actor_name="Maya Rao",
        actor_role="patient",
        actor_user_id=PATIENT_USER_ID,
        created_at=at(days=-2.5),
        details={"status": "granted", "granteeUserId": CAREGIVER_USER_ID},
    )

    # Snapshot after plan creation.
    _snapshot(
        store,
        patient=patient,
        twin=twin,
        version=1,
        reason="Recovery plan structured",
        created_at=at(days=-3, hours=0.0),
    )

    # ------------------------------------------------------- first check-in
    _seed_checkin(
        store,
        patient=patient,
        user=users[0],
        submitted_at=at(days=-2),
        overall_feeling="same",
        pain_score=4,
        temperature_c=37.4,
        breathlessness_score=3,
        adherence="all",
        missed_doses=0,
        notes="Cough is still present but I managed breakfast and a short walk.",
        symptoms=[("cough", "Cough", 4), ("fatigue", "Fatigue", 5)],
        evidence_id="src_checkin_1",
        event_id="evt_checkin_1",
        checkin_id="chk_seed_1",
    )
    _bump(
        store,
        patient=patient,
        twin=twin,
        version=2,
        reason="Patient check-in recorded",
        at=at(days=-2),
    )

    # ---------------------------------------------------------- observation
    _evidence(
        store,
        evidence_id="src_observation_1",
        patient_id=PATIENT_ID,
        source_type="caregiver_report",
        title="Caregiver observation · energy and appetite",
        document_name="Caregiver observation form",
        page_ref="Caregiver submission",
        excerpt=(
            "Maya needed help preparing the evening meal and seemed more tired than "
            "yesterday. She ate most of lunch and drank water regularly."
        ),
        verification_status="caregiver_reported",
        extracted_by_ai=False,
        captured_at=at(days=-1.5),
    )
    store.create_observation(
        {
            "id": "obs_seed_1",
            "patient_id": PATIENT_ID,
            "caregiver_user_id": CAREGIVER_USER_ID,
            "observed_at": at(days=-1.5),
            "category": "appetite",
            "note": (
                "Maya needed help preparing the evening meal and seemed more tired than "
                "yesterday. She ate most of lunch and drank water regularly."
            ),
            "verification_status": "caregiver_reported",
            "evidence_id": "src_observation_1",
            "created_at": at(days=-1.5),
        }
    )
    _event(
        store,
        event_id="evt_observation_1",
        patient_id=PATIENT_ID,
        event_type="observation_recorded",
        occurred_at=at(days=-1.5),
        actor_name="Arjun Rao",
        actor_role="caregiver",
        actor_user_id=CAREGIVER_USER_ID,
        source_type="caregiver_report",
        evidence_id="src_observation_1",
        verification_status="caregiver_reported",
        title="Caregiver observation · appetite",
        description=(
            "Maya needed help preparing the evening meal and seemed more tired than yesterday."
        ),
        payload={"observationId": "obs_seed_1", "category": "appetite"},
    )
    _audit(
        store,
        patient_id=PATIENT_ID,
        action="caregiver_observation.created",
        entity_type="caregiver_observation",
        entity_id="obs_seed_1",
        actor_name="Arjun Rao",
        actor_role="caregiver",
        actor_user_id=CAREGIVER_USER_ID,
        created_at=at(days=-1.5),
        details={"evidenceId": "src_observation_1"},
    )
    _bump(
        store,
        patient=patient,
        twin=twin,
        version=3,
        reason="Caregiver observation recorded",
        at=at(days=-1.5),
    )

    # -------------------------------------------------- milestone completed
    store.update_milestone("msl_48h", "completed", at(days=-1.2), at(days=-1.2))
    _event(
        store,
        event_id="evt_milestone_48h",
        patient_id=PATIENT_ID,
        event_type="milestone_completed",
        occurred_at=at(days=-1.2),
        actor_name="Dr. Nandini Iyer",
        actor_role="clinician",
        actor_user_id=CLINICIAN_USER_ID,
        source_type="clinician_note",
        evidence_id="src_discharge_p1",
        verification_status="clinician_verified",
        title="Milestone completed · first 48 hours of antibiotics",
        description="The first 48-hour antibiotic milestone was marked complete after review.",
        payload={"milestoneId": "msl_48h", "status": "completed"},
        review_status="reviewed",
    )
    _audit(
        store,
        patient_id=PATIENT_ID,
        action="milestone.updated",
        entity_type="recovery_milestone",
        entity_id="msl_48h",
        actor_name="Dr. Nandini Iyer",
        actor_role="clinician",
        actor_user_id=CLINICIAN_USER_ID,
        created_at=at(days=-1.2),
        details={"status": "completed"},
    )
    _bump(
        store,
        patient=patient,
        twin=twin,
        version=4,
        reason="Milestone updated",
        at=at(days=-1.2),
    )

    # ------------------------------------------------------ second check-in
    alerts = _seed_checkin(
        store,
        patient=patient,
        user=users[0],
        submitted_at=at(hours=-26),
        overall_feeling="worse",
        pain_score=6,
        temperature_c=38.6,
        breathlessness_score=5,
        adherence="missed_multiple",
        missed_doses=2,
        notes=(
            "Felt feverish overnight and missed two antibiotic doses. Cough is worse and "
            "I am more breathless walking to the kitchen."
        ),
        symptoms=[
            ("cough", "Cough", 5),
            ("fever", "Fever", 6),
            ("fatigue", "Fatigue", 7),
            ("chest_pain", "Chest pain", 2),
        ],
        evidence_id="src_checkin_2",
        event_id="evt_checkin_2",
        checkin_id="chk_seed_2",
    )
    _bump(
        store,
        patient=patient,
        twin=twin,
        version=5,
        reason="Patient check-in recorded with rule alerts",
        at=at(hours=-26),
    )

    store.create_safety_decision(
        {
            "id": "sfd_seed_checkin",
            "patient_id": PATIENT_ID,
            "operation": "patient_checkin.create",
            "outcome": "allowed_with_alerts",
            "checks_json": json.dumps(
                [
                    {"code": "patient_self_write", "label": "Patient is the authenticated author", "passed": True, "detail": "Patient self-write verified."},
                    {"code": "synthetic_data_label", "label": "Patient is labeled synthetic", "passed": True, "detail": "Synthetic demo safety guardrail."},
                    {"code": "attributed_provenance", "label": "Author and timestamp are attributable", "passed": True, "detail": "Maya Rao · patient_report."},
                    {"code": "bounded_inputs", "label": "Clinical scales are within configured bounds", "passed": True, "detail": "All scales 0-10."},
                    {"code": "deterministic_monitoring", "label": "Clinician-configured rules were evaluated", "passed": True, "detail": f"{len(alerts)} rule-based alert(s) created from this check-in."},
                ],
                separators=(",", ":"),
            ),
            "actor_name": "Maya Rao",
            "actor_role": "patient",
            "created_at": at(hours=-26),
        }
    )
    store.create_safety_decision(
        {
            "id": "sfd_seed_medverify",
            "patient_id": PATIENT_ID,
            "operation": "medication.verify",
            "outcome": "allowed",
            "checks_json": json.dumps(
                [
                    {"code": "clinician_role", "label": "Reviewer is a clinician", "passed": True, "detail": "Dr. Nandini Iyer."},
                    {"code": "evidence_link", "label": "Medication has document evidence", "passed": True, "detail": "src_discharge_p2."},
                    {"code": "reviewable_state", "label": "Instruction is in a reviewable state", "passed": True, "detail": "Instruction was document extracted."},
                ],
                separators=(",", ":"),
            ),
            "actor_name": "Dr. Nandini Iyer",
            "actor_role": "clinician",
            "created_at": at(days=-3, hours=0.1),
        }
    )
    store.create_safety_decision(
        {
            "id": "sfd_seed_consent",
            "patient_id": PATIENT_ID,
            "operation": "consent.update",
            "outcome": "allowed",
            "checks_json": json.dumps(
                [
                    {"code": "patient_self_control", "label": "Patient controls their own consent", "passed": True, "detail": "Maya Rao."},
                    {"code": "consent_ownership", "label": "Consent record belongs to the patient", "passed": True, "detail": "con_maya_arjun."},
                    {"code": "auditable_change", "label": "Change is attributable for audit", "passed": True, "detail": "Actor captured for audit."},
                ],
                separators=(",", ":"),
            ),
            "actor_name": "Maya Rao",
            "actor_role": "patient",
            "created_at": at(days=-2.5),
        }
    )


    if include_clinical_records:
        # ------------------------------------------------ clinical encounters (synthetic)
        enc_evidence_id = "src_encounter_1"
        _evidence(
            store,
            evidence_id=enc_evidence_id,
            patient_id=PATIENT_ID,
            source_type="discharge_document",
            title="Discharge encounter summary",
            excerpt="Synthetic discharge encounter record for post-infectious respiratory recovery follow-up.",
            document_name="discharge_summary_maya_rao.pdf",
            page_ref="Encounter summary",
            verification_status="document_extracted",
            extracted_by_ai=False,
            captured_at=at(days=-3, hours=0.45),
        )
        store.insert_demo_row(
            "clinical_encounters",
            {
                "id": "enc_seed_1",
                "patient_id": PATIENT_ID,
                "encounter_type": "Inpatient discharge",
                "occurred_at": at(days=-3, hours=1),
                "ended_at": at(days=-3, hours=0.5),
                "facility": "St. Lakeside Hospital",
                "provider_name": "Dr. Nandini Iyer",
                "provider_specialty": "Pulmonology",
                "clinician_user_id": CLINICIAN_USER_ID,
                "reason": "Post-infectious respiratory recovery",
                "summary": "Discharged after stabilization with home recovery plan, medication instructions, and follow-up schedule. Synthetic demonstration record.",
                "discharge_instructions": "Continue prescribed medications, monitor symptoms, complete follow-up appointments, and seek urgent care for worsening breathing or chest pain.",
                "follow_up_plan": "Primary care in 7 days and respiratory clinic in 14 days.",
                "source_document": "discharge_summary_maya_rao.pdf",
                "evidence_id": enc_evidence_id,
                "verification_status": "document_extracted",
                "review_status": "pending",
                "created_by_user_id": CLINICIAN_USER_ID,
                "created_at": at(days=-3, hours=0.45),
                "updated_at": at(days=-3, hours=0.45),
            },
        )
        _event(
            store,
            event_id="evt_encounter_1",
            patient_id=PATIENT_ID,
            event_type="clinical_encounter_recorded",
            occurred_at=at(days=-3, hours=1),
            actor_name="Dr. Nandini Iyer",
            actor_role="clinician",
            source_type="discharge_document",
            evidence_id=enc_evidence_id,
            verification_status="document_extracted",
            title="Clinical encounter · Inpatient discharge",
            description="Discharged after stabilization with documented recovery plan and follow-up. Synthetic demonstration record.",
            payload={"encounterId": "enc_seed_1", "facility": "St. Lakeside Hospital"},
        )
        _bump(store, patient=patient, twin=twin, version=6, reason="Clinical encounter recorded", at=at(days=-3, hours=0.45))

        # ---------------------------------------------------------- lab results (synthetic, exact supplied values)
        labs = [
            {
                "id": "lab_seed_crp",
                "code": "CRP",
                "name": "C-reactive protein",
                "panel": "Inflammation",
                "specimen": "Blood",
                "collected_at": at(days=-2, hours=-2),
                "resulted_at": at(days=-2, hours=-1),
                "value_numeric": 12.0,
                "value_text": "",
                "unit": "mg/L",
                "source_range_low": 0.0,
                "source_range_high": 5.0,
                "source_range_text": "0-5 mg/L (source document)",
                "comparison_status": "above_range",
                "comparison_note": "Above source-provided reference range as documented; clinician review advised.",
                "verification_status": "document_extracted",
                "evidence_id": "src_lab_crp",
                "title": "Lab result · C-reactive protein",
                "excerpt": "CRP 12.0 mg/L. Source reference range 0-5 mg/L provided in synthetic lab report.",
            },
            {
                "id": "lab_seed_wbc",
                "code": "WBC",
                "name": "White blood cell count",
                "panel": "CBC",
                "specimen": "Blood",
                "collected_at": at(days=-2, hours=-2),
                "resulted_at": at(days=-2, hours=-1),
                "value_numeric": 9.8,
                "value_text": "",
                "unit": "10^3/uL",
                "source_range_low": 4.0,
                "source_range_high": 11.0,
                "source_range_text": "4.0-11.0 10^3/uL (source document)",
                "comparison_status": "in_range",
                "comparison_note": "Within source-provided reference range.",
                "verification_status": "clinician_verified",
                "evidence_id": "src_lab_wbc",
                "title": "Lab result · White blood cell count",
                "excerpt": "WBC 9.8 10^3/uL. Source reference range 4.0-11.0 10^3/uL provided in synthetic lab report.",
            },
        ]
        for lab in labs:
            _evidence(
                store,
                evidence_id=lab["evidence_id"],
                patient_id=PATIENT_ID,
                source_type="clinician_note",
                title=lab["title"],
                excerpt=lab["excerpt"],
                document_name="synthetic_lab_report.pdf",
                page_ref="Lab panel",
                verification_status=lab["verification_status"],
                extracted_by_ai=False,
                captured_at=lab["resulted_at"],
            )
            store.insert_demo_row(
                "lab_results",
                {
                    "id": lab["id"],
                    "patient_id": PATIENT_ID,
                    "encounter_id": "enc_seed_1",
                    "panel": lab["panel"],
                    "test_code": lab["code"],
                    "test_name": lab["name"],
                    "specimen": lab["specimen"],
                    "collected_at": lab["collected_at"],
                    "resulted_at": lab["resulted_at"],
                    "value_numeric": lab["value_numeric"],
                    "value_text": lab["value_text"],
                    "unit": lab["unit"],
                    "source_range_low": lab["source_range_low"],
                    "source_range_high": lab["source_range_high"],
                    "source_range_text": lab["source_range_text"],
                    "clinician_range_low": None,
                    "clinician_range_high": None,
                    "clinician_range_text": "",
                    "range_source": "provided",
                    "comparison_status": lab["comparison_status"],
                    "comparison_note": lab["comparison_note"],
                    "ambiguity_note": "",
                    "verification_status": lab["verification_status"],
                    "evidence_id": lab["evidence_id"],
                    "synthetic": 1,
                    "created_by_user_id": CLINICIAN_USER_ID,
                    "verified_by_user_id": CLINICIAN_USER_ID if lab["verification_status"] == "clinician_verified" else None,
                    "verified_by_name": "Dr. Nandini Iyer" if lab["verification_status"] == "clinician_verified" else None,
                    "verified_at": lab["resulted_at"] if lab["verification_status"] == "clinician_verified" else None,
                    "created_at": lab["resulted_at"],
                    "updated_at": lab["resulted_at"],
                },
            )
            store.insert_demo_row(
                "encounter_links",
                {
                    "id": f"elnk_{lab['id']}",
                    "patient_id": PATIENT_ID,
                    "encounter_id": "enc_seed_1",
                    "target_type": "lab_result",
                    "target_id": lab["id"],
                    "created_at": lab["resulted_at"],
                },
            )
            _event(
                store,
                event_id=f"evt_{lab['id']}",
                patient_id=PATIENT_ID,
                event_type="lab_result_recorded",
                occurred_at=lab["collected_at"],
                actor_name="Dr. Nandini Iyer",
                actor_role="clinician",
                source_type="clinician_note",
                evidence_id=lab["evidence_id"],
                verification_status=lab["verification_status"],
                title=f"Lab result recorded · {lab['name']}",
                description=f"{lab['name']}: {lab['value_numeric']} {lab['unit']}. Reference range and unit stored exactly as supplied; none inferred.",
                payload={"labResultId": lab["id"], "testCode": lab["code"], "comparisonStatus": lab["comparison_status"]},
            )
        _bump(store, patient=patient, twin=twin, version=7, reason="Lab results recorded", at=at(days=-2, hours=-1))


    # Refresh status after all seed activity.
    milestones_now = store.list_milestones(PATIENT_ID)
    alerts_now = store.list_alerts(PATIENT_ID)
    status, reason = twin_service.compute_status(alerts_now, milestones_now)
    store.update_twin(
        twin["id"],
        version=7 if include_clinical_records else 5,
        status=status,
        reason=reason,
        updated_at=at(days=-2, hours=-1) if include_clinical_records else at(hours=-26),
    )
