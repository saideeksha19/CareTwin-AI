"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileSearch,
  FileText,
  FileWarning,
  Loader2,
  Pill,
  RefreshCw,
  ScanLine,
  Upload,
  XCircle,
} from "lucide-react";
import { formatDateTime, formatRelative } from "@caretwin/shared";
import { ApiClientError, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/fields";
import {
  EmptyState,
  ErrorState,
  InlineMessage,
  LoadingBlock,
  PageSkeleton,
  SafetyFooterNote,
} from "@/components/ui/feedback";
import { Tabs } from "@/components/ui/tabs";
import {
  DOCUMENT_TYPES,
  MAX_UPLOAD_BYTES,
  askAssistant,
  documentTypeLabel,
  extractionStatusLabel,
  fetchDocumentAnalysis,
  fetchDocumentDetail,
  fetchDocumentFileBlob,
  fetchDocumentPrescription,
  formatBytes,
  formatValueWithUnit,
  reprocessDocument,
  reviewExtraction,
  uploadDocument,
  type AssistantAnswer,
  type DocumentAnalysis,
  type DocumentDetail,
  type DocumentExtraction,
  type DocumentSummary,
  type PrescriptionResult,
} from "@/lib/documents";

type DetailTab = "analysis" | "prescription" | "extracted" | "source";

const statusTone = (status: string) =>
  status === "completed"
    ? ("teal" as const)
    : status === "pending" || status === "processing"
      ? ("blue" as const)
      : ("amber" as const);

const ACCEPTED = ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,application/pdf,image/png,image/jpeg,image/tiff,image/webp";

export default function DocumentsPage() {
  const { patientId, selectedUser } = useSession();
  const listState = useApi<DocumentSummary[]>(
    patientId ? `/patients/${patientId}/documents` : null,
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<unknown>(null);

  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("blood_test_report");
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [tab, setTab] = useState<DetailTab>("analysis");
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<unknown>(null);
  const [prescription, setPrescription] = useState<PrescriptionResult | null>(null);
  const [prescriptionLoading, setPrescriptionLoading] = useState(false);
  const [prescriptionError, setPrescriptionError] = useState<unknown>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reprocessing, setReprocessing] = useState(false);
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [assistantAnswer, setAssistantAnswer] = useState<AssistantAnswer | null>(null);
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [sourcePage, setSourcePage] = useState<number | null>(null);

  const loadDetail = useCallback(
    async (documentId: string) => {
      if (!patientId) return;
      setDetailLoading(true);
      setDetailError(null);
      try {
        setDetail(await fetchDocumentDetail(patientId, documentId, selectedUser?.id));
      } catch (error) {
        setDetail(null);
        setDetailError(error);
      } finally {
        setDetailLoading(false);
      }
    },
    [patientId, selectedUser?.id],
  );

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  useEffect(() => {
    if (!selectedId && listState.data?.length) setSelectedId(listState.data[0].id);
  }, [listState.data, selectedId]);

  // Reset per-document panels when a different document is opened.
  useEffect(() => {
    setAnalysis(null);
    setPrescription(null);
    setAssistantAnswer(null);
    setAssistantError(null);
    setReviewError(null);
    setSourcePage(null);
    setTab("analysis");
  }, [selectedId]);

  const isPrescriptionDoc = useMemo(
    () =>
      detail?.documentType === "prescription" ||
      Boolean(detail?.extractions.some((item) => item.itemType === "medication_mention")),
    [detail],
  );

  useEffect(() => {
    if (!selectedId || !patientId || tab !== "analysis" || analysis) return;
    let cancelled = false;
    setAnalysisLoading(true);
    setAnalysisError(null);
    fetchDocumentAnalysis(patientId, selectedId, selectedUser?.id)
      .then((payload) => {
        if (!cancelled) setAnalysis(payload);
      })
      .catch((error: unknown) => {
        if (!cancelled) setAnalysisError(error);
      })
      .finally(() => {
        if (!cancelled) setAnalysisLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, selectedId, patientId, analysis, selectedUser?.id]);

  useEffect(() => {
    if (!selectedId || !patientId || tab !== "prescription" || prescription) return;
    let cancelled = false;
    setPrescriptionLoading(true);
    setPrescriptionError(null);
    fetchDocumentPrescription(patientId, selectedId, selectedUser?.id)
      .then((payload) => {
        if (!cancelled) setPrescription(payload);
      })
      .catch((error: unknown) => {
        if (!cancelled) setPrescriptionError(error);
      })
      .finally(() => {
        if (!cancelled) setPrescriptionLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, selectedId, patientId, prescription, selectedUser?.id]);

  // The original file needs an authorization header, so it is fetched as a blob.
  useEffect(() => {
    if (!selectedId || !patientId || tab !== "source") return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setPreviewError(null);
    fetchDocumentFileBlob(patientId, selectedId, selectedUser?.id)
      .then((url) => {
        objectUrl = url;
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        setPreviewUrl(url);
      })
      .catch((error: unknown) => {
        if (!cancelled) setPreviewError(errorMessage(error));
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setPreviewUrl(null);
    };
  }, [tab, selectedId, patientId, selectedUser?.id]);

  if (!selectedUser) return <PageSkeleton />;

  const openSourcePage = (pageNumber: number | null) => {
    setSourcePage(pageNumber);
    setTab("source");
  };

  const documents = listState.data ?? [];
  const canUpload = Boolean(patientId && selectedUser);

  const pickFile = (candidate: File | null) => {
    setUploadError(null);
    setUploadSuccess(null);
    if (!candidate) {
      setFile(null);
      return;
    }
    if (candidate.size === 0) {
      setUploadError("That file is empty. Choose a PDF or image with content.");
      return;
    }
    if (candidate.size > MAX_UPLOAD_BYTES) {
      setUploadError(
        `${candidate.name} is ${formatBytes(candidate.size)}. The maximum accepted size is ${formatBytes(
          MAX_UPLOAD_BYTES,
        )}.`,
      );
      return;
    }
    if (!/\.(pdf|png|jpe?g|tiff?|webp)$/i.test(candidate.name)) {
      setUploadError(
        `${candidate.name} is not a supported format. Upload a PDF, PNG, JPEG, TIFF or WebP file. DICOM image sets are not supported.`,
      );
      return;
    }
    setFile(candidate);
  };

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    setUploadError(null);
    setUploadSuccess(null);
    if (!patientId || !selectedUser) return;
    if (!file) {
      setUploadError("Choose a PDF or image file to upload.");
      return;
    }
    setUploading(true);
    setProgress(0);
    try {
      const result = await uploadDocument({
        patientId,
        userId: selectedUser.id,
        file,
        documentType,
        onProgress: setProgress,
      });
      const doc = result.document;
      setUploadSuccess(
        result.duplicate
          ? `${doc.originalFilename} was stored and flagged as a duplicate of an earlier upload. ${extractionStatusLabel(
              doc.extractionStatus,
            )}.`
          : `${doc.originalFilename} uploaded and processed · ${extractionStatusLabel(doc.extractionStatus)}.`,
      );
      setFile(null);
      setFileInputKey((key) => key + 1);
      listState.refresh();
      setSelectedId(doc.id);
    } catch (error) {
      setUploadError(errorMessage(error));
    } finally {
      setUploading(false);
    }
  };

  const handleReview = async (
    extraction: DocumentExtraction,
    action: "verify" | "reject",
  ) => {
    if (!patientId || !selectedId || !selectedUser) return;
    setReviewError(null);
    setReviewingId(extraction.id);
    try {
      await reviewExtraction({
        patientId,
        documentId: selectedId,
        extractionId: extraction.id,
        userId: selectedUser.id,
        action,
      });
      await loadDetail(selectedId);
      setAnalysis(null);
      setPrescription(null);
      listState.refresh();
    } catch (error) {
      setReviewError(errorMessage(error));
    } finally {
      setReviewingId(null);
    }
  };

  const handleReprocess = async () => {
    if (!patientId || !selectedId || !selectedUser) return;
    setReprocessing(true);
    setReviewError(null);
    try {
      await reprocessDocument(patientId, selectedId, selectedUser.id);
      await loadDetail(selectedId);
      setAnalysis(null);
      setPrescription(null);
      listState.refresh();
    } catch (error) {
      setReviewError(errorMessage(error));
    } finally {
      setReprocessing(false);
    }
  };

  const askAboutDocument = async (question: string) => {
    if (!patientId || !selectedUser || !selectedId) return;
    setAssistantBusy(true);
    setAssistantError(null);
    try {
      setAssistantAnswer(
        await askAssistant({
          patientId,
          userId: selectedUser.id,
          question,
          documentId: selectedId,
        }),
      );
    } catch (error) {
      setAssistantAnswer(null);
      setAssistantError(errorMessage(error));
    } finally {
      setAssistantBusy(false);
    }
  };

  if (listState.loading && !listState.data) return <PageSkeleton />;
  if (listState.error) {
    if (listState.error instanceof ApiClientError && listState.error.status === 403) {
      return (
        <div>
          <PageHeader
            eyebrow="Medical documents"
            title="Documents are not shared with this role"
          />
          <InlineMessage tone="warning" title="Consent boundary">
            The server denied access to this patient&rsquo;s documents. Caregiver visibility
            depends on an active consent scope covering the recovery twin.
          </InlineMessage>
        </div>
      );
    }
    return <ErrorState error={listState.error} onRetry={listState.refresh} />;
  }

  const failed =
    detail &&
    (detail.processingStatus === "error" ||
      detail.extractionStatus === "failed" ||
      detail.extractionStatus === "unavailable");

  return (
    <div>
      <PageHeader
        eyebrow="Medical documents"
        title="Document intelligence"
        description="Upload blood tests, prescriptions, imaging reports, discharge summaries and prior records. Digital text is extracted first; image-only pages are rendered and OCR'd. Everything extracted stays unverified until a clinician reviews it against the source page."
        actions={
          <Badge tone="amber">
            <FileWarning className="h-3 w-3" /> Extractions require review
          </Badge>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <SectionCard
            title="Upload a document"
            description="PDF, PNG, JPEG, TIFF or WebP · 15 MB max"
            icon={<Upload className="h-4 w-4" />}
          >
            <form onSubmit={handleUpload} className="space-y-3">
              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragActive(false);
                  if (!canUpload || uploading) return;
                  pickFile(event.dataTransfer.files?.[0] ?? null);
                }}
                className={
                  dragActive
                    ? "rounded-xl border-2 border-dashed border-care-300 bg-care-50 p-4 text-center"
                    : "rounded-xl border-2 border-dashed border-slate-300 bg-mist-50 p-4 text-center transition-colors"
                }
              >
                <input
                  ref={fileInputRef}
                  id="document-file"
                  key={fileInputKey}
                  type="file"
                  accept={ACCEPTED}
                  className="sr-only"
                  onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
                  disabled={!canUpload || uploading}
                />
                <FileText className="mx-auto h-5 w-5 text-care-700" />
                <p className="mt-2 break-all text-[0.7rem] font-semibold text-navy-800">
                  {file ? file.name : "Drag a report here, or choose a file"}
                </p>
                <p className="mt-0.5 text-[0.6rem] text-slate-500">
                  {file
                    ? `${formatBytes(file.size)} · ready to upload`
                    : "Scanned pages are OCR-extracted one page at a time."}
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="mt-2.5"
                  disabled={!canUpload || uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  Choose file
                </Button>
              </div>

              <Field label="Document category" htmlFor="document-type">
                <Select
                  id="document-type"
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value)}
                  disabled={!canUpload || uploading}
                >
                  {DOCUMENT_TYPES.map((item) => (
                    <option key={item.value} value={item.value} className="bg-white">
                      {item.group} · {item.label}
                    </option>
                  ))}
                </Select>
              </Field>

              {uploading && (
                <div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-care-500 transition-[width] duration-300"
                      style={{ width: `${Math.max(progress, 6)}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[0.6rem] text-slate-500">
                    {progress < 100
                      ? `Uploading ${progress}%…`
                      : "Upload complete · extracting text, running OCR where needed."}
                  </p>
                </div>
              )}

              <Button type="submit" size="sm" disabled={!canUpload || uploading || !file}>
                {uploading ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Processing…
                  </>
                ) : (
                  <>
                    <Upload className="h-3.5 w-3.5" /> Upload &amp; extract
                  </>
                )}
              </Button>
              {uploadError && (
                <InlineMessage tone="error" title="Upload rejected">
                  {uploadError}
                </InlineMessage>
              )}
              {uploadSuccess && (
                <InlineMessage tone="success" title="Upload processed">
                  {uploadSuccess}
                </InlineMessage>
              )}
            </form>
          </SectionCard>

          <SectionCard
            title={`Document history · ${documents.length}`}
            description="Newest first · original files preserved"
            icon={<FileText className="h-4 w-4" />}
          >
            {documents.length === 0 ? (
              <EmptyState
                title="No documents uploaded"
                description="Upload a blood test, prescription or discharge summary to create evidence."
              />
            ) : (
              <ul className="scrollbar-thin max-h-[32rem] space-y-1.5 overflow-y-auto pr-1">
                {documents.map((doc) => (
                  <li key={doc.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(doc.id)}
                      aria-current={selectedId === doc.id ? "true" : undefined}
                      className={
                        selectedId === doc.id
                          ? "w-full rounded-lg border border-care-200 bg-care-50 px-3 py-2.5 text-left"
                          : "w-full rounded-lg border border-transparent px-3 py-2.5 text-left transition-colors hover:border-slate-200 hover:bg-mist-100"
                      }
                    >
                      <span className="flex items-start justify-between gap-2">
                        <span className="min-w-0">
                          <span className="block truncate text-[0.72rem] font-semibold text-navy-900">
                            {doc.originalFilename}
                          </span>
                          <span className="mt-0.5 block truncate text-[0.58rem] text-slate-500">
                            {documentTypeLabel(doc.documentType)} ·{" "}
                            {formatRelative(doc.uploadedAt)} ·{" "}
                            {doc.pageCount
                              ? `${doc.pageCount} ${doc.pageCount === 1 ? "page" : "pages"}`
                              : "pages unknown"}
                          </span>
                        </span>
                        <Badge tone={statusTone(doc.extractionStatus)}>
                          {extractionStatusLabel(doc.extractionStatus)}
                        </Badge>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>

        <div className="min-w-0 space-y-4">
          {detailLoading && <LoadingBlock label="Loading document detail" />}
          {detailError !== null && (
            <ErrorState
              error={detailError}
              title="Unable to open this document"
              onRetry={() => selectedId && void loadDetail(selectedId)}
            />
          )}
          {!detailLoading && !detailError && !detail && (
            <EmptyState
              icon={<ScanLine className="h-4 w-4" />}
              title="Select a document"
              description="Open an upload to read its analysis, prescription details, extracted items and the original page."
            />
          )}

          {detail && !detailLoading && (
            <>
              <SectionCard
                title={detail.originalFilename}
                description={`${documentTypeLabel(detail.documentType)} · ${formatBytes(
                  detail.fileSizeBytes,
                )} · uploaded ${formatDateTime(detail.uploadedAt)} by ${
                  detail.uploadedBy.name || "unknown"
                }`}
                icon={<FileText className="h-4 w-4" />}
                action={
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone={statusTone(detail.extractionStatus)}>
                      {extractionStatusLabel(detail.extractionStatus)}
                    </Badge>
                    {failed && selectedUser.role !== "caregiver" && (
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={reprocessing}
                        onClick={() => void handleReprocess()}
                      >
                        {reprocessing ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                        Reprocess
                      </Button>
                    )}
                  </div>
                }
              >
                <dl className="grid grid-cols-2 gap-2 text-[0.66rem] sm:grid-cols-4">
                  {[
                    ["Pages", detail.pageCount ? String(detail.pageCount) : "—"],
                    ["Method", detail.extractionMethod || "—"],
                    ["Processed", detail.processedAt ? formatRelative(detail.processedAt) : "—"],
                    ["Duplicate", detail.isDuplicateOf ? "Flagged" : "No"],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg bg-mist-100 p-2">
                      <dt className="text-[0.52rem] uppercase tracking-[0.12em] text-slate-500">
                        {label}
                      </dt>
                      <dd className="mt-0.5 truncate font-medium text-navy-800">{value}</dd>
                    </div>
                  ))}
                </dl>
                {detail.isDuplicateOf && (
                  <InlineMessage tone="warning" className="mt-3">
                    This file matches an earlier upload and was flagged as a duplicate. The
                    original content is preserved.
                  </InlineMessage>
                )}
                {detail.extractionError && (
                  <InlineMessage
                    tone={failed ? "error" : "warning"}
                    title={failed ? "Processing failed" : "Extraction notes"}
                    className="mt-3"
                  >
                    {detail.extractionError}
                  </InlineMessage>
                )}
                {reviewError && (
                  <InlineMessage tone="error" className="mt-3">
                    {reviewError}
                  </InlineMessage>
                )}
              </SectionCard>

              <Tabs
                items={[
                  { value: "analysis", label: "Analysis" },
                  ...(isPrescriptionDoc
                    ? [{ value: "prescription" as DetailTab, label: "Prescription" }]
                    : []),
                  { value: "extracted", label: "Extracted items", count: detail.extractions.length },
                  { value: "source", label: "Original & pages" },
                ]}
                value={tab}
                onChange={setTab}
              />

              {tab === "analysis" && (
                <div className="space-y-4">
                  {analysisLoading && <LoadingBlock label="Building document analysis" />}
                  {analysisError !== null && (
                    <ErrorState
                      error={analysisError}
                      compact
                      onRetry={() => {
                        setAnalysis(null);
                        setAnalysisError(null);
                      }}
                    />
                  )}
                  {analysis && (
                    <>
                      <SectionCard
                        title="What this document contains"
                        description="Extraction only — not a clinical interpretation"
                        icon={<FileSearch className="h-4 w-4" />}
                        action={
                          <Badge tone={analysis.aiUsed ? "violet" : "slate"}>
                            {analysis.aiUsed ? "model assisted" : "deterministic extraction"}
                          </Badge>
                        }
                      >
                        <p className="text-[0.72rem] leading-relaxed text-slate-600">
                          {analysis.summary.paragraph}
                        </p>
                        <p className="mt-2 rounded-lg border border-slate-100 bg-mist-50 p-2.5 text-[0.64rem] leading-relaxed text-slate-500">
                          {analysis.ai.message} Model state:{" "}
                          <span className="font-mono">{analysis.ai.state}</span>.
                        </p>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-[0.64rem] sm:grid-cols-4">
                          {[
                            ["Extracted", String(analysis.summary.extractedItemCount)],
                            ["Verified", String(analysis.summary.verifiedItemCount)],
                            ["Awaiting review", String(analysis.summary.awaitingReviewCount)],
                            ["OCR used", analysis.summary.usedOcr ? "Yes" : "No"],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-lg bg-mist-100 p-2">
                              <p className="text-[0.52rem] uppercase tracking-[0.12em] text-slate-500">
                                {label}
                              </p>
                              <p className="mt-0.5 font-semibold text-navy-800">{value}</p>
                            </div>
                          ))}
                        </div>
                      </SectionCard>

                      {analysis.values.length > 0 && (
                        <SectionCard
                          title={`Reported values · ${analysis.values.length}`}
                          description="Values, units and ranges exactly as printed, with page references"
                          icon={<ClipboardList className="h-4 w-4" />}
                        >
                          <div className="scrollbar-thin w-full min-w-0 overflow-x-auto">
                            <table className="w-full min-w-[34rem] text-left text-[0.66rem]">
                              <thead>
                                <tr className="text-[0.55rem] uppercase tracking-[0.1em] text-slate-500">
                                  <th className="pb-1.5 pr-2 font-semibold">Test</th>
                                  <th className="pb-1.5 pr-2 font-semibold">Reported value</th>
                                  <th className="pb-1.5 pr-2 font-semibold">Reported range</th>
                                  <th className="pb-1.5 pr-2 font-semibold">Page</th>
                                  <th className="pb-1.5 font-semibold">Review</th>
                                </tr>
                              </thead>
                              <tbody>
                                {analysis.values.map((value) => (
                                  <tr key={value.id} className="border-t border-slate-100">
                                    <td className="py-1.5 pr-2 font-medium text-navy-800">
                                      {value.label}
                                    </td>
                                    <td className="py-1.5 pr-2 font-mono text-navy-900">
                                      {formatValueWithUnit(value.value, value.unit)}
                                    </td>
                                    <td className="py-1.5 pr-2 font-mono text-slate-500">
                                      {value.referenceRange || "not printed"}
                                    </td>
                                    <td className="py-1.5 pr-2 text-slate-500">
                                      {value.pageNumber ?? "?"}
                                    </td>
                                    <td className="py-1.5">
                                      <Badge
                                        tone={
                                          value.verificationStatus === "verified" ? "teal" : "amber"
                                        }
                                      >
                                        {value.verificationStatus === "verified"
                                          ? "verified"
                                          : "unverified"}
                                      </Badge>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </SectionCard>
                      )}

                      {analysis.findingsRequiringReview.length > 0 && (
                        <SectionCard
                          title={`Needs professional review · ${analysis.findingsRequiringReview.length}`}
                          description="Checks against the range printed on this report only"
                          icon={<AlertTriangle className="h-4 w-4" />}
                        >
                          <div className="space-y-2">
                            {analysis.findingsRequiringReview.map((flag, index) => (
                              <div
                                key={`${flag.label}-${index}`}
                                className="rounded-xl border border-amber-200 bg-amber-50 p-2.5"
                              >
                                <p className="text-[0.68rem] font-semibold text-amber-800">
                                  {flag.label} · {formatValueWithUnit(flag.value, flag.unit)}
                                </p>
                                <p className="mt-0.5 text-[0.62rem] leading-relaxed text-amber-700">
                                  {flag.reason}
                                </p>
                                {flag.sourceText && (
                                  <p className="mt-1 border-l border-amber-200 pl-2 text-[0.6rem] italic text-amber-600">
                                    Page {flag.pageNumber ?? "?"}: “{flag.sourceText}”
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </SectionCard>
                      )}

                      {analysis.terminology.length > 0 && (
                        <SectionCard
                          title="What the terms mean"
                          description="General explanations only — CareTwin AI supplies no reference ranges"
                          icon={<FileSearch className="h-4 w-4" />}
                        >
                          <dl className="space-y-2">
                            {analysis.terminology.map((item) => (
                              <div key={item.term} className="rounded-lg bg-mist-50 p-2.5">
                                <dt className="text-[0.66rem] font-semibold text-navy-800">
                                  {item.term}
                                </dt>
                                <dd className="mt-0.5 text-[0.63rem] leading-relaxed text-slate-500">
                                  {item.explanation}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </SectionCard>
                      )}

                      {(analysis.unreadableOrMissing.length > 0 ||
                        analysis.questionsToAsk.length > 0) && (
                        <div className="grid gap-4 md:grid-cols-2">
                          <SectionCard
                            title="Unreadable or missing"
                            description="What the extractor could not recover"
                            icon={<AlertTriangle className="h-4 w-4" />}
                          >
                            {analysis.unreadableOrMissing.length === 0 ? (
                              <p className="text-[0.66rem] text-slate-500">
                                Every page produced readable text.
                              </p>
                            ) : (
                              <ul className="space-y-2">
                                {analysis.unreadableOrMissing.map((item, index) => (
                                  <li
                                    key={`${item.scope}-${index}`}
                                    className="rounded-lg bg-mist-50 p-2.5 text-[0.63rem] leading-relaxed text-slate-500"
                                  >
                                    <span className="font-semibold text-slate-600">
                                      {item.scope === "page"
                                        ? `Page ${item.pageNumber ?? "?"}:`
                                        : "Document:"}
                                    </span>{" "}
                                    {item.detail}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </SectionCard>

                          <SectionCard
                            title="Questions for your clinician"
                            description="Generated from gaps in this document"
                            icon={<ClipboardList className="h-4 w-4" />}
                          >
                            <ul className="space-y-2">
                              {analysis.questionsToAsk.map((item, index) => (
                                <li
                                  key={index}
                                  className="text-[0.65rem] leading-relaxed text-slate-600"
                                >
                                  <span className="text-care-700">·</span> {item.question}
                                  <span className="mt-0.5 block pl-2 text-[0.58rem] text-slate-500">
                                    {item.basis}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </SectionCard>
                        </div>
                      )}

                      <SectionCard
                        title="Ask about this document"
                        description="Answers use only the extracted facts above, with page references"
                        icon={<FileSearch className="h-4 w-4" />}
                      >
                        <div className="flex flex-wrap gap-2">
                          {[
                            "Explain this report in simple language",
                            "Which values are outside the printed range?",
                            "What questions should I ask my doctor?",
                          ].map((question) => (
                            <Button
                              key={question}
                              size="sm"
                              variant="secondary"
                              disabled={assistantBusy || selectedUser.role === "caregiver"}
                              onClick={() => void askAboutDocument(question)}
                            >
                              {question}
                            </Button>
                          ))}
                        </div>
                        {assistantBusy && (
                          <LoadingBlock label="Reading the document" className="py-4" />
                        )}
                        {assistantError && (
                          <InlineMessage tone="error" className="mt-2">
                            {assistantError}
                          </InlineMessage>
                        )}
                        {assistantAnswer && (
                          <div className="mt-2.5 space-y-2 rounded-xl border border-care-200 bg-care-50 p-3">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <Badge tone="slate">{assistantAnswer.route}</Badge>
                              <Badge tone={assistantAnswer.aiConfigured ? "violet" : "amber"}>
                                {assistantAnswer.aiConfigured
                                  ? "model explanation"
                                  : "record retrieval only"}
                              </Badge>
                            </div>
                            <ul className="space-y-1">
                              {assistantAnswer.facts.map((fact, index) => (
                                <li key={index} className="text-[0.66rem] text-navy-800">
                                  · {fact}
                                </li>
                              ))}
                            </ul>
                            <p className="whitespace-pre-line text-[0.65rem] leading-relaxed text-slate-600">
                              {assistantAnswer.explanation}
                            </p>
                            {assistantAnswer.citations.length > 0 && (
                              <p className="text-[0.58rem] text-slate-500">
                                Sources:{" "}
                                {assistantAnswer.citations
                                  .slice(0, 3)
                                  .map(
                                    (citation) =>
                                      `${citation.documentName} p.${citation.pageNumber ?? "?"}`,
                                  )
                                  .join(" · ")}
                              </p>
                            )}
                            {assistantAnswer.modelNote && (
                              <p className="text-[0.58rem] text-amber-700">
                                {assistantAnswer.modelNote}
                              </p>
                            )}
                          </div>
                        )}
                      </SectionCard>

                      <p className="text-[0.6rem] leading-relaxed text-slate-500">
                        {analysis.limits.join(" ")}
                      </p>
                    </>
                  )}
                </div>
              )}

              {tab === "prescription" && (
                <div className="space-y-4">
                  {prescriptionLoading && <LoadingBlock label="Reading the prescription" />}
                  {prescriptionError !== null && <ErrorState error={prescriptionError} compact />}
                  {prescription && (
                    <>
                      <SectionCard
                        title={`Medicines as written · ${prescription.medicineCount}`}
                        description={`Transcribed from ${prescription.documentName} · unverified`}
                        icon={<Pill className="h-4 w-4" />}
                        action={
                          <Badge tone="amber">
                            {prescription.clarifications.length} need clarification
                          </Badge>
                        }
                      >
                        {prescription.medicines.length === 0 ? (
                          <EmptyState
                            title="No medicine line could be read"
                            description="Check the original prescription in the Original & pages tab before relying on any instruction."
                          />
                        ) : (
                          <div className="space-y-2">
                            {prescription.medicines.map((medicine, index) => (
                              <div
                                key={`${medicine.name}-${index}`}
                                className="rounded-xl border border-slate-100 bg-mist-50 p-3"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-[0.72rem] font-semibold text-navy-900">
                                    {medicine.name}
                                  </p>
                                  <div className="flex flex-wrap items-center gap-1.5">
                                    <Badge tone="slate">Page {medicine.pageNumber ?? "?"}</Badge>
                                    <Badge
                                      tone={medicine.clarificationNeeded.length ? "amber" : "teal"}
                                    >
                                      {medicine.clarificationNeeded.length
                                        ? "needs clarification"
                                        : "fields read"}
                                    </Badge>
                                  </div>
                                </div>
                                <dl className="mt-2 grid grid-cols-2 gap-1.5 text-[0.62rem] sm:grid-cols-4">
                                  {[
                                    ["Dose", medicine.dosage],
                                    ["Frequency", medicine.frequency],
                                    ["Timing", medicine.timing],
                                    ["Duration", medicine.duration],
                                  ].map(([label, value]) => (
                                    <div key={label} className="rounded bg-mist-100 p-1.5">
                                      <dt className="text-[0.5rem] uppercase tracking-[0.1em] text-slate-500">
                                        {label}
                                      </dt>
                                      <dd className={value ? "text-navy-800" : "text-amber-700"}>
                                        {value || "not readable"}
                                      </dd>
                                    </div>
                                  ))}
                                </dl>
                                <p className="mt-2 text-[0.62rem] leading-relaxed text-slate-500">
                                  {medicine.plainExplanation}
                                </p>
                                <p className="mt-1.5 border-l border-care-200 pl-2 text-[0.6rem] italic text-slate-500">
                                  “{medicine.sourceText}”
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </SectionCard>

                      <div className="grid gap-4 md:grid-cols-2">
                        <SectionCard
                          title="Prescriber"
                          description="As printed on the document"
                          icon={<ClipboardList className="h-4 w-4" />}
                        >
                          {prescription.prescriber.name ? (
                            <div className="text-[0.68rem] text-slate-600">
                              <p className="font-semibold text-navy-900">
                                {prescription.prescriber.name}
                              </p>
                              <p className="mt-0.5 text-slate-500">
                                Registration:{" "}
                                {prescription.prescriber.registrationNumber || "not printed"}
                              </p>
                              <p className="mt-0.5 text-slate-500">
                                Page {prescription.prescriber.pageNumber ?? "?"}
                              </p>
                            </div>
                          ) : (
                            <p className="text-[0.66rem] text-amber-700">
                              No prescriber name could be read from this document. Check the
                              original page.
                            </p>
                          )}
                          {prescription.clarifications.length > 0 && (
                            <ul className="mt-2 space-y-1">
                              {prescription.clarifications.map((item, index) => (
                                <li key={index} className="text-[0.62rem] text-amber-700">
                                  · {item}
                                </li>
                              ))}
                            </ul>
                          )}
                        </SectionCard>

                        <SectionCard
                          title="Prescription page text"
                          description="Original extraction, unedited"
                          icon={<FileText className="h-4 w-4" />}
                        >
                          <pre className="scrollbar-thin max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-mist-100 p-2.5 font-mono text-[0.6rem] leading-relaxed text-slate-600">
                            {detail.pages.map((page) => page.textContent).join("\n\n") ||
                              "No page text was recovered. Open the original file to read the prescription."}
                          </pre>
                        </SectionCard>
                      </div>

                      <div className="space-y-1.5">
                        <SafetyFooterNote />
                        <p className="text-[0.62rem] leading-relaxed text-slate-500">
                          {prescription.safetyNote}
                        </p>
                      </div>
                    </>
                  )}
                </div>
              )}

              {tab === "extracted" && (
                <SectionCard
                  title={`Extracted items · ${detail.extractions.length}`}
                  description="Every value keeps its page, source text and review state"
                  icon={<FileText className="h-4 w-4" />}
                  action={<Badge tone="amber">Unverified until reviewed</Badge>}
                >
                  {reviewError && (
                    <InlineMessage tone="error" className="mb-3">
                      {reviewError}
                    </InlineMessage>
                  )}
                  {detail.extractions.length === 0 ? (
                    <EmptyState
                      title="No structured items extracted"
                      description="The page text is available in the Original & pages tab even when no structured item was detected."
                    />
                  ) : (
                    <div className="space-y-2">
                      {detail.extractions.map((item) => {
                        const verified = item.verificationStatus === "verified";
                        const rejected = item.verificationStatus === "rejected";
                        return (
                          <div
                            key={item.id}
                            className="rounded-xl border border-slate-100 bg-mist-50 p-3"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div className="min-w-0">
                                <p className="text-[0.7rem] font-semibold text-navy-900">
                                  {item.label ||
                                    item.itemType?.replaceAll("_", " ") ||
                                    "Extracted item"}
                                </p>
                                <p className="mt-0.5 font-mono text-[0.68rem] text-navy-800">
                                  {formatValueWithUnit(
                                    item.correctedValueText || item.valueText,
                                    item.unit,
                                  )}
                                </p>
                              </div>
                              <Badge tone={verified ? "teal" : rejected ? "rose" : "amber"}>
                                {verified ? (
                                  <>
                                    <CheckCircle2 className="h-3 w-3" /> Clinician verified
                                  </>
                                ) : rejected ? (
                                  <>
                                    <XCircle className="h-3 w-3" /> Rejected
                                  </>
                                ) : (
                                  <>Unverified</>
                                )}
                              </Badge>
                            </div>
                            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[0.58rem] text-slate-500">
                              <Badge tone="slate">Page {item.pageNumber ?? "?"}</Badge>
                              {item.referenceRange && (
                                <Badge tone="slate">Range: {item.referenceRange}</Badge>
                              )}
                              <span className="truncate">{item.confidenceNote}</span>
                            </div>
                            {item.sourceText && (
                              <p className="mt-1.5 line-clamp-2 border-l border-care-200 pl-2 text-[0.62rem] italic leading-relaxed text-slate-500">
                                {item.sourceText}
                              </p>
                            )}
                            {item.reviewNote && (
                              <p className="mt-1.5 text-[0.6rem] text-slate-500">
                                Review note: {item.reviewNote}
                              </p>
                            )}
                            {selectedUser.role === "clinician" && !rejected && (
                              <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2">
                                <Button
                                  size="sm"
                                  variant="subtle"
                                  disabled={reviewingId === item.id || verified}
                                  onClick={() => void handleReview(item, "verify")}
                                >
                                  {reviewingId === item.id ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <CheckCircle2 className="h-3 w-3" />
                                  )}
                                  {verified ? "Verified" : "Verify against source"}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="danger"
                                  disabled={reviewingId === item.id}
                                  onClick={() => void handleReview(item, "reject")}
                                >
                                  <XCircle className="h-3 w-3" /> Reject
                                </Button>
                              </div>
                            )}
                            {selectedUser.role !== "clinician" && !verified && (
                              <p className="mt-2 text-[0.58rem] text-slate-500">
                                Awaiting clinician review. This value is not treated as confirmed.
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </SectionCard>
              )}

              {tab === "source" && (
                <div className="space-y-4">
                  <SectionCard
                    title="Original document"
                    description="Stored file exactly as uploaded · view is recorded in the audit trail"
                    icon={<FileSearch className="h-4 w-4" />}
                  >
                    {previewError ? (
                      <InlineMessage tone="warning">{previewError}</InlineMessage>
                    ) : !previewUrl ? (
                      <LoadingBlock label="Loading original file" className="py-6" />
                    ) : detail.mimeType === "application/pdf" ? (
                      <iframe
                        title={`Original ${detail.originalFilename}`}
                        src={previewUrl}
                        className="h-[32rem] w-full rounded-lg border border-slate-200 bg-white"
                      />
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={previewUrl}
                        alt={`Original ${detail.originalFilename}`}
                        className="max-h-[32rem] w-full rounded-lg border border-slate-200 object-contain"
                      />
                    )}
                  </SectionCard>

                  <SectionCard
                    title="Page extraction"
                    description="Per-page method and status · scanned pages use OCR"
                    icon={<ScanLine className="h-4 w-4" />}
                  >
                    {detail.pages.length === 0 ? (
                      <EmptyState title="No page records" />
                    ) : (
                      <div className="space-y-2">
                        {detail.pages.map((page) => (
                          <details
                            key={page.id}
                            open={sourcePage === page.pageNumber}
                            className="group rounded-xl border border-slate-100 bg-mist-50 px-3 py-2.5"
                          >
                            <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 [&::-webkit-details-marker]:hidden">
                              <span className="text-[0.7rem] font-semibold text-navy-800">
                                Page {page.pageNumber}
                              </span>
                              <span className="flex items-center gap-1.5">
                                <Badge tone="slate">{page.extractionMethod || "unknown"}</Badge>
                                <Badge
                                  tone={
                                    page.status === "extracted"
                                      ? "teal"
                                      : page.status === "error"
                                        ? "rose"
                                        : "amber"
                                  }
                                >
                                  {page.status?.replaceAll("_", " ") ?? "unavailable"}
                                </Badge>
                              </span>
                            </summary>
                            {page.error && (
                              <p className="mt-2 rounded-md bg-rose-50 px-2 py-1.5 text-[0.62rem] text-rose-700">
                                {page.error}
                              </p>
                            )}
                            <pre className="scrollbar-thin mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-mist-100 p-2.5 font-mono text-[0.62rem] leading-relaxed text-slate-600">
                              {page.textContent || "No extractable text on this page."}
                            </pre>
                          </details>
                        ))}
                      </div>
                    )}
                  </SectionCard>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
