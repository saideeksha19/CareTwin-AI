"use client";

import { useState } from "react";
import {
  BookOpenCheck,
  FileSearch,
  Loader2,
  Quote,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { formatDateTime, formatRelative } from "@caretwin/shared";
import { apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/fields";
import {
  EmptyState,
  ErrorState,
  InlineMessage,
  LoadingBlock,
  PageSkeleton,
  SafetyFooterNote,
} from "@/components/ui/feedback";
import type { GuidanceRecord, GuidanceResult } from "@/lib/documents";

const GUIDANCE_TYPES = [
  { value: "general", label: "General summary" },
  { value: "document_explanation", label: "Explain my documents" },
  { value: "medical_history_summary", label: "Medical history summary" },
  { value: "lab_findings", label: "Documented lab findings" },
  { value: "discharge_instructions", label: "Discharge instructions" },
  { value: "precautions", label: "Documented precautions" },
  { value: "medication_instructions", label: "Medication instructions" },
  { value: "follow_up", label: "Follow-up requirements" },
  { value: "clinician_questions", label: "Questions for my clinician" },
  { value: "historical_comparison", label: "Historical comparison" },
];

export default function GuidancePage() {
  const { patientId, selectedUser } = useSession();
  const historyState = useApi<GuidanceRecord[]>(
    patientId ? `/patients/${patientId}/guidance/history` : null,
  );
  const [guidanceType, setGuidanceType] = useState("document_explanation");
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GuidanceResult | null>(null);
  const [selectedHistory, setSelectedHistory] = useState<GuidanceRecord | null>(null);

  if (!selectedUser) return <PageSkeleton />;

  const generate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!patientId) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const payload = await apiRequest<GuidanceResult>(
        `/patients/${patientId}/guidance`,
        {
          method: "POST",
          userId: selectedUser.id,
          body: {
            guidanceType,
            question: question.trim().slice(0, 1000),
          },
        },
      );
      setResult(payload);
      setSelectedHistory(null);
      historyState.refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRunning(false);
    }
  };

  if (historyState.loading && !historyState.data) return <PageSkeleton />;

  const shown = result ?? null;
  const historyRecord = selectedHistory;

  return (
    <div>
      <PageHeader
        eyebrow="Recovery guidance"
        title="Evidence-grounded explanations"
        description="Ask for an explanation of the documented record. CareTwin quotes verified sources, lists unverified items separately, and never diagnoses, prescribes or changes a dose. Explanations are informational only."
        actions={
          <Badge tone="violet">
            <Sparkles className="h-3 w-3" /> Informational, not medical advice
          </Badge>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <div className="space-y-4">
          <SectionCard
            title="Request guidance"
            description="If no AI model is configured, a deterministic, source-quoted summary is returned."
            icon={<BookOpenCheck className="h-4 w-4" />}
          >
            <form onSubmit={generate} className="space-y-3">
              <Field label="Guidance type" htmlFor="guidance-type">
                <Select
                  id="guidance-type"
                  value={guidanceType}
                  onChange={(event) => setGuidanceType(event.target.value)}
                  disabled={running}
                >
                  {GUIDANCE_TYPES.map((type) => (
                    <option key={type.value} value={type.value} className="bg-white">
                      {type.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field
                label="Optional question"
                htmlFor="guidance-question"
                hint="Questions are answered only from the documented record."
              >
                <Textarea
                  id="guidance-question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  maxLength={1000}
                  placeholder="What did my discharge summary say about follow-up?"
                  disabled={running}
                />
              </Field>
              <Button type="submit" size="sm" disabled={running}>
                {running ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Grounding…
                  </>
                ) : (
                  <>
                    <Sparkles className="h-3.5 w-3.5" /> Generate grounded guidance
                  </>
                )}
              </Button>
              {error && (
                <InlineMessage tone="error" title="Guidance unavailable">
                  {error}
                </InlineMessage>
              )}
            </form>
          </SectionCard>

          <SectionCard
            title="Guidance history"
            description="Every request is recorded with its mode and citations"
            icon={<FileSearch className="h-4 w-4" />}
          >
            {historyState.loading ? (
              <LoadingBlock label="Loading history" className="py-6" />
            ) : historyState.data?.length ? (
              <ul className="space-y-1.5">
                {historyState.data.slice(0, 12).map((record) => (
                  <li key={record.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedHistory(record);
                        setResult(null);
                      }}
                      className={
                        historyRecord?.id === record.id
                          ? "w-full rounded-lg border border-care-200 bg-care-50 px-3 py-2 text-left"
                          : "w-full rounded-lg border border-transparent px-3 py-2 text-left transition-colors hover:border-slate-200 hover:bg-mist-100"
                      }
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-[0.7rem] font-medium capitalize text-navy-900">
                          {record.guidanceType.replaceAll("_", " ")}
                        </span>
                        <Badge tone={record.grounded ? "teal" : "amber"}>
                          {record.grounded ? "grounded" : "ungrounded"}
                        </Badge>
                      </span>
                      <span className="mt-0.5 block text-[0.56rem] text-slate-500">
                        {formatRelative(record.createdAt)} · {record.mode.replaceAll("_", " ")}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No guidance yet"
                description="Generate guidance once to create an auditable history entry."
              />
            )}
          </SectionCard>
        </div>

        <div className="space-y-4">
          {shown && (
            <SectionCard
              title="Grounded response"
              description={`${shown.mode.replaceAll("_", " ")} · ${formatDateTime(shown.createdAt)}`}
              icon={<Sparkles className="h-4 w-4" />}
              action={
                <Badge tone={shown.grounded ? "teal" : "amber"}>
                  {shown.grounded ? "Grounded in record" : "Not fully grounded"}
                </Badge>
              }
            >
              <pre className="whitespace-pre-wrap font-sans text-[0.76rem] leading-relaxed text-navy-800">
                {shown.answer}
              </pre>

              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {[
                  ["Documents", shown.evidenceSummary.documentCount ?? 0],
                  ["Verified items", shown.evidenceSummary.verifiedExtractionCount ?? 0],
                  ["Unverified items", shown.evidenceSummary.unverifiedExtractionCount ?? 0],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-mist-100 p-2.5">
                    <p className="text-[0.52rem] uppercase tracking-[0.12em] text-slate-500">
                      {label}
                    </p>
                    <p className="mt-0.5 text-sm font-semibold text-navy-950">{value}</p>
                  </div>
                ))}
              </div>

              {shown.citations.length > 0 && (
                <div className="mt-3">
                  <p className="text-[0.55rem] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Cited sources
                  </p>
                  <ul className="mt-1.5 space-y-1">
                    {shown.citations.map((citation) => (
                      <li
                        key={citation.id}
                        className="flex flex-wrap items-center gap-1.5 rounded-md bg-mist-50 px-2 py-1.5 text-[0.62rem] text-slate-300"
                      >
                        <Quote className="h-3 w-3 shrink-0 text-care-500" />
                        <span className="font-medium">{citation.label}</span>
                        <span className="text-slate-500">
                          {citation.documentName ?? "document"} · p.
                          {citation.pageNumber ?? "?"}
                        </span>
                        <Badge tone={citation.verificationStatus === "verified" ? "teal" : "amber"}>
                          {citation.verificationStatus.replaceAll("_", " ")}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <InlineMessage tone="info" className="mt-4" title="How to read this">
                Deterministic mode quotes documented facts only. When a model is
                configured, its explanation is validated against the same grounding.
                {shown.unverifiedItemsExcludedFromConfirmation > 0 && (
                  <>
                    {" "}
                    {shown.unverifiedItemsExcludedFromConfirmation} unverified item
                    {shown.unverifiedItemsExcludedFromConfirmation === 1 ? " was" : "s were"}{" "}
                    excluded from confirmation.
                  </>
                )}
              </InlineMessage>
              <p className="mt-2 text-[0.62rem] text-slate-500">
                AI state: {shown.aiState.replaceAll("_", " ")}
                {shown.model ? ` · model ${shown.model}` : ""}
              </p>
            </SectionCard>
          )}

          {historyRecord && !shown && (
            <SectionCard
              title="Recorded guidance"
              description={`${historyRecord.mode.replaceAll("_", " ")} · ${formatDateTime(historyRecord.createdAt)}`}
              icon={<FileSearch className="h-4 w-4" />}
              action={
                <Badge tone={historyRecord.grounded ? "teal" : "amber"}>
                  {historyRecord.grounded ? "Grounded" : "Ungrounded"}
                </Badge>
              }
            >
              <p className="text-[0.68rem] uppercase tracking-[0.12em] text-slate-500">
                {historyRecord.guidanceType.replaceAll("_", " ")}
              </p>
              {historyRecord.question && (
                <p className="mt-1 text-[0.72rem] italic text-slate-400">
                  “{historyRecord.question}”
                </p>
              )}
              <pre className="mt-3 whitespace-pre-wrap font-sans text-[0.76rem] leading-relaxed text-navy-800">
                {historyRecord.answer}
              </pre>
              <p className="mt-3 text-[0.6rem] text-slate-500">
                Requested by {historyRecord.requestedBy.name ?? "unknown"} (
                {historyRecord.requestedBy.role ?? "unknown"}) · AI state{" "}
                {historyRecord.aiState.replaceAll("_", " ")}
              </p>
              <p className="mt-1 text-[0.6rem] text-slate-500">
                {historyRecord.citations.length} citation
                {historyRecord.citations.length === 1 ? "" : "s"} retained with this record.
              </p>
            </SectionCard>
          )}

          {!shown && !historyRecord && (
            <SectionCard
              title="What this page will not do"
              description="Clinical boundaries are enforced server-side"
              icon={<ShieldAlert className="h-4 w-4" />}
            >
              <ul className="space-y-2 text-[0.72rem] leading-relaxed text-slate-300">
                {[
                  "It will not diagnose a condition or interpret the 3D model.",
                  "It will not recommend a medication, dose or dose change.",
                  "It will not treat an unverified OCR value as confirmed.",
                  "It will not create alerts — those come only from clinician-configured rules.",
                ].map((line) => (
                  <li key={line} className="flex gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-care-300" />
                    {line}
                  </li>
                ))}
              </ul>
              <div className="mt-3">
                <SafetyFooterNote />
              </div>
            </SectionCard>
          )}
        </div>
      </div>
    </div>
  );
}
