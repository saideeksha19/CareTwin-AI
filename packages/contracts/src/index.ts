export type UserRole = "patient" | "caregiver" | "clinician";

export type VerificationStatus =
  | "clinician_verified"
  | "document_extracted"
  | "patient_reported"
  | "caregiver_reported"
  | "ai_generated"
  | "simulated_demo"
  | "awaiting_review"
  | "rejected";

export type SourceType =
  | "discharge_document"
  | "patient_report"
  | "caregiver_report"
  | "clinician_note"
  | "system_demo"
  | "monitoring_rule"
  | "ai_output";

export type RecoveryEventType =
  | "discharge_recorded"
  | "document_processed"
  | "instruction_verified"
  | "plan_created"
  | "medication_started"
  | "milestone_completed"
  | "follow_up_scheduled"
  | "checkin_submitted"
  | "observation_recorded"
  | "safety_alert_raised"
  | "alert_acknowledged"
  | "alert_resolved"
  | "alert_deduplicated"
  | "consent_updated"
  | "medication_verified"
  | "twin_snapshot_created"
  | "lab_result_recorded"
  | "clinical_encounter_recorded"
  | "monitoring_sweep_completed";

export type TwinStatus = "on_track" | "needs_attention" | "urgent_review";
export type AlertSeverity = "info" | "moderate" | "urgent" | "critical";
export type AlertStatus = "open" | "acknowledged" | "resolved";
export type MilestoneStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "overdue"
  | "not_applicable";
export type ConsentStatus = "granted" | "revoked" | "expired";
export type ObservationCategory =
  | "general"
  | "mobility"
  | "appetite"
  | "medication_support"
  | "symptom"
  | "appointment";

export interface DemoUser {
  id: string;
  name: string;
  role: UserRole;
  title: string;
  organization: string;
  initials: string;
  patientId: string;
  linkedPatientName: string;
  consentStatus?: "granted" | "revoked" | "not_required";
  scopes?: string[];
}

export interface DemoSession {
  users: DemoUser[];
  patient: {
    id: string;
    fullName: string;
    synthetic: true;
  };
  disclaimer: string;
}

export interface Provenance {
  verificationStatus: VerificationStatus;
  sourceType: SourceType;
  sourceId?: string | null;
  sourceLabel?: string | null;
  actorName?: string | null;
  actorRole?: UserRole | "system";
  recordedAt?: string | null;
  synthetic: boolean;
  extractedByAi: boolean;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
}

export interface PatientProfile {
  id: string;
  mrn: string;
  fullName: string;
  preferredName: string;
  dateOfBirth: string;
  age: number;
  sex: string;
  primaryLanguage: string;
  condition: string;
  dischargedOn: string;
  postDischargeDay: number;
  synthetic: boolean;
}

export interface RecoveryPlan {
  id: string;
  title: string;
  summary: string;
  startDate: string;
  targetEndDate: string;
  status: string;
}

export interface Milestone {
  id: string;
  title: string;
  description: string;
  dueDate: string;
  status: MilestoneStatus;
  completedAt?: string | null;
  verificationStatus: VerificationStatus;
  evidence?: EvidenceSource | null;
}

export interface MedicationInstruction {
  id: string;
  name: string;
  dosage: string;
  route: string;
  frequency: string;
  duration: string;
  instructions: string;
  status: string;
  verificationStatus: VerificationStatus;
  prescribedBy: string;
  evidence?: EvidenceSource | null;
}

export interface FollowUp {
  id: string;
  title: string;
  clinicianName: string;
  specialty: string;
  scheduledFor: string;
  location: string;
  status: string;
  notes: string;
  verificationStatus: VerificationStatus;
  evidence?: EvidenceSource | null;
}

export interface SymptomReport {
  code: string;
  label: string;
  severity: number;
  notes: string;
}

export interface PatientCheckIn {
  id: string;
  submittedAt: string;
  submittedBy: string;
  overallFeeling: string;
  painScore: number;
  temperatureC: number | null;
  breathlessnessScore: number;
  adherence: string;
  missedDoses: number;
  notes: string;
  symptoms: SymptomReport[];
  verificationStatus: VerificationStatus;
  evidenceId?: string | null;
}

export interface CaregiverObservation {
  id: string;
  observedAt: string;
  caregiverName: string;
  category: ObservationCategory;
  note: string;
  verificationStatus: VerificationStatus;
  evidenceId?: string | null;
}

export interface SafetyAlert {
  id: string;
  ruleId: string;
  severity: AlertSeverity;
  category: string;
  title: string;
  rationale: string;
  status: AlertStatus;
  createdAt: string;
  acknowledgedBy?: string | null;
  acknowledgedAt?: string | null;
  resolvedBy?: string | null;
  resolvedAt?: string | null;
  resolutionNote?: string | null;
  evidenceId?: string | null;
  evidence?: EvidenceSource | null;
}

export interface ConsentRecord {
  id: string;
  patientId: string;
  granteeUserId: string;
  granteeName: string;
  granteeRelationship: string;
  scopes: string[];
  status: ConsentStatus;
  grantedAt: string;
  updatedAt: string;
}

export interface EvidenceSource {
  id: string;
  sourceType: SourceType;
  title: string;
  documentName: string;
  pageRef: string;
  excerpt: string;
  synthetic: boolean;
  verificationStatus: VerificationStatus;
  extractedByAi: boolean;
  capturedAt: string;
}

export interface RecoveryEvent {
  id: string;
  patientId: string;
  eventType: RecoveryEventType;
  occurredAt: string;
  recordedAt: string;
  actorName: string;
  actorRole: UserRole | "system";
  sourceType: SourceType;
  evidenceId?: string | null;
  verificationStatus: VerificationStatus;
  title: string;
  description: string;
  payload: Record<string, unknown>;
  reviewStatus: string;
  evidence?: EvidenceSource | null;
}

export interface TwinSnapshotMeta {
  id: string;
  version: number;
  reason: string;
  createdAt: string;
}

export interface TwinSnapshot extends TwinSnapshotMeta {
  snapshot: Record<string, unknown>;
}

export interface DataQuality {
  totalEvidence: number;
  verifiedEvidence: number;
  awaitingReview: number;
  unverifiedMedicationInstructions: number;
  sourcesByType: Record<string, number>;
}

export interface RecoveryTwin {
  id: string;
  patient: PatientProfile;
  version: number;
  status: TwinStatus;
  statusReason: string;
  updatedAt: string;
  progress: {
    completed: number;
    total: number;
    ratio: number;
  };
  plan: RecoveryPlan;
  milestones: Milestone[];
  medications: MedicationInstruction[];
  followUps: FollowUp[];
  recentCheckIns: PatientCheckIn[];
  observations: CaregiverObservation[];
  openAlerts: SafetyAlert[];
  evidence: EvidenceSource[];
  nextFollowUp: FollowUp | null;
  dataQuality: DataQuality;
  visibility: {
    role: UserRole;
    filtered: boolean;
    note: string;
  };
  syntheticDisclaimer: string;
}

export interface TimelineResponse {
  patientId: string;
  generatedAt: string;
  total: number;
  events: RecoveryEvent[];
}

export interface AuditEvent {
  id: string;
  action: string;
  entityType: string;
  entityId: string;
  actorName: string;
  actorRole: UserRole | "system";
  outcome: string;
  details: Record<string, unknown>;
  createdAt: string;
}

export interface SafetyCheck {
  code: string;
  label: string;
  passed: boolean;
  detail: string;
}

export interface SafetyDecision {
  id: string;
  patientId: string;
  operation: string;
  outcome: "allowed" | "rejected" | "allowed_with_alerts";
  checks: SafetyCheck[];
  actorName: string;
  actorRole: UserRole | "system";
  createdAt: string;
}

export type AgentMaturity =
  | "working_deterministic"
  | "working_permissions"
  | "architecturally_prepared"
  | "requires_ai_configuration";

export interface AgentInfo {
  id: string;
  name: string;
  responsibility: string;
  phase1Status: AgentMaturity;
  statusLabel: string;
  permissions: string[];
  boundaries: string[];
  interfaces: string[];
}

export interface AiStatus {
  configured: boolean;
  provider: string;
  model: string;
  state: "not_configured" | "ready" | "error";
  message: string;
  groundedContextReady: boolean;
  serverSideOnly: boolean;
}

export interface ClinicalSummarySection {
  title: string;
  finding: string;
  evidenceRefs: string[];
}

export interface ClinicalSummary {
  patientId: string;
  generatedAt: string;
  mode: "deterministic";
  sections: ClinicalSummarySection[];
  safetyNotes: string[];
}

export interface MonitoringRule {
  id: string;
  code: string;
  name: string;
  description: string;
  kind: string;
  threshold: number;
  severity: AlertSeverity;
  enabled: boolean;
  updatedAt: string;
  configuredBy: string;
}

export interface CheckinSymptomInput {
  code: string;
  label: string;
  severity: number;
}

export interface CreateCheckinRequest {
  overallFeeling: "better" | "same" | "worse";
  painScore: number;
  temperatureC: number | null;
  breathlessnessScore: number;
  adherence: "all" | "missed_one" | "missed_multiple";
  missedDoses: number;
  symptoms: CheckinSymptomInput[];
  notes: string;
}

export interface CheckinResult {
  checkIn: PatientCheckIn;
  eventId: string;
  alerts: SafetyAlert[];
  deduplicatedAlerts: SafetyAlert[];
  safetyDecision: SafetyDecision;
  twinVersion: number;
}

export interface CreateObservationRequest {
  category: ObservationCategory;
  note: string;
}

export interface ObservationResult {
  observation: CaregiverObservation;
  eventId: string;
  safetyDecision: SafetyDecision;
}

export interface MonitoringSweepResult {
  evaluatedAt: string;
  alertsCreated: SafetyAlert[];
  rulesEvaluated: number;
  checkinGapHours: number | null;
  message: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    requestId?: string;
  };
}

export interface AiExplainRequest {
  patientId: string;
  question: string;
}

export interface AiExplanation {
  answer: string;
  citations: string[];
  uncertainty: string;
  mode: "external_model";
  provider: string;
  model: string;
}
