"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { formatRelative } from "@caretwin/shared";
import { ApiClientError, errorMessage } from "@/lib/api";
import { Badge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/cards";
import { InlineMessage, LoadingBlock } from "@/components/ui/feedback";
import {
  fetchDocumentExplanation,
  requestDocumentExplanation,
  type AiStatus,
  type DocumentExplanation,
  type ExplanationValidationFailure,
} from "@/lib/documents";

const FAILURE_LABELS: Record<string, string> = {
  unsupported_number: "The model stated a number that is not printed in this document.",
  unknown_citation: "The model cited a source that was not supplied with the document.",
  diagnosis_claim: "The model asserted a diagnosis. CareTwin never displays one.",
  medication_change: "The model advised changing or stopping a medicine.",
  no_uncertainty: "The model did not disclose its uncertainty.",
  no_limitations: "The model did not state its limitations.",
  missing_escalation: "The report contains urgent findings but the model did not advise urgent care.",
};

const PROVIDER_FAILURE_CODES = new Set([
  "ai_timeout",
  "ai_provider_unavailable",
  "ai_rate_limited",
  "ai_quota_exhausted",
  "ai_auth_failed",
  "ai_model_unavailable",
  "ai_content_blocked",
  "ai_invalid_response",
  "ai_request_budget_exhausted",
]);

function failureLabel(failure: ExplanationValidationFailure) {
  return FAILURE_LABELS[failure.code] ?? failure.code.replaceAll("_", " ");
}

export function AiExplanationPanel({
  patientId,
  documentId,
  mode,
  userId,
  aiStatus,
  onOpenPage,
  className,
}: {
  patientId: string;
  documentId: string;
  mode: "report" | "prescription";
  userId: string;
  aiStatus: AiStatus | null;
  onOpenPage?: (pageNumber: number | null) => void;
  className?: string;
}) {
  const [explanation, setExplanation] = useState<DocumentExplanation | null>(null);
  const [loadingSaved, setLoadingSaved] = useState(true);
  const [savedError, setSavedError] = useState<unknown>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<unknown>(null);
  const [servedFrom, setServedFrom] = useState<"saved" | "generated" | null>(null);

  const loadSaved = useCallback(async () => {
    setLoadingSaved(true);
    setSavedError(null);
    try {
      const payload = await fetchDocumentExplanation(patientId, documentId, mode, userId);
      setExplanation(payload.available ? payload : null);
      setServedFrom(payload.available ? "saved" : null);
    } catch (error) {
      setSavedError(error);
    } finally {
      setLoadingSaved(false);
    }
  }, [patientId, documentId, mode, userId]);

  useEffect(() => {
    setExplanation(null);
    setGenerateError(null);
    setServedFrom(null);
    void loadSaved();
  }, [loadSaved]);

  const configured = Boolean(aiStatus?.configured);
  const apiError = generateError instanceof ApiClientError ? generateError : null;
  const validationFailures =
    apiError?.code === "ai_output_rejected"
      ? ((apiError.details?.failures as ExplanationValidationFailure[] | undefined) ?? [])
      : [];
  const providerFailure = apiError ? PROVIDER_FAILURE_CODES.has(apiError.code) : false;

  const generate = async (force: boolean) => {
    setGenerating(true);
    setGenerateError(null);
    try {
      const payload = await requestDocumentExplanation({
        patientId,
        documentId,
        mode,
        userId,
        force,
      });
      setExplanation(payload);
      setServedFrom("generated");
    } catch (error) {
      setGenerateError(error);
    } finally {
      setGenerating(false);
    }
  };

  const isPrescription = mode === "prescription";

  return (
    <SectionCard
      className={className}
      title={isPrescription ? "AI prescription explanation" : "AI explanation"}
      description={
        isPrescription
          ? "Model-written explanation of the written instructions — never a new prescription"
          : "Model-written explanation verified against this document before display"
      }
      icon={<Sparkles className="h-4 w-4" />}
      action={
        <div className="flex flex-wrap items-center gap-1.5">
          {explanation ? (
            <Badge tone="violet">AI-powered analysis</Badge>
          ) : configured ? (
            <Badge tone="slate">Not generated yet</Badge>
          ) : (
            <Badge tone="amber">AI unavailable</Badge>
          )}
          {explanation?.model && <Badge tone="slate">{explanation.model}</Badge>}
        </div>
      }
    >
      {loadingSaved && <LoadingBlock label="Checking for a saved explanation" className="py-4" />}

      {!loadingSaved && savedError !== null && (
        <InlineMessage tone="warning" className="mb-3">
          A saved explanation could not be checked: {errorMessage(savedError)}
        </InlineMessage>
      )}

      {!configured && !explanation && (
        <InlineMessage tone="warning" title="AI explanation is unavailable">
          {aiStatus?.message ??
            "The API server has no Gemini key configured, so no model-written explanation can be produced."}{" "}
          The deterministic extraction below is complete and does not use a language model.
        </InlineMessage>
      )}

      {configured && !explanation && (
        <div className="space-y-2">
          <p className="text-[0.68rem] leading-relaxed text-slate-500">
            CareTwin can ask {aiStatus?.provider ?? "Gemini"} to explain this{" "}
            {isPrescription ? "prescription" : "report"} in plain language. The document is treated as
            untrusted data, the answer is checked against the printed values, and an answer that
            invents a number, a diagnosis or a medicine change is discarded rather than shown.
          </p>
          <Button size="sm" disabled={generating} onClick={() => void generate(false)}>
            {generating ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" /> Generate AI explanation
              </>
            )}
          </Button>
          <p className="text-[0.58rem] text-slate-500">
            Uses one provider request {aiStatus?.limits ? `· budget ${aiStatus.limits.requestsPerHour}/hour · timeout ${aiStatus.limits.timeoutSeconds}s` : ""}
          </p>
        </div>
      )}

      {apiError && (
        <div className="mt-3">
          {apiError.code === "ai_output_rejected" ? (
            <InlineMessage tone="error" title="AI answer rejected by CareTwin validation">
              <p>{apiError.message}</p>
              <ul className="mt-1.5 space-y-0.5">
                {validationFailures.map((failure) => (
                  <li key={failure.code}>· {failureLabel(failure)}</li>
                ))}
              </ul>
              <p className="mt-1.5 text-[0.62rem] text-rose-700">
                Nothing from that answer is shown. Fix the extraction or regenerate after review.
              </p>
            </InlineMessage>
          ) : (
            <InlineMessage tone="warning" title={providerFailure ? "AI provider unavailable" : "AI explanation failed"}>
              {apiError.message}
              <p className="mt-1 text-[0.62rem] text-amber-700">
                Deterministic extraction, comparison and your records remain available.
              </p>
            </InlineMessage>
          )}
        </div>
      )}

      {explanation && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone="teal">evidence validated</Badge>
            {servedFrom === "saved" && <Badge tone="slate">saved explanation</Badge>}
            {servedFrom === "generated" && <Badge tone="violet">freshly generated</Badge>}
            <span className="text-[0.56rem] text-slate-500">
              {explanation.meta?.model ?? explanation.model} ·{" "}
              {formatRelative(explanation.generatedAt)}
              {explanation.meta?.latencyMs ? ` · ${Math.round(explanation.meta.latencyMs)} ms` : ""}
            </span>
          </div>

          {explanation.injectionSignals && explanation.injectionSignals.length > 0 && (
            <InlineMessage tone="warning" title="Instruction-like text was ignored">
              This document contains text that looks like an instruction to the model (
              {explanation.injectionSignals.join(", ").replaceAll("_", " ")}). It was kept as data,
              neutralised in the prompt and recorded in the audit trail.
            </InlineMessage>
          )}

          {explanation.summary && (
            <p className="text-[0.72rem] leading-relaxed text-navy-800">{explanation.summary}</p>
          )}

          {explanation.results && explanation.results.length > 0 && (
            <div className="space-y-2">
              {explanation.results.map((row, index) => (
                <div
                  key={`${row.label}-${index}`}
                  className="rounded-xl border border-slate-100 bg-mist-50 p-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                    <p className="text-[0.68rem] font-semibold text-navy-900">
                      {row.label}: {row.valueText} {row.unit}
                    </p>
                    <div className="flex items-center gap-1.5">
                      {row.referenceRangePrinted && (
                        <Badge tone="slate">printed range {row.referenceRangePrinted}</Badge>
                      )}
                      {onOpenPage && (
                        <button
                          type="button"
                          onClick={() => onOpenPage(row.pageNumber)}
                          className="inline-flex items-center gap-1 rounded-full border border-care-200 px-2 py-0.5 text-[0.56rem] text-care-700 hover:bg-care-50"
                        >
                          <ExternalLink className="h-2.5 w-2.5" />
                          p.{row.pageNumber ?? "?"}
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="mt-1 text-[0.63rem] leading-relaxed text-slate-500">
                    {row.explanation}
                  </p>
                </div>
              ))}
            </div>
          )}

          {explanation.terminology && explanation.terminology.length > 0 && (
            <dl className="space-y-1.5">
              {explanation.terminology.map((item) => (
                <div key={item.term} className="rounded-lg bg-mist-50 p-2">
                  <dt className="text-[0.64rem] font-semibold text-navy-800">{item.term}</dt>
                  <dd className="mt-0.5 text-[0.62rem] leading-relaxed text-slate-500">
                    {item.explanation}
                  </dd>
                </div>
              ))}
            </dl>
          )}

          {explanation.interpretation && (
            <p className="text-[0.68rem] leading-relaxed text-slate-600">
              {explanation.interpretation}
            </p>
          )}

          <div className="grid gap-2 md:grid-cols-2">
            {explanation.findingsForClinicianReview && explanation.findingsForClinicianReview.length > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-2.5">
                <p className="flex items-center gap-1.5 text-[0.56rem] font-semibold uppercase tracking-[0.12em] text-amber-700">
                  <AlertTriangle className="h-3 w-3" /> For clinician review
                </p>
                <ul className="mt-1 space-y-0.5 text-[0.62rem] leading-relaxed text-amber-700">
                  {explanation.findingsForClinicianReview.map((item, index) => (
                    <li key={index}>· {item}</li>
                  ))}
                </ul>
              </div>
            )}
            {explanation.missingOrAmbiguous && explanation.missingOrAmbiguous.length > 0 && (
              <div className="rounded-xl border border-slate-100 bg-mist-50 p-2.5">
                <p className="text-[0.56rem] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Missing or ambiguous
                </p>
                <ul className="mt-1 space-y-0.5 text-[0.62rem] leading-relaxed text-slate-500">
                  {explanation.missingOrAmbiguous.map((item, index) => (
                    <li key={index}>· {item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {explanation.questionsForDoctor && explanation.questionsForDoctor.length > 0 && (
            <div>
              <p className="text-[0.56rem] font-semibold uppercase tracking-[0.12em] text-slate-500">
                Questions for your clinician
              </p>
              <ul className="mt-1 space-y-0.5 text-[0.62rem] leading-relaxed text-slate-600">
                {explanation.questionsForDoctor.map((item, index) => (
                  <li key={index}>· {item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.generalEducation && explanation.generalEducation.length > 0 && (
            <div className="rounded-lg border border-slate-100 bg-mist-50 p-2.5">
              <p className="text-[0.56rem] font-semibold uppercase tracking-[0.12em] text-slate-500">
                General education (not about your result)
              </p>
              <ul className="mt-1 space-y-0.5 text-[0.62rem] leading-relaxed text-slate-500">
                {explanation.generalEducation.map((item, index) => (
                  <li key={index}>· {item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.uncertainty && (
            <p className="rounded-lg border border-slate-100 bg-mist-50 p-2 text-[0.6rem] italic leading-relaxed text-slate-500">
              Uncertainty: {explanation.uncertainty}
            </p>
          )}

          {explanation.citations && explanation.citations.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="inline-flex items-center gap-1 text-[0.56rem] uppercase tracking-[0.12em] text-slate-500">
                <FileText className="h-3 w-3" /> Evidence cited
              </span>
              {explanation.citations.slice(0, 6).map((citation) => (
                <Badge key={citation} tone="slate">
                  {citation.length > 34 ? `${citation.slice(0, 34)}…` : citation}
                </Badge>
              ))}
            </div>
          )}

          {explanation.limitations && explanation.limitations.length > 0 && (
            <p className="text-[0.58rem] leading-relaxed text-slate-500">
              {explanation.limitations.join(" ")}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={generating}
              onClick={() => void generate(true)}
            >
              {generating ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Regenerating…
                </>
              ) : (
                <>
                  <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                </>
              )}
            </Button>
            <span className="text-[0.56rem] text-slate-500">
              A regenerated answer replaces the saved one only after it passes validation.
            </span>
          </div>

          <p className="flex items-start gap-1.5 border-t border-slate-100 pt-2 text-[0.58rem] leading-relaxed text-slate-500">
            <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0 text-slate-600" />
            AI-generated explanation · not a diagnosis, prescription or reference range. CareTwin
            never changes a dose. Confirm every clinical decision with your care team.
          </p>
        </div>
      )}

      {!configured && explanation && (
        <p className="mt-2 text-[0.58rem] text-slate-500">
          This saved explanation was generated earlier while the model was configured.{" "}
          <Bot className="inline h-3 w-3" /> It is shown as stored, not regenerated.
        </p>
      )}
    </SectionCard>
  );
}
