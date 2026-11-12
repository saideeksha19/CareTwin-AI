from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MONITORING_OPERATORS = Literal[
    "equals",
    "not_equals",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "missing",
    "stale",
    "in_set",
]
MONITORING_INPUT_TYPES = Literal[
    "symptom_severity",
    "temperature",
    "pain_delta",
    "missed_doses",
    "checkin_gap_hours",
    "observation_category",
    "observation_severity",
    "observation_note",
]

def to_camel(value: str) -> str:
    parts = value.split('_')
    return parts[0] + ''.join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )


class CheckinSymptomInput(StrictModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=2, max_length=80)
    severity: int = Field(ge=0, le=10)
    notes: str = Field(default="", max_length=500)


class CreateCheckinRequest(StrictModel):
    overall_feeling: Literal["better", "same", "worse"]
    pain_score: int = Field(ge=0, le=10)
    temperature_c: float | None = Field(default=None, ge=30.0, le=45.0)
    breathlessness_score: int = Field(ge=0, le=10)
    adherence: Literal["all", "missed_one", "missed_multiple"]
    missed_doses: int = Field(default=0, ge=0, le=20)
    symptoms: list[CheckinSymptomInput] = Field(default_factory=list, max_length=12)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_adherence_consistency(self) -> "CreateCheckinRequest":
        if self.adherence == "all" and self.missed_doses > 0:
            raise ValueError("missed_doses must be zero when adherence is 'all'.")
        if self.adherence == "missed_one" and self.missed_doses not in {0, 1}:
            raise ValueError("missed_doses must be 0 or 1 when adherence is 'missed_one'.")
        codes = [symptom.code for symptom in self.symptoms]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate symptom codes are not allowed.")
        if self.notes and len(self.notes) < 2 and self.symptoms:
            raise ValueError("Notes must contain at least two characters when provided.")
        return self


class CreateObservationRequest(StrictModel):
    category: Literal[
        "general",
        "mobility",
        "appetite",
        "medication_support",
        "symptom",
        "appointment",
    ]
    note: str = Field(min_length=3, max_length=2000)


class ConsentUpdateRequest(StrictModel):
    status: Literal["granted", "revoked"]
    reason: str = Field(default="", max_length=500)


class AlertAcknowledgeRequest(StrictModel):
    note: str = Field(default="", max_length=1000)


class AlertResolveRequest(StrictModel):
    note: str = Field(min_length=3, max_length=1000)


class MedicationVerifyRequest(StrictModel):
    note: str = Field(default="", max_length=1000)


class MonitoringRuleUpdateRequest(StrictModel):
    threshold: float | None = Field(default=None, ge=0)
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "MonitoringRuleUpdateRequest":
        if self.threshold is None and self.enabled is None:
            raise ValueError("Provide at least one of threshold or enabled.")
        return self


class MilestoneUpdateRequest(StrictModel):
    status: Literal["pending", "in_progress", "completed", "overdue", "not_applicable"]
    note: str = Field(default="", max_length=1000)


class AiExplainRequest(StrictModel):
    patient_id: str = Field(min_length=3, max_length=64)
    question: str = Field(min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank.")
        return value


class HealthResponse(ApiModel):
    status: str
    service: str
    version: str
    environment: str
    database: str
    ai_state: str
    demo_mode: bool
    # "demo" or "production"; the client never infers identity mode from a header.
    auth_mode: str = "demo"
    request_id: str | None = None
    components: dict[str, Any] = Field(default_factory=dict)


class DemoUserResponse(ApiModel):
    id: str
    name: str
    role: str
    title: str
    organization: str
    initials: str
    patient_id: str
    linked_patient_name: str
    consent_status: str = "not_required"
    scopes: list[str] = Field(default_factory=list)


class DemoSessionResponse(ApiModel):
    users: list[DemoUserResponse]
    patient: dict[str, Any]
    disclaimer: str


class DemoSwitchRequest(StrictModel):
    user_id: str = Field(min_length=1, max_length=64, pattern=r"^usr_[a-z0-9_]+$")


class CheckinResponse(ApiModel):
    check_in: dict[str, Any]
    event_id: str
    alerts: list[dict[str, Any]]
    deduplicated_alerts: list[dict[str, Any]]
    safety_decision: dict[str, Any]
    twin_version: int


class ObservationResponse(ApiModel):
    observation: dict[str, Any]
    event_id: str
    safety_decision: dict[str, Any]
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    deduplicated_alerts: list[dict[str, Any]] = Field(default_factory=list)


class TimelineResponse(ApiModel):
    patient_id: str
    generated_at: str
    total: int
    events: list[dict[str, Any]]


class TwinResponse(ApiModel):
    patient: dict[str, Any]
    version: int
    status: str
    status_reason: str
    updated_at: str
    progress: dict[str, Any]
    plan: dict[str, Any]
    milestones: list[dict[str, Any]]
    medications: list[dict[str, Any]]
    follow_ups: list[dict[str, Any]]
    recent_check_ins: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    open_alerts: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    next_follow_up: dict[str, Any] | None
    data_quality: dict[str, Any]
    visibility: dict[str, Any]
    synthetic_disclaimer: str
    clinical_documents: list[dict[str, Any]] = Field(default_factory=list)
    document_findings: dict[str, Any] = Field(default_factory=dict)
    body_region_note: str = Field(default="")


class CreateLabResultRequest(StrictModel):
    test_code: str = Field(min_length=1, max_length=64)
    test_name: str = Field(min_length=1, max_length=120)
    panel: str = Field(default="", max_length=120)
    specimen: str = Field(default="", max_length=120)
    collected_at: str = Field(min_length=10, max_length=40)
    resulted_at: str | None = Field(default=None, max_length=40)
    value_numeric: float | None = None
    value_text: str = Field(default="", max_length=200)
    unit: str = Field(default="", max_length=40)
    source_range_low: float | None = None
    source_range_high: float | None = None
    source_range_text: str = Field(default="", max_length=120)
    clinician_range_low: float | None = None
    clinician_range_high: float | None = None
    clinician_range_text: str = Field(default="", max_length=120)
    comparison_status: Literal["in_range", "above_range", "below_range", "abnormal", "unavailable"] = "unavailable"
    comparison_note: str = Field(default="", max_length=500)
    ambiguity_note: str = Field(default="", max_length=500)
    verification_status: Literal[
        "clinician_verified",
        "document_extracted",
        "patient_reported",
        "caregiver_reported",
        "awaiting_review",
    ] = "document_extracted"
    encounter_id: str | None = Field(default=None, max_length=64)
    evidence_title: str = Field(default="", max_length=120)
    evidence_excerpt: str = Field(default="", max_length=1200)
    evidence_document_name: str = Field(default="Clinical record", max_length=200)
    evidence_page_ref: str = Field(default="Lab result", max_length=80)
    source_type: Literal["discharge_document", "clinician_note", "patient_report", "caregiver_report", "system_demo"] = "clinician_note"

    @model_validator(mode="after")
    def validate_value(self) -> "CreateLabResultRequest":
        if self.value_numeric is None and not self.value_text.strip():
            raise ValueError("Provide either value_numeric or value_text.")
        # never infer units or reference ranges; allow empty
        return self


class CreateEncounterRequest(StrictModel):
    encounter_type: str = Field(min_length=2, max_length=80)
    occurred_at: str = Field(min_length=10, max_length=40)
    ended_at: str | None = Field(default=None, max_length=40)
    facility: str = Field(default="", max_length=160)
    provider_name: str = Field(default="", max_length=120)
    provider_specialty: str = Field(default="", max_length=120)
    reason: str = Field(default="", max_length=300)
    summary: str = Field(min_length=3, max_length=4000)
    discharge_instructions: str = Field(default="", max_length=4000)
    follow_up_plan: str = Field(default="", max_length=2000)
    source_document: str = Field(default="", max_length=200)
    verification_status: Literal[
        "clinician_verified",
        "document_extracted",
        "patient_reported",
        "awaiting_review",
    ] = "document_extracted"
    evidence_title: str = Field(default="", max_length=120)
    evidence_excerpt: str = Field(default="", max_length=1200)
    evidence_document_name: str = Field(default="Clinical encounter record", max_length=200)
    evidence_page_ref: str = Field(default="Encounter", max_length=80)
    source_type: Literal["discharge_document", "clinician_note", "patient_report", "system_demo"] = "clinician_note"



class DocumentReviewRequest(StrictModel):
    action: Literal["verify", "reject"]
    note: str = Field(default="", max_length=2000)
    corrected_value_text: str | None = Field(default=None, max_length=2000)


class DocumentExplainRequest(StrictModel):
    mode: Literal["report", "prescription"] = "report"
    force: bool = False


class AssistantAskRequest(StrictModel):
    patient_id: str = Field(min_length=3, max_length=64)
    question: str = Field(min_length=3, max_length=500)
    conversation_id: str | None = Field(default=None, max_length=64)
    document_id: str | None = Field(default=None, max_length=64)

    @field_validator("question")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank.")
        return value.strip()


class GuidanceRequest(StrictModel):
    guidance_type: Literal[
        "document_explanation",
        "medical_history_summary",
        "lab_findings",
        "discharge_instructions",
        "precautions",
        "medication_instructions",
        "follow_up",
        "clinician_questions",
        "historical_comparison",
        "general",
    ] = "general"
    question: str = Field(default="", max_length=1000)
    document_id: str | None = Field(default=None, max_length=64)
