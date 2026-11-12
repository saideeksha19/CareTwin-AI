import { API_BASE_URL, ApiClientError, apiRequest } from "@/lib/api";
import { AUTH_MODE, authHeaders } from "@/lib/auth";
import type { ApiErrorBody } from "@caretwin/contracts";

export type DocumentSummary = {
  id: string;
  patientId: string;
  originalFilename: string;
  documentType: string;
  mimeType: string;
  fileExtension: string;
  fileSizeBytes: number;
  contentHash: string;
  uploadStatus: string;
  processingStatus: string;
  extractionStatus: string;
  extractionMethod: string;
  extractionError: string;
  pageCount: number | null;
  isDuplicateOf: string | null;
  uploadedAt: string;
  processedAt: string | null;
  uploadedBy: { id: string | null; name: string; role: string };
};

export type DocumentPage = {
  id: string;
  documentId: string;
  pageNumber: number;
  extractionMethod: string;
  status: string;
  error: string;
  textContent: string;
};

export type DocumentExtraction = {
  id: string;
  documentId: string;
  patientId: string;
  itemType: string;
  label: string;
  valueText: string;
  valueNumeric: number | null;
  unit: string;
  referenceRange: string;
  abnormalFlag: string;
  pageNumber: number | null;
  sourceText: string;
  extractionStatus: string;
  verificationStatus: "unverified" | "verified" | "rejected" | string;
  confidenceNote: string;
  evidenceId: string | null;
  verifiedBy: { id: string | null; name: string; at: string | null };
  rejectedBy: { id: string | null; name: string; at: string | null };
  reviewNote: string;
  correctedValueText: string | null;
  original: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
};

export type DocumentDetail = DocumentSummary & {
  pages: DocumentPage[];
  extractions: DocumentExtraction[];
};

export type GuidanceCitation = {
  type: string;
  id: string;
  documentId: string | null;
  documentName: string | null;
  pageNumber: number | null;
  label: string;
  verificationStatus: string;
};

export type GuidanceRecord = {
  id: string;
  patientId: string;
  guidanceType: string;
  mode: string;
  aiState: string;
  model: string;
  question: string;
  answer: string;
  citations: GuidanceCitation[];
  evidence: Record<string, unknown>;
  grounded: boolean;
  requestedBy: { name: string | null; role: string | null };
  createdAt: string;
};

export type GuidanceResult = {
  id: string;
  patientId: string;
  guidanceType: string;
  mode: string;
  aiState: string;
  model: string;
  grounded: boolean;
  answer: string;
  citations: GuidanceCitation[];
  evidenceSummary: {
    documentCount?: number;
    verifiedExtractionCount?: number;
    unverifiedExtractionCount?: number;
  };
  unverifiedItemsExcludedFromConfirmation: number;
  createdAt: string;
};

/** Must match the backend allow-list in apps/api/app/services/document_storage.py. */
export const DOCUMENT_TYPES: Array<{ value: string; label: string; group: string }> = [
  { value: "blood_test_report", label: "Blood test report", group: "Laboratory" },
  { value: "prescription", label: "Prescription", group: "Laboratory" },
  { value: "mri_ct_report", label: "MRI / CT report", group: "Imaging" },
  { value: "xray_report", label: "X-ray report", group: "Imaging" },
  { value: "ultrasound_report", label: "Ultrasound report", group: "Imaging" },
  { value: "discharge_summary", label: "Discharge summary", group: "Clinical notes" },
  { value: "consultation_report", label: "Consultation note", group: "Clinical notes" },
  { value: "medical_history", label: "Previous medical record", group: "Clinical notes" },
  { value: "follow_up_report", label: "Follow-up report", group: "Clinical notes" },
  { value: "pdf_report", label: "Other report (PDF)", group: "Other" },
  { value: "medical_report_image", label: "Scanned image report", group: "Other" },
  { value: "other_medical_document", label: "Other medical document", group: "Other" },
];

export function documentTypeLabel(value: string | null | undefined) {
  return (
    DOCUMENT_TYPES.find((item) => item.value === value)?.label ??
    (value ? value.replaceAll("_", " ") : "Document")
  );
}

export const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export function formatValueWithUnit(value: string | null | undefined, unit: string | null | undefined) {
  const text = (value ?? "").trim();
  const suffix = (unit ?? "").trim();
  if (!suffix) return text || "—";
  if (!text) return suffix;
  return text.toLowerCase().includes(suffix.toLowerCase()) ? text : `${text} ${suffix}`;
}

export function formatBytes(bytes: number) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type DocumentDetailPayload = {
  document: DocumentSummary;
  pages: DocumentPage[];
  extractions: DocumentExtraction[];
};

export function uploadDocument({
  patientId,
  userId,
  file,
  documentType,
  onProgress,
}: {
  patientId: string;
  userId: string;
  file: File;
  documentType: string;
  onProgress?: (percent: number) => void;
}): Promise<{ document: DocumentSummary; duplicate?: boolean }> {
  const form = new FormData();
  form.append("file", file);
  form.append("documentType", documentType);

  // XMLHttpRequest is used only to expose real upload progress events.
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/patients/${patientId}/documents`);
    request.withCredentials = AUTH_MODE === "production";
    if (AUTH_MODE === "demo") {
      request.setRequestHeader("X-Demo-User-Id", userId);
    }
    for (const [header, value] of Object.entries(authHeaders())) {
      request.setRequestHeader(header, value);
    }
    request.setRequestHeader("Accept", "application/json");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    request.addEventListener("error", () => {
      reject(
        new ApiClientError(
          0,
          "network_error",
          "The CareTwin backend is not reachable. Start the FastAPI server and retry.",
        ),
      );
    });
    request.addEventListener("load", () => {
      let body: DocumentDetailPayload | ApiErrorBody | null = null;
      try {
        body = JSON.parse(request.responseText) as DocumentDetailPayload | ApiErrorBody;
      } catch {
        body = null;
      }
      if (request.status < 200 || request.status >= 300) {
        const errorBody = body as ApiErrorBody | null;
        reject(
          new ApiClientError(
            request.status,
            errorBody?.error?.code ?? "upload_failed",
            errorBody?.error?.message ?? `Upload failed with status ${request.status}.`,
            errorBody?.error?.details,
            errorBody?.error?.requestId,
          ),
        );
        return;
      }
      if (!body || !("document" in body)) {
        reject(new ApiClientError(request.status, "invalid_response", "The upload response was not readable."));
        return;
      }
      onProgress?.(100);
      const payload = body as DocumentDetailPayload;
      resolve({
        document: payload.document,
        duplicate: Boolean(payload.document.isDuplicateOf),
      });
    });
    request.send(form);
  });
}

export function documentFileUrl(patientId: string, documentId: string) {
  return `${API_BASE_URL}/patients/${patientId}/documents/${documentId}/file`;
}

/** Fetch the stored original with demo-user authorization, as a displayable object URL. */
export async function fetchDocumentFileBlob(
  patientId: string,
  documentId: string,
  userId?: string | null,
) {
  const response = await fetch(documentFileUrl(patientId, documentId), {
    credentials: AUTH_MODE === "production" ? "include" : "same-origin",
    headers: {
      ...(AUTH_MODE === "demo" && userId ? { "X-Demo-User-Id": userId } : {}),
      ...authHeaders(),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ApiClientError(
      response.status,
      "file_unavailable",
      `Original file could not be loaded (status ${response.status}).`,
    );
  }
  return URL.createObjectURL(await response.blob());
}

export type AnalysisValue = {
  id: string;
  itemType: string;
  label: string;
  value: string;
  valueNumeric: number | null;
  unit: string;
  referenceRange: string;
  pageNumber: number | null;
  sourceText: string;
  verificationStatus: string;
  confidenceNote: string;
  plainExplanation: string;
  canonicalTest: string | null;
  kind?: string;
};

export type ReviewFlag = {
  label: string;
  value: string;
  unit: string;
  referenceRange: string;
  pageNumber: number | null;
  reason: string;
  verificationStatus: string;
  sourceText: string;
};

export type PrescriptionMedicine = {
  name: string;
  dosage: string | null;
  frequency: string | null;
  timing: string | null;
  duration: string | null;
  instructions: string;
  clarificationNeeded: string[];
  confidence: string;
  pageNumber: number | null;
  sourceText: string;
  verificationStatus: string;
  plainExplanation: string;
};

export type PrescriptionResult = {
  documentId: string;
  documentName: string;
  medicines: PrescriptionMedicine[];
  medicineCount: number;
  prescriber: { name: string | null; registrationNumber: string | null; pageNumber: number | null; sourceText: string };
  prescriberStatus: string;
  unreadablePages: Array<{ pageNumber: number | null; status: string; detail: string }>;
  clarifications: string[];
  parseMode: string;
  safetyNote: string;
  generatedAt: string;
};

export type DocumentAnalysis = {
  documentId: string;
  patientId: string;
  documentType: string;
  documentTypeLabel: string;
  generatedAt: string;
  analysisMode: string;
  aiUsed: boolean;
  ai: { state: string; configured: boolean; model: string; message: string };
  summary: {
    headline: string;
    paragraph: string;
    pageCount: number;
    extractionStatus: string;
    extractionMethod: string;
    extractionError: string;
    extractedItemCount: number;
    verifiedItemCount: number;
    awaitingReviewCount: number;
    usedOcr: boolean;
    documentDates: string[];
  };
  keyInformation: AnalysisValue[];
  values: AnalysisValue[];
  terminology: Array<{ term: string; explanation: string; basis: string }>;
  findingsRequiringReview: ReviewFlag[];
  unreadableOrMissing: Array<{ scope: string; pageNumber: number | null; detail: string }>;
  questionsToAsk: Array<{ question: string; basis: string }>;
  prescription: null | {
    medicines: PrescriptionMedicine[];
    prescriber: { name: string | null; registrationNumber: string | null; pageNumber: number | null };
    clarifications: string[];
  };
  limits: string[];
};

export type ComparisonSide = {
  documentId: string;
  documentName: string | null;
  date: string;
  dateSource: string;
  value: number;
  valueText: string;
  referenceRange: string;
  pageNumber: number | null;
  verificationStatus: string;
};

export type ComparisonRow = {
  canonicalTest: string;
  label: string;
  explanation: string | null;
  unit: string;
  unitRaw: string;
  comparable: boolean;
  validityReasons: string[];
  previous: ComparisonSide;
  latest: ComparisonSide;
  difference: number;
  differencePercent: number | null;
  direction: string;
  verification: { previous: string; latest: string; bothVerified: boolean };
  interpretationNote: string;
};

export type ReportComparison = {
  patientId: string;
  generatedAt: string;
  documentCount: number;
  observationCount: number;
  comparisons: ComparisonRow[];
  insufficientHistory: Array<{ label: string; unit: string; reason: string }>;
  notComparable: Array<{ label: string; reason: string }>;
  unitMismatches: Array<{ label: string; units: string[]; reason: string }>;
  notes: string[];
};

export type AssistantCitation = {
  type: string;
  id: string;
  documentId: string | null;
  documentName: string | null;
  pageNumber: number | null;
  label: string;
  verificationStatus: string;
  quote: string;
};

export type AssistantAnswer = {
  id: string;
  conversationId: string;
  patientId: string;
  question: string;
  route: string;
  mode: string;
  aiState: string;
  aiConfigured: boolean;
  model: string;
  modelNote: string;
  facts: string[];
  explanation: string;
  uncertainty: string;
  followUpQuestions: string[];
  citations: AssistantCitation[];
  containsVerifiedFacts: boolean;
  createdAt: string;
};

export type AssistantRecord = {
  id: string;
  conversationId: string;
  question: string;
  answer: string;
  mode: string;
  aiState: string;
  uncertainty: string;
  followUpQuestions: string[];
  citations: AssistantCitation[];
  evidence: { route?: string; factCount?: number };
  requestedBy: { id: string | null; role: string | null };
  createdAt: string;
};

export function fetchDocumentAnalysis(patientId: string, documentId: string, userId?: string | null) {
  return apiRequest<DocumentAnalysis>(
    `/patients/${patientId}/documents/${documentId}/analysis`,
    { userId },
  );
}

export function fetchDocumentPrescription(patientId: string, documentId: string, userId?: string | null) {
  return apiRequest<PrescriptionResult>(
    `/patients/${patientId}/documents/${documentId}/prescription`,
    { userId },
  );
}

export function fetchReportComparison(patientId: string, userId?: string | null) {
  return apiRequest<ReportComparison>(`/patients/${patientId}/reports/comparison`, { userId });
}

export function askAssistant({
  patientId,
  userId,
  question,
  conversationId,
  documentId,
}: {
  patientId: string;
  userId: string;
  question: string;
  conversationId?: string | null;
  documentId?: string | null;
}) {
  return apiRequest<AssistantAnswer>(`/patients/${patientId}/assistant/ask`, {
    method: "POST",
    userId,
    body: {
      patientId,
      question,
      ...(conversationId ? { conversationId } : {}),
      ...(documentId ? { documentId } : {}),
    },
  });
}

export function fetchAssistantHistory(
  patientId: string,
  userId?: string | null,
  conversationId?: string | null,
) {
  const query = conversationId ? `?conversationId=${encodeURIComponent(conversationId)}` : "";
  return apiRequest<AssistantRecord[]>(`/patients/${patientId}/assistant/history${query}`, { userId });
}

export function reprocessDocument(patientId: string, documentId: string, userId: string) {
  return apiRequest<DocumentDetailPayload>(
    `/patients/${patientId}/documents/${documentId}/reprocess`,
    { method: "POST", userId, body: {} },
  );
}

export async function fetchDocumentDetail(
  patientId: string,
  documentId: string,
  userId?: string | null,
): Promise<DocumentDetail> {
  const payload = await apiRequest<DocumentDetailPayload>(
    `/patients/${patientId}/documents/${documentId}`,
    { userId },
  );
  return {
    ...payload.document,
    pages: payload.pages ?? [],
    extractions: payload.extractions ?? [],
  };
}

export async function reviewExtraction({
  patientId,
  documentId,
  extractionId,
  userId,
  action,
  note,
  correctedValueText,
}: {
  patientId: string;
  documentId: string;
  extractionId: string;
  userId: string;
  action: "verify" | "reject";
  note?: string;
  correctedValueText?: string | null;
}) {
  return apiRequest<unknown>(
    `/patients/${patientId}/documents/${documentId}/extractions/${extractionId}/review`,
    {
      method: "POST",
      userId,
      body: {
        action,
        note: note ?? "",
        ...(correctedValueText ? { correctedValueText } : {}),
      },
    },
  );
}

export function verificationTone(status: DocumentExtraction["verificationStatus"]) {
  if (status === "verified" || status === "clinician_verified") return "teal" as const;
  if (status === "rejected") return "rose" as const;
  return "amber" as const;
}

export function extractionStatusLabel(status: string | null | undefined) {
  const map: Record<string, string> = {
    unverified: "Unverified extraction",
    verified: "Clinician verified",
    rejected: "Rejected by clinician",
    clinician_verified: "Clinician verified",
    document_extracted: "Extracted — not verified",
    awaiting_review: "Awaiting review",
  };
  if (!status) return "Status unavailable";
  return map[status] ?? status.replaceAll("_", " ");
}

/* ------------------------------------------------------------------ AI layer */

export type AiStatus = {
  configured: boolean;
  provider: string;
  model: string;
  state: string;
  message: string;
  serverSideOnly: boolean;
  capabilities: {
    documentExplanation: boolean;
    prescriptionExplanation: boolean;
    conversationalAssistant: boolean;
    deterministicFallback: boolean;
  };
  limits: {
    maxInputChars: number;
    maxOutputTokens: number;
    requestsPerHour: number;
    timeoutSeconds: number;
  };
  metrics: {
    lastLatencyMs: number | null;
    requests: number;
    failures: number;
    lastError: string | null;
    lastSuccessAt: string | null;
  };
};

export type AiHealth = {
  configured: boolean;
  reachable: boolean;
  state: string;
  latencyMs?: number;
  message: string;
  checkedAt?: string;
};

export type ExplanationValidationFailure = { code: string; detail: string };

export type ExplanationResultRow = {
  label: string;
  valueText: string;
  unit: string;
  referenceRangePrinted: string;
  pageNumber: number | null;
  explanation: string;
  citationIds?: string[];
};

export type DocumentExplanation = {
  available: boolean;
  id?: string;
  documentId: string;
  documentName: string;
  documentType?: string;
  mode: "report" | "prescription" | string;
  analysisMode: string;
  aiUsed: boolean;
  model?: string;
  provider?: string;
  generatedAt: string;
  summary?: string;
  terminology?: Array<{ term: string; explanation: string; citationIds?: string[] }>;
  results?: ExplanationResultRow[];
  interpretation?: string;
  findingsForClinicianReview?: string[];
  missingOrAmbiguous?: string[];
  questionsForDoctor?: string[];
  generalEducation?: string[];
  limitations?: string[];
  citations?: string[];
  uncertainty?: string;
  validation?: { ok: boolean; failures: ExplanationValidationFailure[] };
  meta?: { model?: string; latencyMs?: number; promptTokens?: number; outputTokens?: number };
  injectionSignals?: string[];
  cached?: boolean;
  reason?: string;
};

export function fetchAiStatus() {
  return apiRequest<AiStatus>("/ai/status");
}

export function fetchAiHealth() {
  return apiRequest<AiHealth>("/ai/health");
}

export async function fetchDocumentExplanation(
  patientId: string,
  documentId: string,
  mode: "report" | "prescription",
  userId?: string | null,
): Promise<DocumentExplanation> {
  return apiRequest<DocumentExplanation>(
    `/patients/${patientId}/documents/${documentId}/explanation?mode=${mode}`,
    { userId },
  );
}

export function requestDocumentExplanation({
  patientId,
  documentId,
  mode,
  userId,
  force,
}: {
  patientId: string;
  documentId: string;
  mode: "report" | "prescription";
  userId: string;
  force: boolean;
}) {
  return apiRequest<DocumentExplanation>(
    `/patients/${patientId}/documents/${documentId}/explain`,
    { method: "POST", userId, body: { mode, force } },
  );
}
