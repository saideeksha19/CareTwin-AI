"use client";

import { useCallback, useEffect, useState } from "react";
import { Bot, FileText, Loader2, ShieldAlert, Sparkles } from "lucide-react";
import { formatRelative } from "@caretwin/shared";
import { ApiClientError, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import {
  EmptyState,
  ErrorState,
  InlineMessage,
  LoadingBlock,
  PageSkeleton,
  SafetyFooterNote,
} from "@/components/ui/feedback";
import {
  askAssistant,
  fetchAssistantHistory,
  type AssistantAnswer,
  type AssistantRecord,
} from "@/lib/documents";

type AiStatus = {
  configured: boolean;
  provider: string;
  model: string;
  state: string;
  message: string;
};

const SUGGESTIONS = [
  "Explain my latest blood report",
  "What does hemoglobin mean in my report?",
  "Compare my latest report with my previous report",
  "Explain my prescription",
  "What precautions did my doctor document?",
  "What follow-up instructions are available in my records?",
  "Summarize my medical history",
  "What questions should I ask during my next consultation?",
];

export default function AssistantPage() {
  const { patientId, selectedUser } = useSession();
  const aiState = useApi<AiStatus>("/ai/status");
  const [messages, setMessages] = useState<AssistantAnswer[]>([]);
  const [history, setHistory] = useState<AssistantRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<unknown>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    if (!patientId || !selectedUser) return;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const rows = await fetchAssistantHistory(patientId, selectedUser.id);
      setHistory(rows);
      const latestConversation = rows.length ? rows[rows.length - 1].conversationId : null;
      setConversationId((current) => current ?? latestConversation);
    } catch (err) {
      setHistoryError(err);
    } finally {
      setHistoryLoading(false);
    }
  }, [patientId, selectedUser]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  if (!selectedUser) return <PageSkeleton />;

  const status = aiState.data;
  const caregiver = selectedUser.role === "caregiver";

  const ask = async (text: string) => {
    if (!patientId || !selectedUser || !text.trim()) return;
    setAsking(true);
    setError(null);
    setLastQuestion(text.trim());
    try {
      const answer = await askAssistant({
        patientId,
        userId: selectedUser.id,
        question: text.trim(),
        conversationId,
      });
      setConversationId(answer.conversationId);
      setMessages((current) => [...current, answer]);
      setQuestion("");
      void loadHistory();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAsking(false);
    }
  };

  if (aiState.loading && !aiState.data) return <PageSkeleton />;
  if (aiState.error) {
    return <ErrorState error={aiState.error} onRetry={aiState.refresh} />;
  }

  if (caregiver) {
    return (
      <div>
        <PageHeader eyebrow="CareTwin AI assistant" title="Assistant is limited to the patient and care team" />
        <InlineMessage tone="warning" title="Consent boundary">
          Caregivers keep their shared document, schedule and alert access, but the assistant
          answers only for the patient and their clinician because it summarizes full records.
          Switch to the patient or clinician demo identity to use it.
        </InlineMessage>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="CareTwin AI assistant"
        title="Ask your own records."
        description="Answers are built from the documents, extractions, encounters and follow-ups stored for this patient. Every fact keeps its document and page reference, and unverified extraction is never presented as confirmed."
        actions={
          <div className="flex flex-wrap gap-1.5">
            <Badge tone={status?.configured ? "teal" : "amber"}>
              <Bot className="h-3 w-3" />
              {status?.configured ? "model ready" : "record retrieval only"}
            </Badge>
            <Badge tone="slate">{status?.model || "no model"}</Badge>
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <div className="space-y-4">
          <SectionCard
            title="Conversation"
            description="Patient-specific · evidence-linked · uncertainty stated"
            icon={<Sparkles className="h-4 w-4" />}
            action={
              messages.length > 0 ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setMessages([]);
                    setConversationId(null);
                  }}
                >
                  New conversation
                </Button>
              ) : null
            }
          >
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void ask(question);
              }}
              className="space-y-2"
            >
              <label className="block text-[0.62rem] font-semibold text-slate-400">
                Your question
                <textarea
                  value={question}
                  rows={2}
                  maxLength={500}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="e.g. Explain my latest blood report"
                  className="mt-1 block w-full resize-y rounded-lg border border-slate-200 bg-mist-100 px-2.5 py-2 text-[0.72rem] text-navy-900 placeholder:text-slate-600 focus:border-care-300 focus:outline-none focus:ring-2 focus:ring-care-300/15"
                />
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <Button type="submit" size="sm" disabled={asking || !question.trim()}>
                  {asking ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Reading records…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3.5 w-3.5" /> Ask CareTwin AI
                    </>
                  )}
                </Button>
                <span className="text-[0.6rem] text-slate-500">
                  {question.length}/500 · answers never change medicines or diagnose
                </span>
              </div>
            </form>

            {error && (
              <InlineMessage tone="error" className="mt-3" title="Assistant unavailable">
                {error}
                {lastQuestion && (
                  <div className="mt-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={asking}
                      onClick={() => void ask(lastQuestion)}
                    >
                      Retry question
                    </Button>
                  </div>
                )}
              </InlineMessage>
            )}

            <div className="mt-3 flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={asking}
                  onClick={() => void ask(suggestion)}
                  className="rounded-full border border-slate-200 bg-mist-50 px-2.5 py-1 text-[0.6rem] text-slate-300 transition-colors hover:border-care-300 hover:text-care-800 disabled:opacity-40"
                >
                  {suggestion}
                </button>
              ))}
            </div>

            <div className="mt-4 space-y-3">
              {messages.length === 0 && !asking && (
                <EmptyState
                  icon={<Bot className="h-4 w-4" />}
                  title="No question asked in this session"
                  description="Pick a suggestion above or ask about a specific report, medicine or precaution."
                />
              )}
              {messages.map((answer) => (
                <div key={answer.id} className="space-y-2">
                  <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-care-50 px-3 py-1.5 text-[0.72rem] text-care-50">
                    {answer.question}
                  </p>
                  <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white p-3">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone="slate">{answer.route.replaceAll("_", " ")}</Badge>
                      <Badge
                        tone={
                          answer.aiState === "used"
                            ? "violet"
                            : answer.aiState === "error"
                              ? "amber"
                              : "slate"
                        }
                      >
                        {answer.aiState === "used"
                          ? "AI explanation · grounded"
                          : answer.aiState === "error"
                            ? "AI unavailable · deterministic"
                            : "deterministic records"}
                      </Badge>
                      <span className="text-[0.56rem] text-slate-500">
                        {formatRelative(answer.createdAt)}
                      </span>
                    </div>

                    {answer.facts.length > 0 && (
                      <div className="mt-2 rounded-lg bg-mist-100 p-2.5">
                        <p className="text-[0.54rem] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Extracted facts
                        </p>
                        <ul className="mt-1 space-y-1">
                          {answer.facts.map((fact, index) => (
                            <li key={index} className="text-[0.66rem] leading-relaxed text-navy-800">
                              · {fact}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <p className="mt-2 whitespace-pre-line text-[0.7rem] leading-relaxed text-slate-300">
                      {answer.explanation}
                    </p>

                    {answer.uncertainty && (
                      <p className="mt-2 rounded-lg border border-slate-100 bg-mist-50 p-2 text-[0.6rem] italic leading-relaxed text-slate-400">
                        Uncertainty: {answer.uncertainty}
                      </p>
                    )}

                    {answer.followUpQuestions.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {answer.followUpQuestions.map((followUp) => (
                          <button
                            key={followUp}
                            type="button"
                            disabled={asking}
                            onClick={() => void ask(followUp)}
                            className="rounded-full border border-care-200 bg-care-50 px-2.5 py-1 text-[0.58rem] text-care-800 transition-colors hover:border-care-300 disabled:opacity-40"
                          >
                            {followUp}
                          </button>
                        ))}
                      </div>
                    )}

                    {answer.citations.length > 0 && (
                      <div className="mt-2.5">
                        <p className="text-[0.54rem] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Sources
                        </p>
                        <div className="mt-1 space-y-1">
                          {answer.citations.slice(0, 6).map((citation) => (
                            <div
                              key={`${citation.id}-${citation.pageNumber}`}
                              className="rounded-lg border border-slate-100 bg-mist-50 p-2"
                            >
                              <div className="flex flex-wrap items-center gap-1.5">
                                <FileText className="h-3 w-3 text-care-700" />
                                <span className="text-[0.62rem] font-semibold text-navy-800">
                                  {citation.documentName || "Record"}
                                </span>
                                <Badge tone="slate">Page {citation.pageNumber ?? "?"}</Badge>
                                <Badge
                                  tone={
                                    citation.verificationStatus === "verified" ? "teal" : "amber"
                                  }
                                >
                                  {citation.verificationStatus}
                                </Badge>
                              </div>
                              {citation.quote && (
                                <p className="mt-1 line-clamp-2 text-[0.6rem] italic text-slate-400">
                                  “{citation.quote}”
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {answer.modelNote && (
                      <p className="mt-2 text-[0.58rem] leading-relaxed text-amber-700">
                        {answer.modelNote}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              {asking && <LoadingBlock label="Reading your records" className="py-3" />}
            </div>
          </SectionCard>

          <div className="space-y-1.5">
            <SafetyFooterNote />
            <p className="text-[0.64rem] leading-relaxed text-slate-400">
              The assistant explains recorded information only. It does not diagnose, does not
              recommend starting, stopping or changing a medicine, and does not supply reference
              ranges. Confirm every clinical decision with your care team.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <SectionCard
            title="Earlier questions"
            description="Stored per patient, with the same source references"
            icon={<ShieldAlert className="h-4 w-4" />}
          >
            {historyLoading ? (
              <LoadingBlock label="Loading history" className="py-4" />
            ) : historyError ? (
              <ErrorState error={historyError} onRetry={() => void loadHistory()} compact />
            ) : history.length === 0 ? (
              <EmptyState title="No assistant history yet" />
            ) : (
              <ul className="scrollbar-thin max-h-[30rem] space-y-2 overflow-y-auto pr-1">
                {[...history].reverse().slice(0, 20).map((row) => (
                  <li
                    key={row.id}
                    className="rounded-lg border border-slate-100 bg-mist-50 p-2.5"
                  >
                    <p className="text-[0.64rem] font-semibold text-navy-800">{row.question}</p>
                    <p className="mt-0.5 text-[0.52rem] text-slate-500">
                      {formatRelative(row.createdAt)} · {row.mode} · {row.aiState}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
