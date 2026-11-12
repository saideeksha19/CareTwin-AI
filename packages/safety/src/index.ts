import type { VerificationStatus } from "@caretwin/contracts";

/**
 * This package contains presentation-side safety rules only.
 * Authoritative authorization, provenance and monitoring decisions live in
 * apps/api/app/safety and are enforced at service boundaries.
 */

export const SYNTHETIC_DISCLAIMER =
  "Synthetic demo patient. No real patient information. Not for clinical use.";

export const CLINICAL_DISCLAIMER =
  "CareTwin AI organizes documented and reported recovery information. It does not diagnose conditions, prescribe treatment, or replace clinical judgment. In an emergency, contact local emergency services.";

export const AI_BOUNDARY_NOTE =
  "External models may explain recorded information only. Deterministic rules and human permissions govern alerts, verification, and record changes.";

export const SAFE_EMERGENCY_COPY =
  "If symptoms feel severe or rapidly worsening, contact emergency services or your care team now. Do not wait for app-based review.";

export function isClinicianVerified(status: VerificationStatus): boolean {
  return status === "clinician_verified";
}

export function mustShowReviewBadge(status: VerificationStatus): boolean {
  return (
    status === "awaiting_review" ||
    status === "document_extracted" ||
    status === "ai_generated" ||
    status === "rejected"
  );
}

export function provenanceWeight(status: VerificationStatus): number {
  switch (status) {
    case "clinician_verified":
      return 5;
    case "document_extracted":
      return 3;
    case "patient_reported":
    case "caregiver_reported":
      return 2;
    case "awaiting_review":
      return 1;
    case "ai_generated":
      return 0.5;
    case "simulated_demo":
      return 0.5;
    case "rejected":
      return 0;
  }
}

export function permissionLabel(scope: string): string {
  const labels: Record<string, string> = {
    "twin:read": "View recovery twin",
    "timeline:read": "View recovery timeline",
    "schedule:read": "View medication & follow-up schedule",
    "observations:write": "Submit caregiver observations",
    "alerts:read": "View safety alerts",
    "consents:read": "View consent records",
    "summary:read": "View clinical summary",
    "rules:write": "Configure monitoring rules",
    "medications:verify": "Verify extracted medications",
  };
  return labels[scope] ?? scope;
}
