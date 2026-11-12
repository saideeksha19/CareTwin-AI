from __future__ import annotations

from datetime import date, datetime

from typing import Any

from app.repositories.store import Store
from app.services.auth import require_access
from app.utils import iso


def _refs(*ids: str | None) -> list[str]:
    return [item for item in ids if item]


def generate_clinical_summary(
    store: Store, *, user: dict[str, Any], patient_id: str
) -> dict[str, Any]:
    access = require_access(store, user, patient_id, "summary:read")
    patient = access.patient
    plan = store.get_plan(patient_id)
    milestones = store.list_milestones(patient_id)
    checkins = store.list_checkins(patient_id, limit=1)
    alerts = [alert for alert in store.list_alerts(patient_id) if alert["status"] == "open"]
    medications = store.list_medications(patient_id)
    follow_ups = store.list_follow_ups(patient_id)
    observations = store.list_observations(patient_id)
    evidence = store.list_evidence(patient_id)
    discharge = next(
        (item for item in evidence if item["source_type"] == "discharge_document"), None
    )

    completed = len([item for item in milestones if item["status"] == "completed"])
    total = len([item for item in milestones if item["status"] != "not_applicable"])
    sections: list[dict[str, Any]] = [
        {
            "title": "Recovery position",
            "finding": (
                f"Day {max(1, (datetime.now().date() - date.fromisoformat(patient['discharged_on'])).days + 1)} "
                f"after discharge following {patient['condition']}. "
                f"{completed} of {total} documented recovery milestones are complete."
            ),
            "evidenceRefs": _refs(
                discharge["id"] if discharge else None,
                plan.get("evidence_id") if plan else None,
            ),
        }
    ]

    if plan:
        sections.append(
            {
                "title": "Documented recovery plan",
                "finding": plan["summary"],
                "evidenceRefs": _refs(plan.get("evidence_id")),
            }
        )

    if checkins:
        latest = checkins[0]
        temperature = (
            f"{latest['temperature_c']:.1f}°C"
            if latest["temperature_c"] is not None
            else "not recorded"
        )
        symptom_text = (
            ", ".join(
                f"{item['label']} {item['severity']}/10"
                for item in latest.get("symptoms", [])
            )
            or "no selected symptoms"
        )
        sections.append(
            {
                "title": "Latest patient-reported check-in",
                "finding": (
                    f"Recorded {latest['submitted_at']}. Overall feeling: "
                    f"{latest['overall_feeling']}. Pain {latest['pain_score']}/10; "
                    f"breathlessness {latest['breathlessness_score']}/10; temperature "
                    f"{temperature}; adherence {latest['adherence']} with "
                    f"{latest['missed_doses']} missed dose(s). Symptoms: {symptom_text}."
                ),
                "evidenceRefs": _refs(latest.get("evidence_id")),
            }
        )

    if alerts:
        sections.append(
            {
                "title": "Open rule-based concerns",
                "finding": " | ".join(
                    f"{alert['severity'].upper()}: {alert['title']}" for alert in alerts
                ),
                "evidenceRefs": _refs(*(alert.get("evidence_id") for alert in alerts)),
            }
        )
    else:
        sections.append(
            {
                "title": "Open rule-based concerns",
                "finding": "No open deterministic safety alerts at the time of generation.",
                "evidenceRefs": _refs(discharge["id"] if discharge else None),
            }
        )

    review_meds = [
        item
        for item in medications
        if item["verification_status"] in {"awaiting_review", "document_extracted"}
    ]
    if review_meds:
        sections.append(
            {
                "title": "Medication instructions awaiting review",
                "finding": ", ".join(
                    f"{item['name']} {item['dosage']} ({item['frequency']})"
                    for item in review_meds
                ),
                "evidenceRefs": _refs(*(item.get("evidence_id") for item in review_meds)),
            }
        )

    upcoming = [item for item in follow_ups if item["status"] in {"scheduled", "upcoming"}]
    if upcoming:
        next_item = upcoming[0]
        sections.append(
            {
                "title": "Next follow-up",
                "finding": (
                    f"{next_item['title']} with {next_item['clinician_name']} "
                    f"({next_item['specialty']}) scheduled for "
                    f"{next_item['scheduled_for']} at {next_item['location']}."
                ),
                "evidenceRefs": _refs(next_item.get("evidence_id")),
            }
        )

    if observations:
        latest_observation = observations[0]
        sections.append(
            {
                "title": "Latest caregiver observation",
                "finding": (
                    f"{latest_observation.get('caregiver_name', 'Caregiver')} reported "
                    f"({latest_observation['category'].replace('_', ' ')}): "
                    f"{latest_observation['note']}"
                ),
                "evidenceRefs": _refs(latest_observation.get("evidence_id")),
            }
        )

    awaiting = len(
        [
            item
            for item in evidence
            if item["verification_status"] in {"awaiting_review", "document_extracted"}
        ]
    )
    verified = len(
        [item for item in evidence if item["verification_status"] == "clinician_verified"]
    )
    sections.append(
        {
            "title": "Evidence coverage",
            "finding": (
                f"{len(evidence)} linked evidence source(s): {verified} clinician verified, "
                f"{awaiting} awaiting review. Patient- and caregiver-reported information "
                "remains attributed and unverified unless reviewed."
            ),
            "evidenceRefs": _refs(*(item["id"] for item in evidence[:6])),
        }
    )

    return {
        "patientId": patient_id,
        "generatedAt": iso(),
        "mode": "deterministic",
        "sections": sections,
        "safetyNotes": [
            "This summary is generated deterministically from recorded data. It is not an AI diagnosis.",
            "Open safety alerts are rule-based flags that require human clinical review.",
            "No medication change is recommended by this summary.",
            "Synthetic demo data only. Not for clinical use.",
        ],
    }
