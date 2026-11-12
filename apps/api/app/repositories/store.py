from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from app.utils import iso, new_id


def _loads(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class Store:
    """Small, explicit repository around a single SQLite connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        row = self.conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(sql, tuple(params)).fetchall()]

    def _insert(self, table: str, values: dict[str, Any]) -> None:
        columns = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        self.conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )

    def _update(self, table: str, entity_id: str, values: dict[str, Any]) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        self.conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            (*values.values(), entity_id),
        )

    def insert_demo_row(self, table: str, values: dict[str, Any]) -> None:
        """Seed-only insert for fixed synthetic demo rows.

        Domain services use explicit methods above. This method exists so the
        seed builder never contains raw SQL while initializing a new demo DB.
        """
        self._insert(table, values)

    # ------------------------------------------------------------------ users
    def get_user(self, user_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM users WHERE id = ?", (user_id,))

    def get_identity_link(
        self, issuer: str, subject: str
    ) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM identity_links WHERE issuer = ? AND subject = ?",
            (issuer, subject),
        )

    def link_identity(
        self, *, user_id: str, issuer: str, subject: str
    ) -> dict[str, Any]:
        existing = self.get_identity_link(issuer, subject)
        if existing:
            return existing
        link = {
            "id": new_id("idn"),
            "issuer": issuer,
            "subject": subject,
            "user_id": user_id,
            "created_at": iso(),
        }
        self._insert("identity_links", link)
        return link

    def revoke_token(
        self,
        *,
        jti: str,
        issuer: str,
        subject: str,
        expires_at: str,
        reason: str = "",
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO auth_revocations "
            "(jti, issuer, subject, expires_at, revoked_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (jti, issuer, subject, expires_at, iso(), reason[:120]),
        )

    def is_token_revoked(self, jti: str) -> bool:
        return self._one("SELECT 1 AS revoked FROM auth_revocations WHERE jti = ?", (jti,)) is not None

    def record_auth_event(self, event: dict[str, Any]) -> None:
        self._insert("auth_events", event)

    # ------------------------------------------------------------- sessions
    def create_auth_session(self, session: dict[str, Any]) -> None:
        self._insert("auth_sessions", session)

    def get_auth_session_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM auth_sessions WHERE token_hash = ?", (token_hash,)
        )

    def get_auth_session(self, session_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM auth_sessions WHERE id = ?", (session_id,))

    def touch_auth_session(self, session_id: str, seen_at: str) -> None:
        self.conn.execute(
            "UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?",
            (seen_at, session_id),
        )

    def revoke_auth_session(
        self, session_id: str, *, reason: str = "", revoked_at: str | None = None
    ) -> None:
        self.conn.execute(
            "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?), "
            "revoked_reason = CASE WHEN revoked_at IS NULL THEN ? ELSE revoked_reason END "
            "WHERE id = ?",
            (revoked_at or iso(), reason[:120], session_id),
        )

    def revoke_user_sessions(
        self, user_id: str, *, reason: str = "", revoked_at: str | None = None
    ) -> int:
        cursor = self.conn.execute(
            "UPDATE auth_sessions SET revoked_at = COALESCE(revoked_at, ?), "
            "revoked_reason = CASE WHEN revoked_at IS NULL THEN ? ELSE revoked_reason END "
            "WHERE user_id = ? AND revoked_at IS NULL",
            (revoked_at or iso(), reason[:120], user_id),
        )
        return cursor.rowcount

    def list_user_sessions(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM auth_sessions WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )

    # ---------------------------------------------------------------- flows
    def create_auth_flow(self, flow: dict[str, Any]) -> None:
        self._insert("auth_flows", flow)

    def get_auth_flow(self, state_hash: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM auth_flows WHERE state_hash = ?", (state_hash,))

    def consume_auth_flow(self, state_hash: str, used_at: str) -> bool:
        """Atomically mark a flow used; False means it was already consumed."""
        cursor = self.conn.execute(
            "UPDATE auth_flows SET used_at = ? WHERE state_hash = ? AND used_at IS NULL",
            (used_at, state_hash),
        )
        return cursor.rowcount == 1

    def list_users(self) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM users ORDER BY CASE role WHEN 'patient' THEN 1 "
            "WHEN 'caregiver' THEN 2 ELSE 3 END"
        )

    # --------------------------------------------------------------- patients
    def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM patients WHERE id = ?", (patient_id,))

    def list_patients(self) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM patients ORDER BY full_name")

    def get_relationship(self, patient_id: str, user_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM care_relationships WHERE patient_id = ? AND user_id = ?",
            (patient_id, user_id),
        )
        if row:
            row["scopes"] = _loads(row.pop("scopes_json"), [])
        return row

    # ---------------------------------------------------------------- consent
    def get_active_consent(
        self, patient_id: str, grantee_user_id: str
    ) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM consent_records WHERE patient_id = ? AND grantee_user_id = ? "
            "AND status = 'granted' ORDER BY updated_at DESC LIMIT 1",
            (patient_id, grantee_user_id),
        )
        if row:
            row["scopes"] = _loads(row.pop("scopes_json"), [])
        return row

    def list_consents(self, patient_id: str) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT c.*, u.name AS grantee_name FROM consent_records c "
            "JOIN users u ON u.id = c.grantee_user_id WHERE c.patient_id = ? "
            "ORDER BY c.updated_at DESC",
            (patient_id,),
        )
        for row in rows:
            row["scopes"] = _loads(row.pop("scopes_json"), [])
        return rows

    def get_consent(self, patient_id: str, consent_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT c.*, u.name AS grantee_name FROM consent_records c "
            "JOIN users u ON u.id = c.grantee_user_id "
            "WHERE c.patient_id = ? AND c.id = ?",
            (patient_id, consent_id),
        )
        if row:
            row["scopes"] = _loads(row.pop("scopes_json"), [])
        return row

    def update_consent_status(
        self, consent_id: str, status: str, updated_at: str
    ) -> None:
        self.conn.execute(
            "UPDATE consent_records SET status = ?, updated_at = ? WHERE id = ?",
            (status, updated_at, consent_id),
        )

    # ------------------------------------------------------------------- twin
    def get_twin(self, patient_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM recovery_twins WHERE patient_id = ?", (patient_id,))

    def update_twin(
        self, twin_id: str, *, version: int, status: str, reason: str, updated_at: str
    ) -> None:
        self.conn.execute(
            "UPDATE recovery_twins SET version = ?, status = ?, status_reason = ?, "
            "updated_at = ? WHERE id = ?",
            (version, status, reason, updated_at, twin_id),
        )

    # ------------------------------------------------------------------- plan
    def get_plan(self, patient_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM recovery_plans WHERE patient_id = ? ORDER BY created_at LIMIT 1",
            (patient_id,),
        )

    # ------------------------------------------------------------- milestones
    def list_milestones(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM milestones WHERE patient_id = ? "
            "ORDER BY due_date ASC, created_at ASC",
            (patient_id,),
        )

    def get_milestone(self, patient_id: str, milestone_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM milestones WHERE patient_id = ? AND id = ?",
            (patient_id, milestone_id),
        )

    def update_milestone(
        self, milestone_id: str, status: str, completed_at: str | None, updated_at: str
    ) -> None:
        self.conn.execute(
            "UPDATE milestones SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (status, completed_at, updated_at, milestone_id),
        )

    # ------------------------------------------------------------ medications
    def list_medications(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM medication_instructions WHERE patient_id = ? "
            "ORDER BY created_at ASC",
            (patient_id,),
        )

    def get_medication(
        self, patient_id: str, medication_id: str
    ) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM medication_instructions WHERE patient_id = ? AND id = ?",
            (patient_id, medication_id),
        )

    def verify_medication(
        self, medication_id: str, reviewer_user_id: str, updated_at: str
    ) -> None:
        self.conn.execute(
            "UPDATE medication_instructions SET verification_status = 'clinician_verified', "
            "updated_at = ? WHERE id = ?",
            (updated_at, medication_id),
        )

    # -------------------------------------------------------------- followups
    def list_follow_ups(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM follow_ups WHERE patient_id = ? ORDER BY scheduled_for ASC",
            (patient_id,),
        )

    def get_follow_up(self, patient_id: str, follow_up_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM follow_ups WHERE patient_id = ? AND id = ?",
            (patient_id, follow_up_id),
        )

    # --------------------------------------------------------------- checkins
    def list_checkins(self, patient_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT c.*, u.name AS submitted_by_name FROM checkins c "
            "JOIN users u ON u.id = c.submitted_by_user_id "
            "WHERE c.patient_id = ? ORDER BY c.submitted_at DESC LIMIT ?",
            (patient_id, limit),
        )
        if not rows:
            return rows
        ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in ids)
        symptoms = self._all(
            f"SELECT * FROM symptom_reports WHERE checkin_id IN ({placeholders}) "
            "ORDER BY severity DESC",
            ids,
        )
        by_checkin: dict[str, list[dict[str, Any]]] = {row_id: [] for row_id in ids}
        for symptom in symptoms:
            by_checkin.setdefault(symptom["checkin_id"], []).append(symptom)
        for row in rows:
            row["symptoms"] = by_checkin.get(row["id"], [])
        return rows

    def get_checkin(self, patient_id: str, checkin_id: str) -> dict[str, Any] | None:
        rows = self.list_checkins(patient_id, limit=500)
        return next((row for row in rows if row["id"] == checkin_id), None)

    def create_checkin(
        self, checkin: dict[str, Any], symptoms: list[dict[str, Any]]
    ) -> None:
        self._insert("checkins", checkin)
        for symptom in symptoms:
            self._insert("symptom_reports", symptom)

    # ---------------------------------------------------------- observations
    def list_observations(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT o.*, u.name AS caregiver_name FROM caregiver_observations o "
            "JOIN users u ON u.id = o.caregiver_user_id "
            "WHERE o.patient_id = ? ORDER BY o.observed_at DESC",
            (patient_id,),
        )

    def create_observation(self, observation: dict[str, Any]) -> None:
        self._insert("caregiver_observations", observation)

    # --------------------------------------------------------------- evidence
    def list_evidence(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM evidence_sources WHERE patient_id = ? ORDER BY captured_at DESC",
            (patient_id,),
        )

    def get_evidence(self, patient_id: str, evidence_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM evidence_sources WHERE patient_id = ? AND id = ?",
            (patient_id, evidence_id),
        )

    def create_evidence(self, evidence: dict[str, Any]) -> None:
        self._insert("evidence_sources", evidence)

    def update_evidence_verification(
        self, evidence_id: str, status: str
    ) -> None:
        self.conn.execute(
            "UPDATE evidence_sources SET verification_status = ? WHERE id = ?",
            (status, evidence_id),
        )

    # ----------------------------------------------------------------- events
    def create_event(self, event: dict[str, Any]) -> None:
        self._insert("recovery_events", event)

    def get_event(self, patient_id: str, event_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM recovery_events WHERE patient_id = ? AND id = ?",
            (patient_id, event_id),
        )
        if row:
            row["payload"] = _loads(row.pop("payload_json"), {})
        return row

    def list_events(
        self,
        patient_id: str,
        *,
        event_type: str | None = None,
        source_type: str | None = None,
        verification_status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses = ["patient_id = ?"]
        params: list[Any] = [patient_id]
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if verification_status:
            clauses.append("verification_status = ?")
            params.append(verification_status)
        params.append(limit)
        rows = self._all(
            "SELECT * FROM recovery_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY occurred_at DESC LIMIT ?",
            params,
        )
        for row in rows:
            row["payload"] = _loads(row.pop("payload_json"), {})
        return rows

    # ----------------------------------------------------------------- alerts
    def create_alert(self, alert: dict[str, Any]) -> None:
        self._insert("safety_alerts", alert)

    def get_alert(self, patient_id: str, alert_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM safety_alerts WHERE patient_id = ? AND id = ?",
            (patient_id, alert_id),
        )

    def list_alerts(
        self, patient_id: str, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        if status:
            return self._all(
                "SELECT * FROM safety_alerts WHERE patient_id = ? AND status = ? "
                "ORDER BY CASE severity WHEN 'critical' THEN 4 WHEN 'urgent' THEN 3 "
                "WHEN 'moderate' THEN 2 ELSE 1 END DESC, created_at DESC",
                (patient_id, status),
            )
        return self._all(
            "SELECT * FROM safety_alerts WHERE patient_id = ? "
            "ORDER BY CASE severity WHEN 'critical' THEN 4 WHEN 'urgent' THEN 3 "
            "WHEN 'moderate' THEN 2 ELSE 1 END DESC, created_at DESC",
            (patient_id,),
        )

    def acknowledge_alert(
        self,
        alert_id: str,
        *,
        user_id: str,
        name: str,
        acknowledged_at: str,
        note: str,
    ) -> None:
        self.conn.execute(
            "UPDATE safety_alerts SET status = 'acknowledged', acknowledged_by_user_id = ?, "
            "acknowledged_by_name = ?, acknowledged_at = ?, resolution_note = ? WHERE id = ?",
            (user_id, name, acknowledged_at, note, alert_id),
        )

    def resolve_alert(
        self,
        alert_id: str,
        *,
        user_id: str,
        name: str,
        resolved_at: str,
        note: str,
    ) -> None:
        self.conn.execute(
            "UPDATE safety_alerts SET status = 'resolved', resolved_by_user_id = ?, "
            "resolved_by_name = ?, resolved_at = ?, resolution_note = ? WHERE id = ?",
            (user_id, name, resolved_at, note, alert_id),
        )

    def unresolved_alert_for_rule(
        self, patient_id: str, rule_code: str
    ) -> dict[str, Any] | None:
        return self._one(
            "SELECT a.* FROM safety_alerts a JOIN monitoring_rules r ON r.id = a.rule_id "
            "WHERE a.patient_id = ? AND r.code = ? "
            "AND a.status IN ('open', 'acknowledged') "
            "ORDER BY a.created_at DESC LIMIT 1",
            (patient_id, rule_code),
        )

    def open_alert_for_rule(
        self, patient_id: str, rule_code: str, *, since: str | None = None
    ) -> dict[str, Any] | None:
        sql = (
            "SELECT a.* FROM safety_alerts a JOIN monitoring_rules r ON r.id = a.rule_id "
            "WHERE a.patient_id = ? AND r.code = ? AND a.status = 'open'"
        )
        params: list[Any] = [patient_id, rule_code]
        if since:
            sql += " AND a.created_at >= ?"
            params.append(since)
        sql += " ORDER BY a.created_at DESC LIMIT 1"
        return self._one(sql, params)

    # ------------------------------------------------------------------ rules
    def list_rules(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM monitoring_rules WHERE patient_id = ? ORDER BY code",
            (patient_id,),
        )

    def get_rule(self, patient_id: str, rule_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM monitoring_rules WHERE patient_id = ? AND id = ?",
            (patient_id, rule_id),
        )

    def get_rule_by_code(self, patient_id: str, code: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM monitoring_rules WHERE patient_id = ? AND code = ?",
            (patient_id, code),
        )

    def update_rule(
        self,
        rule_id: str,
        *,
        threshold: float | None,
        enabled: bool | None,
        configured_by_user_id: str,
        updated_at: str,
    ) -> None:
        assignments = ["updated_at = ?", "configured_by_user_id = ?"]
        params: list[Any] = [updated_at, configured_by_user_id]
        if threshold is not None:
            assignments.append("threshold = ?")
            params.append(threshold)
        if enabled is not None:
            assignments.append("enabled = ?")
            params.append(1 if enabled else 0)
        params.append(rule_id)
        self.conn.execute(
            f"UPDATE monitoring_rules SET {', '.join(assignments)} WHERE id = ?",
            tuple(params),
        )

    # ----------------------------------------------------------------- audit
    def create_audit(self, audit: dict[str, Any]) -> None:
        self._insert("audit_events", audit)

    def list_audit(self, patient_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM audit_events WHERE patient_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (patient_id, limit),
        )
        for row in rows:
            row["details"] = _loads(row.pop("details_json"), {})
        return rows

    # ------------------------------------------------------------- snapshots
    def create_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._insert("twin_snapshots", snapshot)

    def list_snapshots(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT id, patient_id, twin_id, version, reason, created_at "
            "FROM twin_snapshots WHERE patient_id = ? ORDER BY version DESC",
            (patient_id,),
        )

    def get_snapshot(self, patient_id: str, snapshot_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM twin_snapshots WHERE patient_id = ? AND id = ?",
            (patient_id, snapshot_id),
        )
        if row:
            row["snapshot"] = _loads(row.pop("snapshot_json"), {})
        return row

    # -------------------------------------------------------- safety decisions
    def create_safety_decision(self, decision: dict[str, Any]) -> None:
        self._insert("safety_decisions", decision)

    def list_safety_decisions(
        self, patient_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM safety_decisions WHERE patient_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (patient_id, limit),
        )
        for row in rows:
            row["checks"] = _loads(row.pop("checks_json"), [])
        return rows

    def update_safety_decision(
        self, decision_id: str, *, checks: list[dict[str, Any]], outcome: str
    ) -> None:
        self.conn.execute(
            "UPDATE safety_decisions SET checks_json = ?, outcome = ? WHERE id = ?",
            (_dumps(checks), outcome, decision_id),
        )


    # --------------------------------------------------------------- lab results
    def list_lab_results(self, patient_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM lab_results WHERE patient_id = ? "
            "ORDER BY collected_at DESC, created_at DESC LIMIT ?",
            (patient_id, limit),
        )

    def get_lab_result(self, patient_id: str, lab_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM lab_results WHERE patient_id = ? AND id = ?",
            (patient_id, lab_id),
        )

    def create_lab_result(self, lab: dict[str, Any]) -> None:
        self._insert("lab_results", lab)

    # -------------------------------------------------------- clinical encounters
    def list_encounters(self, patient_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM clinical_encounters WHERE patient_id = ? "
            "ORDER BY occurred_at DESC, created_at DESC LIMIT ?",
            (patient_id, limit),
        )

    def get_encounter(self, patient_id: str, encounter_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM clinical_encounters WHERE patient_id = ? AND id = ?",
            (patient_id, encounter_id),
        )

    def create_encounter(self, encounter: dict[str, Any]) -> None:
        self._insert("clinical_encounters", encounter)

    def create_encounter_link(self, link: dict[str, Any]) -> None:
        self._insert("encounter_links", link)

    def list_encounter_links(self, encounter_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM encounter_links WHERE encounter_id = ? ORDER BY created_at ASC",
            (encounter_id,),
        )


    # ----------------------------------------------------------- documents
    def create_document(self, doc: dict[str, Any]) -> None:
        self._insert("medical_documents", doc)

    def get_document(self, patient_id: str, document_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM medical_documents WHERE patient_id = ? AND id = ?",
            (patient_id, document_id),
        )

    def list_documents(self, patient_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM medical_documents WHERE patient_id = ? ORDER BY uploaded_at DESC",
            (patient_id,),
        )

    def find_document_by_hash(self, patient_id: str, content_hash: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM medical_documents WHERE patient_id = ? AND content_hash = ? ORDER BY uploaded_at DESC LIMIT 1",
            (patient_id, content_hash),
        )

    def update_document(self, document_id: str, values: dict[str, Any]) -> None:
        self._update("medical_documents", document_id, values)

    def delete_document_pages(self, document_id: str) -> None:
        self.conn.execute("DELETE FROM document_pages WHERE document_id = ?", (document_id,))

    def create_document_page(self, page: dict[str, Any]) -> None:
        self._insert("document_pages", page)

    def list_document_pages(self, document_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM document_pages WHERE document_id = ? ORDER BY page_number ASC",
            (document_id,),
        )

    def delete_document_extractions(self, document_id: str) -> None:
        self.conn.execute("DELETE FROM document_extractions WHERE document_id = ?", (document_id,))

    def create_document_extraction(self, item: dict[str, Any]) -> None:
        self._insert("document_extractions", item)

    def list_document_extractions(self, document_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM document_extractions WHERE document_id = ? ORDER BY page_number ASC, created_at ASC",
            (document_id,),
        )

    def get_document_extraction(self, patient_id: str, extraction_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM document_extractions WHERE patient_id = ? AND id = ?",
            (patient_id, extraction_id),
        )

    def update_document_extraction(self, extraction_id: str, values: dict[str, Any]) -> None:
        self._update("document_extractions", extraction_id, values)

    def create_extraction_review(self, review: dict[str, Any]) -> None:
        self._insert("document_extraction_reviews", review)

    def list_extraction_reviews(self, extraction_id: str) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM document_extraction_reviews WHERE extraction_id = ? ORDER BY created_at DESC",
            (extraction_id,),
        )

    def create_guidance_history(self, row: dict[str, Any]) -> None:
        self._insert("guidance_history", row)

    def create_assistant_message(self, row: dict[str, Any]) -> None:
        self._insert("assistant_messages", row)

    def list_assistant_messages(
        self, patient_id: str, conversation_id: str | None = None, limit: int = 60
    ) -> list[dict[str, Any]]:
        if conversation_id:
            rows = self._all(
                "SELECT * FROM assistant_messages WHERE patient_id = ? AND conversation_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (patient_id, conversation_id, limit),
            )
        else:
            rows = self._all(
                "SELECT * FROM assistant_messages WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?",
                (patient_id, limit),
            )
        for row in rows:
            row["citations"] = _loads(row.pop("citations_json", None), [])
            row["evidence"] = _loads(row.pop("evidence_json", None), {})
        return list(reversed(rows))

    def get_ai_explanation(
        self, document_id: str, mode: str, input_hash: str, model: str
    ) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM ai_explanations WHERE document_id = ? AND mode = ? AND model = ? "
            "AND input_hash = ? ORDER BY created_at DESC LIMIT 1",
            (document_id, mode, model, input_hash),
        )
        if not row:
            return None
        payload = _loads(row.get("payload_json"), {})
        if isinstance(payload, dict):
            payload["cached"] = True
        return payload or None

    def latest_ai_explanation(self, document_id: str, mode: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM ai_explanations WHERE document_id = ? AND mode = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (document_id, mode),
        )
        if not row:
            return None
        payload = _loads(row.get("payload_json"), {})
        if isinstance(payload, dict):
            payload["cached"] = True
        return payload or None

    def save_ai_explanation(self, row: dict[str, Any]) -> None:
        self._insert("ai_explanations", row)

    def list_guidance_history(self, patient_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM guidance_history WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?",
            (patient_id, limit),
        )
        for row in rows:
            row["citations"] = _loads(row.pop("citations_json"), [])
            row["evidence"] = _loads(row.pop("evidence_json"), [])
        return rows
