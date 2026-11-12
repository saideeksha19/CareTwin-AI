import type {
  AlertSeverity,
  RecoveryEventType,
  TwinStatus,
  UserRole,
  VerificationStatus,
} from "@caretwin/contracts";

export const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  clinician_verified: "Clinician verified",
  document_extracted: "Extracted from document",
  patient_reported: "Patient reported",
  caregiver_reported: "Caregiver reported",
  ai_generated: "AI generated",
  simulated_demo: "Simulated demo data",
  awaiting_review: "Awaiting review",
  rejected: "Rejected",
};

export function verificationLabel(status: VerificationStatus): string {
  return VERIFICATION_LABELS[status] ?? status;
}

export type VerificationTone = "verified" | "review" | "reported" | "ai" | "neutral";

export function verificationTone(status: VerificationStatus): VerificationTone {
  switch (status) {
    case "clinician_verified":
      return "verified";
    case "awaiting_review":
    case "document_extracted":
      return "review";
    case "patient_reported":
    case "caregiver_reported":
      return "reported";
    case "ai_generated":
      return "ai";
    default:
      return "neutral";
  }
}

export const EVENT_LABELS: Record<RecoveryEventType, string> = {
  discharge_recorded: "Discharge recorded",
  document_processed: "Document processed",
  instruction_verified: "Instruction verified",
  plan_created: "Recovery plan created",
  medication_started: "Medication recorded",
  milestone_completed: "Milestone completed",
  follow_up_scheduled: "Follow-up scheduled",
  checkin_submitted: "Patient check-in",
  observation_recorded: "Caregiver observation",
  safety_alert_raised: "Safety alert raised",
  alert_acknowledged: "Alert acknowledged",
  alert_resolved: "Alert resolved",
  alert_deduplicated: "Repeated alert match linked",
  consent_updated: "Consent updated",
  medication_verified: "Medication verified",
  twin_snapshot_created: "Twin snapshot captured",
  lab_result_recorded: "Lab result recorded",
  clinical_encounter_recorded: "Clinical encounter recorded",
  monitoring_sweep_completed: "Monitoring sweep",
};

export function eventTypeLabel(type: RecoveryEventType): string {
  return EVENT_LABELS[type] ?? type;
}

export function twinStatusLabel(status: TwinStatus): string {
  switch (status) {
    case "on_track":
      return "On track";
    case "needs_attention":
      return "Needs attention";
    case "urgent_review":
      return "Urgent review";
  }
}

export function twinStatusDescription(status: TwinStatus): string {
  switch (status) {
    case "on_track":
      return "No open urgent safety alerts. Milestones and follow-ups are visible and traceable.";
    case "needs_attention":
      return "One or more open concerns require human review. This is not a diagnosis.";
    case "urgent_review":
      return "A clinician-configured rule produced a critical alert. Human review is required.";
  }
}

export function roleLabel(role: UserRole): string {
  switch (role) {
    case "patient":
      return "Patient";
    case "caregiver":
      return "Caregiver";
    case "clinician":
      return "Clinician";
  }
}

export function roleHomePath(role: UserRole): string {
  if (role === "caregiver") return "/workspace/caregiver";
  if (role === "clinician") return "/workspace/clinician";
  return "/workspace";
}

export const ALERT_RANK: Record<AlertSeverity, number> = {
  info: 0,
  moderate: 1,
  urgent: 2,
  critical: 3,
};

export function sortAlertsBySeverity<T extends { severity: AlertSeverity; createdAt: string }>(
  alerts: T[],
): T[] {
  return [...alerts].sort((a, b) => {
    const rank = ALERT_RANK[b.severity] - ALERT_RANK[a.severity];
    if (rank !== 0) return rank;
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });
}

export function countOpenBySeverity(
  alerts: { severity: AlertSeverity; status: string }[],
): Record<AlertSeverity, number> {
  const counts: Record<AlertSeverity, number> = {
    info: 0,
    moderate: 0,
    urgent: 0,
    critical: 0,
  };
  for (const alert of alerts) {
    if (alert.status === "open") counts[alert.severity] += 1;
  }
  return counts;
}

export function eventTone(type: RecoveryEventType): string {
  if (
    type === "safety_alert_raised" ||
    type === "alert_acknowledged" ||
    type === "alert_resolved" ||
    type === "alert_deduplicated"
  )
    return "alert";
  if (type === "checkin_submitted") return "patient";
  if (type === "observation_recorded") return "caregiver";
  if (type === "instruction_verified" || type === "medication_verified") return "verified";
  if (type === "document_processed") return "document";
  return "neutral";
}
