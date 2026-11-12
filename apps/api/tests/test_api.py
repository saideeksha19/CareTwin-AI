from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

PATIENT = "usr_maya"
CAREGIVER = "usr_arjun"
REVOKED_CAREGIVER = "usr_priya"
CLINICIAN = "usr_nandini"
PATIENT_ID = "pat_maya"


def auth(user_id: str) -> dict[str, str]:
    return {"X-Demo-User-Id": user_id}


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(
        db_path=tmp_path / "caretwin-test.db",
        environment="test",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_health_demo_session_agents_and_ai_status(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["aiState"] == "not_configured"
    assert health.json()["demoMode"] is True

    session = client.get("/api/v1/demo/session")
    assert session.status_code == 200
    body = session.json()
    assert body["patient"]["id"] == PATIENT_ID
    assert body["patient"]["synthetic"] is True
    assert len(body["users"]) == 4
    assert "Synthetic demo access" in body["disclaimer"]
    assert {user["role"] for user in body["users"]} == {
        "patient",
        "caregiver",
        "clinician",
    }
    users_by_id = {user["id"]: user for user in body["users"]}
    assert users_by_id[PATIENT]["consentStatus"] == "not_required"
    assert users_by_id[CLINICIAN]["consentStatus"] == "not_required"
    assert users_by_id[CAREGIVER]["consentStatus"] == "granted"
    assert users_by_id[REVOKED_CAREGIVER]["consentStatus"] == "revoked"
    assert users_by_id[REVOKED_CAREGIVER]["scopes"] == []


def test_demo_role_switch_is_server_confirmed(client: TestClient) -> None:
    switched = client.post(
        "/api/v1/demo/session/switch", json={"userId": CLINICIAN}
    )
    assert switched.status_code == 200, switched.text
    assert {user["id"] for user in switched.json()["users"]} == {
        PATIENT,
        CAREGIVER,
        CLINICIAN,
        REVOKED_CAREGIVER,
    }

    confirmed = client.get("/api/v1/auth/session", headers=auth(CLINICIAN))
    assert confirmed.status_code == 200
    assert confirmed.json()["user"]["id"] == CLINICIAN
    assert confirmed.json()["user"]["role"] == "clinician"

    revoked = client.post(
        "/api/v1/demo/session/switch", json={"userId": REVOKED_CAREGIVER}
    )
    assert revoked.status_code == 200, revoked.text
    denied = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(REVOKED_CAREGIVER)
    )
    assert denied.status_code == 403

    unknown = client.post(
        "/api/v1/demo/session/switch", json={"userId": "usr_nope"}
    )
    assert unknown.status_code == 404

    agents = client.get("/api/v1/agents")
    assert agents.status_code == 200
    agent_list = agents.json()["agents"]
    assert len(agent_list) == 7
    maturities = {agent["phase1Status"] for agent in agent_list}
    assert "working_deterministic" in maturities
    assert "requires_ai_configuration" in maturities

    ai_status = client.get("/api/v1/ai/status")
    assert ai_status.status_code == 200
    ai_body = ai_status.json()
    assert ai_body["configured"] is False
    assert ai_body["state"] == "not_configured"
    assert ai_body["serverSideOnly"] is True
    assert ai_body["groundedContextReady"] is True


def test_patient_twin_is_evidence_linked(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(PATIENT)
    )
    assert response.status_code == 200
    twin = response.json()
    assert twin["patient"]["id"] == PATIENT_ID
    assert twin["patient"]["synthetic"] is True
    assert twin["status"] == "needs_attention"
    assert twin["version"] == 5
    assert len(twin["openAlerts"]) == 2
    assert len(twin["medications"]) == 3
    assert len(twin["milestones"]) == 5
    assert twin["progress"]["completed"] == 1
    assert twin["progress"]["total"] == 5
    assert twin["dataQuality"]["totalEvidence"] == 7
    assert twin["dataQuality"]["awaitingReview"] == 2
    assert twin["dataQuality"]["unverifiedMedicationInstructions"] == 1
    assert twin["visibility"]["role"] == "patient"
    assert "Synthetic demo patient" in twin["syntheticDisclaimer"]

    for medication in twin["medications"]:
        assert "verificationStatus" in medication
        assert medication["evidence"] is not None
        assert medication["provenance"]["sourceType"] == "discharge_document"

    salbutamol = next(
        medication
        for medication in twin["medications"]
        if medication["verificationStatus"] == "awaiting_review"
    )
    assert salbutamol["provenance"]["reviewedBy"] is None
    assert salbutamol["evidence"]["verificationStatus"] == "awaiting_review"

    timeline = client.get(
        f"/api/v1/patients/{PATIENT_ID}/timeline", headers=auth(PATIENT)
    )
    assert timeline.status_code == 200
    assert timeline.json()["total"] == 12
    assert all(event["eventType"] for event in timeline.json()["events"])
    assert any(event["evidence"] is not None for event in timeline.json()["events"])

    evidence = client.get(
        f"/api/v1/patients/{PATIENT_ID}/evidence", headers=auth(PATIENT)
    )
    assert evidence.status_code == 200
    assert len(evidence.json()) == 7
    assert any(item["pageRef"] == "Page 2" for item in evidence.json())

    snapshots = client.get(
        f"/api/v1/patients/{PATIENT_ID}/snapshots", headers=auth(PATIENT)
    )
    assert snapshots.status_code == 200
    assert len(snapshots.json()) >= 1
    assert snapshots.json()[0]["version"] == 5


def test_checkin_creates_deterministic_alerts_and_updates_twin(
    client: TestClient,
) -> None:
    payload = {
        "overallFeeling": "worse",
        "painScore": 8,
        "temperatureC": 38.9,
        "breathlessnessScore": 7,
        "adherence": "missed_one",
        "missedDoses": 1,
        "symptoms": [
            {"code": "chest_pain", "label": "Chest pain", "severity": 8},
            {"code": "breathlessness", "label": "Breathlessness", "severity": 7},
        ],
        "notes": "Synthetic pytest check-in.",
    }
    response = client.post(
        f"/api/v1/patients/{PATIENT_ID}/checkins",
        headers=auth(PATIENT),
        json=payload,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["twinVersion"] == 6
    assert result["safetyDecision"]["outcome"] == "allowed_with_alerts"
    assert len(result["alerts"]) == 2
    assert {alert["category"] for alert in result["alerts"]} == {
        "chest_pain_severity",
        "breathlessness_severity",
    }
    assert len(result["deduplicatedAlerts"]) == 1
    deduplicated = result["deduplicatedAlerts"][0]
    assert deduplicated["category"] == "fever_threshold"
    assert deduplicated["status"] == "open"
    assert deduplicated["id"].startswith("alr_")
    chest = next(
        alert for alert in result["alerts"] if alert["category"] == "chest_pain_severity"
    )
    assert chest["severity"] == "critical"
    assert chest["ruleId"].startswith("rule_")
    assert chest["provenance"]["sourceType"] == "patient_report"
    assert chest["evidence"]["id"] == result["checkIn"]["evidenceId"]

    twin = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(PATIENT)
    ).json()
    assert twin["version"] == 6
    assert twin["status"] == "urgent_review"
    assert len(twin["openAlerts"]) == 4
    assert twin["recentCheckIns"][0]["overallFeeling"] == "worse"

    timeline = client.get(
        f"/api/v1/patients/{PATIENT_ID}/timeline", headers=auth(PATIENT)
    ).json()
    events = timeline["events"]
    assert timeline["total"] >= 16
    assert any(event["eventType"] == "checkin_submitted" for event in events)
    assert any(event["eventType"] == "alert_deduplicated" for event in events)
    dedup_event = next(
        event for event in events if event["eventType"] == "alert_deduplicated"
    )
    assert dedup_event["evidence"] is not None

    repeated = client.post(
        f"/api/v1/patients/{PATIENT_ID}/checkins",
        headers=auth(PATIENT),
        json=payload,
    )
    assert repeated.status_code == 200, repeated.text
    repeated_body = repeated.json()
    assert repeated_body["twinVersion"] == 7
    assert repeated_body["alerts"] == []
    assert {alert["category"] for alert in repeated_body["deduplicatedAlerts"]} == {
        "chest_pain_severity",
        "breathlessness_severity",
        "fever_threshold",
    }
    twin_after_repeat = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(PATIENT)
    ).json()
    assert len(twin_after_repeat["openAlerts"]) == 4

    alerts = client.get(
        f"/api/v1/patients/{PATIENT_ID}/alerts", headers=auth(CLINICIAN)
    ).json()
    assert len([alert for alert in alerts if alert["status"] == "open"]) == 4

    audit = client.get(
        f"/api/v1/patients/{PATIENT_ID}/audit?limit=100", headers=auth(CLINICIAN)
    ).json()
    assert any(
        entry["action"] == "safety_alert.deduplicated" for entry in audit
    )


def test_caregiver_scope_revocation_and_observation(client: TestClient) -> None:
    twin = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(CAREGIVER)
    )
    assert twin.status_code == 200
    assert twin.json()["visibility"]["role"] == "caregiver"
    assert twin.json()["visibility"]["filtered"] is True

    summary = client.get(
        f"/api/v1/patients/{PATIENT_ID}/clinical-summary", headers=auth(CAREGIVER)
    )
    assert summary.status_code == 403
    assert summary.json()["error"]["details"]["requiredScope"] == "summary:read"

    decisions = client.get(
        f"/api/v1/patients/{PATIENT_ID}/safety-decisions", headers=auth(CAREGIVER)
    )
    assert decisions.status_code == 403

    audit = client.get(
        f"/api/v1/patients/{PATIENT_ID}/audit", headers=auth(CAREGIVER)
    )
    assert audit.status_code == 403

    revoked = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(REVOKED_CAREGIVER)
    )
    assert revoked.status_code == 403
    assert revoked.json()["error"]["details"]["reason"] == "consent_revoked_or_missing"
    revoked_alerts = client.get(
        f"/api/v1/patients/{PATIENT_ID}/alerts", headers=auth(REVOKED_CAREGIVER)
    )
    assert revoked_alerts.status_code == 403

    observation = client.post(
        f"/api/v1/patients/{PATIENT_ID}/observations",
        headers=auth(CAREGIVER),
        json={
            "category": "mobility",
            "note": "Maya walked to the kitchen without stopping today.",
        },
    )
    assert observation.status_code == 200, observation.text
    observation_body = observation.json()
    assert observation_body["observation"]["caregiverName"] == "Arjun Rao"
    assert observation_body["safetyDecision"]["outcome"] == "allowed"
    assert observation_body["eventId"].startswith("evt_")

    patient_observation = client.post(
        f"/api/v1/patients/{PATIENT_ID}/observations",
        headers=auth(PATIENT),
        json={"category": "mobility", "note": "Patient should not author this."},
    )
    assert patient_observation.status_code == 403


def test_clinician_review_actions_and_audit(client: TestClient) -> None:
    alerts = client.get(
        f"/api/v1/patients/{PATIENT_ID}/alerts", headers=auth(CLINICIAN)
    ).json()
    open_alert = next(alert for alert in alerts if alert["status"] == "open")
    acknowledged = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{open_alert['id']}/acknowledge",
        headers=auth(CLINICIAN),
        json={"note": "Reviewed during synthetic demo."},
    )
    assert acknowledged.status_code == 200, acknowledged.text
    acknowledged_body = acknowledged.json()
    assert acknowledged_body["alert"]["status"] == "acknowledged"
    assert acknowledged_body["alert"]["acknowledgedBy"] == "Dr. Nandini Iyer"
    assert acknowledged_body["alert"]["acknowledgedAt"] is not None
    assert acknowledged_body["safetyDecision"]["outcome"] == "allowed"

    non_clinician_ack = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{open_alert['id']}/acknowledge",
        headers=auth(PATIENT),
        json={"note": "Should be refused."},
    )
    assert non_clinician_ack.status_code == 403

    still_open = next(
        alert
        for alert in alerts
        if alert["status"] == "open" and alert["id"] != open_alert["id"]
    )
    premature = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{still_open['id']}/resolve",
        headers=auth(CLINICIAN),
        json={"note": "Resolving before acknowledgment should fail."},
    )
    assert premature.status_code == 409
    assert premature.json()["error"]["code"] == "conflict"
    assert "alert_acknowledged" in premature.json()["error"]["details"]["failedChecks"]

    patient_resolve = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{open_alert['id']}/resolve",
        headers=auth(PATIENT),
        json={"note": "Should be refused."},
    )
    assert patient_resolve.status_code == 403

    resolved = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{open_alert['id']}/resolve",
        headers=auth(CLINICIAN),
        json={"note": "Symptoms reviewed and follow-up call completed."},
    )
    assert resolved.status_code == 200, resolved.text
    resolved_body = resolved.json()
    assert resolved_body["alert"]["status"] == "resolved"
    assert resolved_body["alert"]["resolvedBy"] == "Dr. Nandini Iyer"
    assert resolved_body["alert"]["resolvedAt"] is not None
    assert resolved_body["alert"]["resolutionNote"] == (
        "Symptoms reviewed and follow-up call completed."
    )
    assert resolved_body["twinVersion"] == 7
    assert resolved_body["safetyDecision"]["operation"] == "safety_alert.resolve"

    replay = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{open_alert['id']}/resolve",
        headers=auth(CLINICIAN),
        json={"note": "Replay should be refused."},
    )
    assert replay.status_code == 409

    twin = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(CLINICIAN)
    ).json()
    assert twin["status"] == "needs_attention"
    assert len(twin["openAlerts"]) == 1
    medication = next(
        item
        for item in twin["medications"]
        if item["verificationStatus"] == "awaiting_review"
    )
    verified = client.post(
        f"/api/v1/patients/{PATIENT_ID}/medications/{medication['id']}/verify",
        headers=auth(CLINICIAN),
        json={"note": "Checked against discharge page 3."},
    )
    assert verified.status_code == 200, verified.text
    verified_body = verified.json()
    assert (
        verified_body["medication"]["verificationStatus"] == "clinician_verified"
    )
    assert verified_body["twinVersion"] == 8

    patient_verify = client.post(
        f"/api/v1/patients/{PATIENT_ID}/medications/{medication['id']}/verify",
        headers=auth(PATIENT),
        json={"note": "Should be refused."},
    )
    assert patient_verify.status_code == 403

    rules = client.get(
        f"/api/v1/patients/{PATIENT_ID}/monitoring-rules", headers=auth(CLINICIAN)
    ).json()
    fever_rule = next(rule for rule in rules if rule["code"] == "fever_threshold")
    updated_rule = client.patch(
        f"/api/v1/patients/{PATIENT_ID}/monitoring-rules/{fever_rule['id']}",
        headers=auth(CLINICIAN),
        json={"threshold": 39.0},
    )
    assert updated_rule.status_code == 200, updated_rule.text
    assert updated_rule.json()["rule"]["threshold"] == 39.0
    assert updated_rule.json()["safetyDecision"]["outcome"] == "allowed"

    patient_rule = client.patch(
        f"/api/v1/patients/{PATIENT_ID}/monitoring-rules/{fever_rule['id']}",
        headers=auth(PATIENT),
        json={"threshold": 40.0},
    )
    assert patient_rule.status_code == 403

    decisions = client.get(
        f"/api/v1/patients/{PATIENT_ID}/safety-decisions", headers=auth(CLINICIAN)
    ).json()
    assert any(
        decision["operation"] == "medication.verify"
        for decision in decisions
    )
    assert all(decision["checks"] for decision in decisions)

    audit = client.get(
        f"/api/v1/patients/{PATIENT_ID}/audit?limit=50", headers=auth(CLINICIAN)
    ).json()
    actions = {entry["action"] for entry in audit}
    assert "safety_alert.acknowledged" in actions
    assert "safety_alert.resolved" in actions
    assert "medication.verified" in actions
    assert "monitoring_rule.updated" in actions
    assert all(entry["outcome"] == "allowed" for entry in audit)


def test_patient_controls_consent_and_boundary_is_enforced(
    client: TestClient,
) -> None:
    consents = client.get(
        f"/api/v1/patients/{PATIENT_ID}/consents", headers=auth(PATIENT)
    ).json()
    arjun = next(item for item in consents if item["granteeName"] == "Arjun Rao")
    priya = next(item for item in consents if item["granteeName"] == "Priya Rao")
    assert arjun["status"] == "granted"
    assert priya["status"] == "revoked"
    assert "observations:write" in arjun["scopes"]
    assert "summary:read" not in arjun["scopes"]

    granted = client.patch(
        f"/api/v1/patients/{PATIENT_ID}/consents/{priya['id']}",
        headers=auth(PATIENT),
        json={"status": "granted", "reason": "Pytest restores sharing."},
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["consent"]["status"] == "granted"
    assert granted.json()["eventId"].startswith("evt_")
    assert (
        client.get(
            f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(REVOKED_CAREGIVER)
        ).status_code
        == 200
    )

    revoked = client.patch(
        f"/api/v1/patients/{PATIENT_ID}/consents/{arjun['id']}",
        headers=auth(PATIENT),
        json={"status": "revoked", "reason": "Pytest revokes sharing."},
    )
    assert revoked.status_code == 200
    assert revoked.json()["consent"]["status"] == "revoked"
    assert (
        client.get(
            f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(CAREGIVER)
        ).status_code
        == 403
    )

    clinician_change = client.patch(
        f"/api/v1/patients/{PATIENT_ID}/consents/{priya['id']}",
        headers=auth(CLINICIAN),
        json={"status": "revoked", "reason": "Should be refused."},
    )
    assert clinician_change.status_code == 403


def test_monitoring_sweep_creates_one_gap_alert_and_is_idempotent(
    client: TestClient,
) -> None:
    patient_run = client.post(
        f"/api/v1/patients/{PATIENT_ID}/monitoring/run", headers=auth(PATIENT)
    )
    assert patient_run.status_code == 403

    first = client.post(
        f"/api/v1/patients/{PATIENT_ID}/monitoring/run", headers=auth(CLINICIAN)
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["rulesEvaluated"] == 6
    assert first_body["checkinGapHours"] >= 24
    assert len(first_body["alertsCreated"]) == 1
    alert = first_body["alertsCreated"][0]
    assert alert["category"] == "checkin_gap"
    assert alert["ruleId"].startswith("rule_")
    assert alert["severity"] == "moderate"
    assert alert["provenance"]["sourceType"] == "patient_report"
    assert first_body["twinVersion"] == 6

    second = client.post(
        f"/api/v1/patients/{PATIENT_ID}/monitoring/run", headers=auth(CLINICIAN)
    )
    assert second.status_code == 200
    assert second.json()["alertsCreated"] == []

    twin = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(PATIENT)
    ).json()
    assert len(twin["openAlerts"]) == 3


def test_acknowledged_critical_alert_keeps_urgent_status(
    client: TestClient,
) -> None:
    response = client.post(
        f"/api/v1/patients/{PATIENT_ID}/checkins",
        headers=auth(PATIENT),
        json={
            "overallFeeling": "worse",
            "painScore": 9,
            "temperatureC": 39.2,
            "breathlessnessScore": 8,
            "adherence": "all",
            "missedDoses": 0,
            "symptoms": [
                {"code": "chest_pain", "label": "Chest pain", "severity": 9},
                {
                    "code": "breathlessness",
                    "label": "Breathlessness",
                    "severity": 8,
                },
            ],
            "notes": "Synthetic critical alert status test.",
        },
    )
    assert response.status_code == 200, response.text
    alerts = client.get(
        f"/api/v1/patients/{PATIENT_ID}/alerts", headers=auth(CLINICIAN)
    ).json()
    chest = next(
        alert
        for alert in alerts
        if alert["category"] == "chest_pain_severity"
        and alert["status"] == "open"
    )

    acknowledged = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{chest['id']}/acknowledge",
        headers=auth(CLINICIAN),
        json={"note": "Critical chest pain review started."},
    )
    assert acknowledged.status_code == 200, acknowledged.text

    after_ack = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(CLINICIAN)
    ).json()
    assert after_ack["status"] == "urgent_review"
    assert "acknowledged" in after_ack["statusReason"].lower()
    assert "not resolved" in after_ack["statusReason"].lower()

    resolved = client.post(
        f"/api/v1/patients/{PATIENT_ID}/alerts/{chest['id']}/resolve",
        headers=auth(CLINICIAN),
        json={"note": "Chest pain evaluated; escalation completed."},
    )
    assert resolved.status_code == 200, resolved.text

    after_resolve = client.get(
        f"/api/v1/patients/{PATIENT_ID}/twin", headers=auth(CLINICIAN)
    ).json()
    assert after_resolve["status"] == "needs_attention"
    assert after_resolve["statusReason"] == (
        "One or more open rule-based concerns require review."
    )


def test_summary_and_ai_boundary(client: TestClient) -> None:
    summary = client.get(
        f"/api/v1/patients/{PATIENT_ID}/clinical-summary", headers=auth(PATIENT)
    )
    assert summary.status_code == 200
    summary_body = summary.json()
    assert summary_body["mode"] == "deterministic"
    assert len(summary_body["safetyNotes"]) == 4
    assert len(summary_body["sections"]) >= 6
    for section in summary_body["sections"]:
        assert section["title"]
        assert section["finding"]
        assert isinstance(section["evidenceRefs"], list)
    assert any(
        section["title"] == "Latest patient-reported check-in"
        for section in summary_body["sections"]
    )

    clinician_summary = client.get(
        f"/api/v1/patients/{PATIENT_ID}/clinical-summary", headers=auth(CLINICIAN)
    )
    assert clinician_summary.status_code == 200

    unconfigured = client.post(
        "/api/v1/ai/explain",
        headers=auth(PATIENT),
        json={
            "patientId": PATIENT_ID,
            "question": "Explain my recovery plan in simple terms.",
        },
    )
    assert unconfigured.status_code == 503
    error = unconfigured.json()["error"]
    assert error["code"] == "ai_not_configured"
    # Provider configuration stays server-side: the client sees no env var name.
    assert "configKey" not in error["details"]
    assert "GEMINI_API_KEY" not in str(error)

    caregiver_ai = client.post(
        "/api/v1/ai/explain",
        headers=auth(CAREGIVER),
        json={
            "patientId": PATIENT_ID,
            "question": "Explain my recovery plan in simple terms.",
        },
    )
    assert caregiver_ai.status_code == 403
    assert caregiver_ai.json()["error"]["details"]["requiredScope"] == "summary:read"

    anonymous = client.get(f"/api/v1/patients/{PATIENT_ID}/twin")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "authentication_required"
