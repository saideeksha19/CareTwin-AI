from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('patient', 'caregiver', 'clinician')),
    title TEXT NOT NULL DEFAULT '',
    organization TEXT NOT NULL DEFAULT '',
    initials TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    mrn TEXT NOT NULL,
    full_name TEXT NOT NULL,
    preferred_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    sex TEXT NOT NULL,
    primary_language TEXT NOT NULL,
    condition TEXT NOT NULL,
    discharged_on TEXT NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS care_relationships (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    relationship TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (patient_id, user_id)
);

CREATE TABLE IF NOT EXISTS consent_records (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    grantee_user_id TEXT NOT NULL REFERENCES users(id),
    grantee_relationship TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    status TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_twins (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL UNIQUE REFERENCES patients(id),
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    status_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_plans (
    id TEXT PRIMARY KEY,
    twin_id TEXT NOT NULL REFERENCES recovery_twins(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    start_date TEXT NOT NULL,
    target_end_date TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by_user_id TEXT,
    evidence_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL,
    completed_at TEXT,
    verification_status TEXT NOT NULL,
    evidence_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medication_instructions (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    route TEXT NOT NULL,
    frequency TEXT NOT NULL,
    duration TEXT NOT NULL,
    instructions TEXT NOT NULL,
    status TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    prescribed_by TEXT NOT NULL,
    evidence_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    title TEXT NOT NULL,
    clinician_name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    evidence_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkins (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    submitted_by_user_id TEXT NOT NULL REFERENCES users(id),
    submitted_at TEXT NOT NULL,
    overall_feeling TEXT NOT NULL,
    pain_score INTEGER NOT NULL,
    temperature_c REAL,
    breathlessness_score INTEGER NOT NULL,
    adherence TEXT NOT NULL,
    missed_doses INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL,
    evidence_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symptom_reports (
    id TEXT PRIMARY KEY,
    checkin_id TEXT NOT NULL REFERENCES checkins(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    symptom_code TEXT NOT NULL,
    label TEXT NOT NULL,
    severity INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS caregiver_observations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    caregiver_user_id TEXT NOT NULL REFERENCES users(id),
    observed_at TEXT NOT NULL,
    category TEXT NOT NULL,
    note TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    patient_context TEXT NOT NULL DEFAULT '',
    consent_reference TEXT,
    verification_status TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'not_required',
    reviewed_by_user_id TEXT,
    reviewed_by_name TEXT,
    reviewed_at TEXT,
    review_note TEXT,
    rule_evaluation_ids_json TEXT NOT NULL DEFAULT '[]',
    alert_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_sources (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    document_name TEXT NOT NULL,
    page_ref TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 1,
    verification_status TEXT NOT NULL,
    extracted_by_ai INTEGER NOT NULL DEFAULT 0,
    captured_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_events (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    twin_id TEXT NOT NULL REFERENCES recovery_twins(id),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    actor_user_id TEXT,
    actor_name TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    source_type TEXT NOT NULL,
    evidence_id TEXT,
    verification_status TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS safety_alerts (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    checkin_id TEXT,
    rule_id TEXT NOT NULL,
    rule_version INTEGER NOT NULL DEFAULT 1,
    evaluation_id TEXT,
    input_event_id TEXT,
    matched_condition TEXT NOT NULL DEFAULT '',
    review_status TEXT NOT NULL DEFAULT 'pending',
    source_type TEXT NOT NULL DEFAULT 'checkin',
    source_id TEXT,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_id TEXT,
    created_at TEXT NOT NULL,
    acknowledged_by_user_id TEXT,
    acknowledged_by_name TEXT,
    acknowledged_at TEXT,
    resolution_note TEXT,
    resolved_by_user_id TEXT,
    resolved_by_name TEXT,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS monitoring_rules (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    kind TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'checkin',
    input_type TEXT NOT NULL DEFAULT 'symptom_severity',
    input_key TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT 'greater_than_or_equal',
    threshold REAL NOT NULL,
    comparison_value TEXT,
    window_hours REAL,
    cooldown_hours REAL NOT NULL DEFAULT 0,
    requires_human_review INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    severity TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    configured_by_user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (patient_id, code)
);

CREATE TABLE IF NOT EXISTS monitoring_rule_versions (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    changed_by_user_id TEXT,
    change_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (rule_id, version)
);

CREATE TABLE IF NOT EXISTS monitoring_evaluations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    twin_id TEXT,
    rule_id TEXT NOT NULL,
    rule_code TEXT NOT NULL,
    rule_version INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_id TEXT,
    input_type TEXT NOT NULL,
    input_key TEXT NOT NULL DEFAULT '',
    observed_value_json TEXT NOT NULL DEFAULT 'null',
    operator TEXT NOT NULL,
    threshold_json TEXT NOT NULL DEFAULT 'null',
    matched INTEGER NOT NULL,
    severity TEXT NOT NULL,
    explanation TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_results (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT,
    panel TEXT NOT NULL DEFAULT '',
    test_code TEXT NOT NULL,
    test_name TEXT NOT NULL,
    specimen TEXT NOT NULL DEFAULT '',
    collected_at TEXT NOT NULL,
    resulted_at TEXT,
    value_numeric REAL,
    value_text TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    source_range_low REAL,
    source_range_high REAL,
    source_range_text TEXT NOT NULL DEFAULT '',
    clinician_range_low REAL,
    clinician_range_high REAL,
    clinician_range_text TEXT NOT NULL DEFAULT '',
    range_source TEXT NOT NULL DEFAULT 'none',
    comparison_status TEXT NOT NULL DEFAULT 'unavailable',
    comparison_note TEXT NOT NULL DEFAULT '',
    ambiguity_note TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'document_extracted',
    evidence_id TEXT,
    synthetic INTEGER NOT NULL DEFAULT 1,
    created_by_user_id TEXT,
    verified_by_user_id TEXT,
    verified_by_name TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clinical_encounters (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    ended_at TEXT,
    facility TEXT NOT NULL DEFAULT '',
    provider_name TEXT NOT NULL DEFAULT '',
    provider_specialty TEXT NOT NULL DEFAULT '',
    clinician_user_id TEXT,
    reason TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    discharge_instructions TEXT NOT NULL DEFAULT '',
    follow_up_plan TEXT NOT NULL DEFAULT '',
    source_document TEXT NOT NULL DEFAULT '',
    evidence_id TEXT,
    verification_status TEXT NOT NULL DEFAULT 'document_extracted',
    review_status TEXT NOT NULL DEFAULT 'pending',
    created_by_user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS encounter_links (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT NOT NULL REFERENCES clinical_encounters(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (encounter_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    actor_user_id TEXT,
    actor_name TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS twin_snapshots (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    twin_id TEXT NOT NULL REFERENCES recovery_twins(id),
    version INTEGER NOT NULL,
    reason TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS safety_decisions (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    operation TEXT NOT NULL,
    outcome TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_patient_time
    ON recovery_events(patient_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_patient_status
    ON safety_alerts(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_checkins_patient_time
    ON checkins(patient_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_patient_time
    ON audit_events(patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_patient
    ON evidence_sources(patient_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_patient_version
    ON twin_snapshots(patient_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_evaluations_patient_time
    ON monitoring_evaluations(patient_id, evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluations_rule
    ON monitoring_evaluations(rule_id, evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_labs_patient_time
    ON lab_results(patient_id, collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_encounters_patient_time
    ON clinical_encounters(patient_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_encounter_links
    ON encounter_links(encounter_id, target_type);
CREATE TABLE IF NOT EXISTS medical_documents (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    uploaded_by_user_id TEXT,
    uploaded_by_name TEXT NOT NULL DEFAULT '',
    uploaded_by_role TEXT NOT NULL DEFAULT '',
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    document_type TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_extension TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    upload_status TEXT NOT NULL DEFAULT 'stored',
    processing_status TEXT NOT NULL DEFAULT 'uploaded',
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    extraction_method TEXT NOT NULL DEFAULT '',
    extraction_error TEXT NOT NULL DEFAULT '',
    page_count INTEGER,
    is_duplicate_of TEXT,
    uploaded_at TEXT NOT NULL,
    processed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_pages (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES medical_documents(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    page_number INTEGER NOT NULL,
    extraction_method TEXT NOT NULL DEFAULT '',
    text_content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (document_id, page_number)
);

CREATE TABLE IF NOT EXISTS document_extractions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES medical_documents(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    item_type TEXT NOT NULL,
    label TEXT NOT NULL,
    value_text TEXT NOT NULL DEFAULT '',
    value_numeric REAL,
    unit TEXT NOT NULL DEFAULT '',
    reference_range TEXT NOT NULL DEFAULT '',
    abnormal_flag TEXT NOT NULL DEFAULT '',
    page_number INTEGER,
    source_text TEXT NOT NULL DEFAULT '',
    extraction_status TEXT NOT NULL DEFAULT 'extracted',
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    confidence_note TEXT NOT NULL DEFAULT '',
    evidence_id TEXT,
    verified_by_user_id TEXT,
    verified_by_name TEXT,
    verified_at TEXT,
    rejected_by_user_id TEXT,
    rejected_by_name TEXT,
    rejected_at TEXT,
    review_note TEXT NOT NULL DEFAULT '',
    corrected_value_text TEXT,
    original_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_extraction_reviews (
    id TEXT PRIMARY KEY,
    extraction_id TEXT NOT NULL REFERENCES document_extractions(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES medical_documents(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    action TEXT NOT NULL,
    actor_user_id TEXT,
    actor_name TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    previous_verification_status TEXT NOT NULL,
    new_verification_status TEXT NOT NULL,
    previous_value_json TEXT NOT NULL DEFAULT '{}',
    new_value_json TEXT NOT NULL DEFAULT '{}',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guidance_history (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    requested_by_user_id TEXT,
    requested_by_name TEXT NOT NULL,
    requested_by_role TEXT NOT NULL,
    question TEXT NOT NULL DEFAULT '',
    guidance_type TEXT NOT NULL,
    mode TEXT NOT NULL,
    ai_state TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    answer TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    grounded INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identity_links (
    id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE (issuer, subject)
);

CREATE TABLE IF NOT EXISTS auth_revocations (
    jti TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS auth_events (
    id TEXT PRIMARY KEY,
    event TEXT NOT NULL,
    outcome TEXT NOT NULL,
    user_id TEXT,
    issuer TEXT NOT NULL DEFAULT '',
    subject_hash TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_events_time
    ON auth_events(occurred_at DESC);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_hash TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    auth_time INTEGER,
    amr TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT,
    revoked_reason TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
    ON auth_sessions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS auth_flows (
    state_hash TEXT PRIMARY KEY,
    nonce TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
);

CREATE TABLE IF NOT EXISTS assistant_messages (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    conversation_id TEXT NOT NULL,
    user_id TEXT,
    user_role TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    mode TEXT NOT NULL,
    ai_state TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assistant_messages_conversation
    ON assistant_messages(patient_id, conversation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_explanations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    document_id TEXT NOT NULL REFERENCES medical_documents(id),
    mode TEXT NOT NULL,
    model TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    validation_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_explanations_lookup
    ON ai_explanations(document_id, mode, model, input_hash, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_documents_patient_time
    ON medical_documents(patient_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_hash
    ON medical_documents(patient_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_document_pages_doc
    ON document_pages(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_extractions_document
    ON document_extractions(document_id, verification_status);
CREATE INDEX IF NOT EXISTS idx_extractions_patient
    ON document_extractions(patient_id, verification_status);
CREATE INDEX IF NOT EXISTS idx_extraction_reviews_extraction
    ON document_extraction_reviews(extraction_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_guidance_patient_time
    ON guidance_history(patient_id, created_at DESC);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    existing = {
        row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


_RULE_METADATA = {
    "chest_pain_severity": ("symptom_severity", "chest_pain", "greater_than_or_equal"),
    "breathlessness_severity": (
        "symptom_severity",
        "breathlessness",
        "greater_than_or_equal",
    ),
    "fever_threshold": ("temperature", "temperature_c", "greater_than_or_equal"),
    "adherence_gap": ("missed_doses", "missed_doses", "greater_than_or_equal"),
    "pain_escalation": ("pain_delta", "pain_score", "greater_than_or_equal"),
    "checkin_gap": ("checkin_gap_hours", "submitted_at", "greater_than_or_equal"),
}


def _backfill_rule_metadata(conn: sqlite3.Connection) -> None:
    for code, (input_type, input_key, operator) in _RULE_METADATA.items():
        conn.execute(
            "UPDATE monitoring_rules SET source_type = 'checkin', input_type = ?, "
            "input_key = ?, operator = ? WHERE code = ? "
            "AND (input_key = '' OR input_key IS NULL)",
            (input_type, input_key, operator, code),
        )
    rows = conn.execute("SELECT * FROM monitoring_rules").fetchall()
    for row in rows:
        existing = conn.execute(
            "SELECT 1 FROM monitoring_rule_versions WHERE rule_id = ? AND version = ?",
            (row["id"], row["version"] or 1),
        ).fetchone()
        if existing:
            continue
        snapshot = {key: row[key] for key in row.keys()}
        version = int(row["version"] or 1)
        conn.execute(
            "INSERT OR IGNORE INTO monitoring_rule_versions "
            "(id, rule_id, patient_id, version, snapshot_json, changed_by_user_id, "
            "change_reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"rvr_{uuid.uuid4().hex[:20]}",
                row["id"],
                row["patient_id"],
                version,
                json.dumps(snapshot, separators=(",", ":"), default=str),
                row["configured_by_user_id"],
                "Migrated from Phase 1 rule state",
                row["updated_at"],
            ),
        )


# Additive, idempotent migration steps. Every step must be safe to re-run and
# must never rewrite or delete existing medical/demo records.
MIGRATIONS: list[tuple[str, str]] = [
    (
        "20261111_001_schema_migrations_registry",
        "CREATE TABLE IF NOT EXISTS schema_migrations (\n"
        "    id TEXT PRIMARY KEY,\n"
        "    applied_at TEXT NOT NULL\n"
        ")",
    ),
    (
        "20261111_002_operational_indexes",
        "CREATE INDEX IF NOT EXISTS idx_documents_patient_uploaded "
        "ON medical_documents(patient_id, uploaded_at DESC);\n"
        "CREATE INDEX IF NOT EXISTS idx_audit_patient_action_time "
        "ON audit_events(patient_id, action, created_at DESC);\n"
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires "
        "ON auth_sessions(expires_at);\n"
        "CREATE INDEX IF NOT EXISTS idx_auth_flows_expires "
        "ON auth_flows(expires_at);\n"
        "CREATE INDEX IF NOT EXISTS idx_guidance_patient_created "
        "ON guidance_history(patient_id, created_at DESC)",
    ),
]


def _apply_migrations(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row["id"] for row in conn.execute("SELECT id FROM schema_migrations").fetchall()}
    newly_applied: list[str] = []
    for migration_id, sql in MIGRATIONS:
        if migration_id in applied:
            continue
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (id, applied_at) VALUES (?, datetime('now'))",
            (migration_id,),
        )
        newly_applied.append(migration_id)
    # Keep SQLite user_version as a monotonic marker of the highest known migration
    # generation without breaking older databases (never decremented).
    try:
        current = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
        target = max(current, len(MIGRATIONS))
        if target != current:
            conn.execute(f"PRAGMA user_version = {target}")
    except Exception:
        pass
    return newly_applied


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        for table, columns in {
            "caregiver_observations": {
                "details_json": "TEXT NOT NULL DEFAULT '{}'",
                "patient_context": "TEXT NOT NULL DEFAULT ''",
                "consent_reference": "TEXT",
                "review_status": "TEXT NOT NULL DEFAULT 'not_required'",
                "reviewed_by_user_id": "TEXT",
                "reviewed_by_name": "TEXT",
                "reviewed_at": "TEXT",
                "review_note": "TEXT",
                "rule_evaluation_ids_json": "TEXT NOT NULL DEFAULT '[]'",
                "alert_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            },
            "monitoring_rules": {
                "source_type": "TEXT NOT NULL DEFAULT 'checkin'",
                "input_type": "TEXT NOT NULL DEFAULT 'symptom_severity'",
                "input_key": "TEXT NOT NULL DEFAULT ''",
                "operator": "TEXT NOT NULL DEFAULT 'greater_than_or_equal'",
                "comparison_value": "TEXT",
                "window_hours": "REAL",
                "cooldown_hours": "REAL NOT NULL DEFAULT 0",
                "requires_human_review": "INTEGER NOT NULL DEFAULT 1",
                "version": "INTEGER NOT NULL DEFAULT 1",
            },
            "safety_alerts": {
                "rule_version": "INTEGER NOT NULL DEFAULT 1",
                "evaluation_id": "TEXT",
                "input_event_id": "TEXT",
                "matched_condition": "TEXT NOT NULL DEFAULT ''",
                "review_status": "TEXT NOT NULL DEFAULT 'pending'",
                "source_type": "TEXT NOT NULL DEFAULT 'checkin'",
                "source_id": "TEXT",
                "resolved_by_user_id": "TEXT",
                "resolved_by_name": "TEXT",
                "resolved_at": "TEXT",
            },
        }.items():
            for column, definition in columns.items():
                _ensure_column(conn, table, column, definition)
        _backfill_rule_metadata(conn)
        _apply_migrations(conn)
        conn.commit()
