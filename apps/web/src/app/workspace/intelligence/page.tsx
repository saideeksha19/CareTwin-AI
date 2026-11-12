"use client";

import { useState } from "react";
import {
  Bot,
  Brain,
  Database,
  Fingerprint,
  GitCommitVertical,
  KeyRound,
  Landmark,
  Layers,
  ScanLine,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import type {
  AgentInfo,
  AiExplanation,
  AiStatus,
  AuditEvent,
  EvidenceSource,
  SafetyDecision,
  TwinSnapshotMeta,
} from "@caretwin/contracts";
import { formatDateTime, formatRelative } from "@caretwin/shared";
import { ApiClientError, apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { LinkButton } from "@/components/ui/button";
import {
  Badge,
  MaturityBadge,
  SourceTypeBadge,
  VerificationBadge,
} from "@/components/ui/badges";
import {
  AccessRestricted,
  EmptyState,
  ErrorState,
  InlineMessage,
  LoadingBlock,
  PageSkeleton,
} from "@/components/ui/feedback";
import { Tabs } from "@/components/ui/tabs";
import { SafetyDecisionCard } from "@/components/workspace/records";

type Tab = "agents" | "evidence" | "ai" | "trust";

type AgentsResponse = { generatedAt: string; agents: AgentInfo[] };

const maturityLegend: Array<{ label: string; status: string; detail: string }> = [
  {
    label: "Working · deterministic",
    status: "working_deterministic",
    detail: "Runs end to end without a model.",
  },
  {
    label: "Working · permissions",
    status: "working_permissions",
    detail: "Role and consent enforcement runs end to end.",
  },
  {
    label: "Architecturally prepared",
    status: "architecturally_prepared",
    detail: "Contracts and data exist; generation is not enabled.",
  },
  {
    label: "Needs AI configuration",
    status: "requires_ai_configuration",
    detail: "Requires a server-side model key.",
  },
];

export default function IntelligencePage() {
  const { patientId, selectedUser } = useSession();
  const role = selectedUser?.role;
  const isCaregiver = role === "caregiver";

  const agentsState = useApi<AgentsResponse>("/agents");
  const aiState = useApi<AiStatus>("/ai/status");
  const evidenceState = useApi<EvidenceSource[]>(
    patientId ? `/patients/${patientId}/evidence` : null,
  );
  const snapshotsState = useApi<TwinSnapshotMeta[]>(
    patientId ? `/patients/${patientId}/snapshots` : null,
  );
  const decisionsState = useApi<SafetyDecision[]>(
    patientId ? `/patients/${patientId}/safety-decisions` : null,
    !isCaregiver,
  );
  const auditState = useApi<AuditEvent[]>(
    patientId ? `/patients/${patientId}/audit?limit=25` : null,
    !isCaregiver,
  );

  const [tab, setTab] = useState<Tab>("agents");
  const [question, setQuestion] = useState(
    "Explain my current recovery plan and what I should watch for.",
  );
  const [asking, setAsking] = useState(false);
  const [explanation, setExplanation] = useState<AiExplanation | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  const agents = agentsState.data?.agents ?? [];
  const evidence = evidenceState.data ?? [];
  const snapshots = snapshotsState.data ?? [];
  const decisions = decisionsState.data ?? [];
  const audit = auditState.data ?? [];
  const aiStatus = aiState.data;
  const canAskAi = role === "patient" || role === "clinician";

  async function askAi() {
    if (!patientId || !selectedUser || !question.trim()) return;
    setAsking(true);
    setAiError(null);
    setExplanation(null);
    try {
      const result = await apiRequest<AiExplanation>("/ai/explain", {
        method: "POST",
        userId: selectedUser.id,
        body: { patientId, question: question.trim() },
      });
      setExplanation(result);
    } catch (err) {
      setAiError(errorMessage(err));
    } finally {
      setAsking(false);
    }
  }

  if (agentsState.loading && !agentsState.data) return <PageSkeleton />;
  if (agentsState.error) {
    return <ErrorState error={agentsState.error} onRetry={agentsState.refresh} />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Intelligence & trust"
        title="Agents, provenance and the model boundary."
        description="CareTwin AI separates deterministic clinical logic from optional model-generated explanations. Every capability below is labeled with what actually works in Phase 1."
        actions={
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="navy">
              <Bot className="h-3 w-3" /> {agents.length} agents
            </Badge>
            <Badge tone={aiStatus?.configured ? "teal" : "amber"}>
              {aiStatus?.configured ? "model ready" : "model unconfigured"}
            </Badge>
          </div>
        }
      />

      <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-care-50 text-care-700 ring-1 ring-care-100">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs font-semibold text-navy-950">
                Deterministic core is always on
              </p>
              <p className="mt-0.5 max-w-2xl text-[0.68rem] leading-relaxed text-slate-500">
                Monitoring, consent, provenance, role boundaries and summaries do not depend
                on an external model. Model explanation is optional and validated before it is
                returned.
              </p>
            </div>
          </div>
          <LinkButton href="/workspace/alerts" variant="secondary" size="sm">
            View alert center
          </LinkButton>
        </div>
      </div>

      <Tabs
        className="mb-4"
        items={[
          { value: "agents", label: "Agent registry", count: agents.length },
          { value: "evidence", label: "Evidence", count: evidence.length },
          { value: "ai", label: "AI boundary" },
          { value: "trust", label: "Safety & history" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "agents" && (
        <div className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {maturityLegend.map((item) => (
              <div
                key={item.status}
                className="rounded-xl border border-slate-200 bg-white p-3"
              >
                <MaturityBadge status={item.status} />
                <p className="mt-1.5 text-[0.64rem] leading-relaxed text-slate-500">
                  {item.detail}
                </p>
              </div>
            ))}
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            {agents.map((agent) => (
              <SectionCard
                key={agent.id}
                title={agent.name}
                description={agent.responsibility}
                icon={<Layers className="h-4 w-4" />}
                action={<MaturityBadge status={agent.phase1Status} />}
              >
                <p className="rounded-lg bg-mist-50 p-2.5 text-[0.68rem] leading-relaxed text-slate-600">
                  {agent.statusLabel}
                </p>
                <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
                  <div>
                    <p className="text-[0.58rem] font-bold uppercase tracking-[0.1em] text-slate-400">
                      Permissions
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {agent.permissions.map((permission) => (
                        <span
                          key={permission}
                          className="rounded bg-care-50 px-1.5 py-0.5 font-mono text-[0.56rem] text-care-800"
                        >
                          {permission}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-[0.58rem] font-bold uppercase tracking-[0.1em] text-slate-400">
                      Interfaces
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {agent.interfaces.map((entry) => (
                        <span
                          key={entry}
                          className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.56rem] text-slate-600"
                        >
                          {entry}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="mt-2.5">
                  <p className="text-[0.58rem] font-bold uppercase tracking-[0.1em] text-slate-400">
                    Boundaries
                  </p>
                  <ul className="mt-1 space-y-1">
                    {agent.boundaries.map((boundary) => (
                      <li
                        key={boundary}
                        className="flex items-start gap-1.5 text-[0.64rem] leading-relaxed text-slate-500"
                      >
                        <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-slate-300" />
                        {boundary}
                      </li>
                    ))}
                  </ul>
                </div>
              </SectionCard>
            ))}
          </div>
          <p className="text-[0.6rem] text-slate-400">
            Registry generated {formatDateTime(agentsState.data?.generatedAt ?? "")}. Status
            reflects Phase 1 implementation, not a roadmap claim.
          </p>
        </div>
      )}

      {tab === "evidence" && (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <SectionCard
            title="Evidence graph"
            description="Page-linked sources behind twin facts. Ambiguous instructions stay awaiting review."
            icon={<Database className="h-4 w-4" />}
            action={<Badge tone="slate">{evidence.length} sources</Badge>}
          >
            {evidenceState.loading ? (
              <LoadingBlock label="Loading evidence" className="py-6" />
            ) : evidenceState.error ? (
              <ErrorState
                error={evidenceState.error}
                onRetry={evidenceState.refresh}
                compact
              />
            ) : evidence.length === 0 ? (
              <EmptyState title="No evidence sources recorded" />
            ) : (
              <div className="space-y-2.5">
                {evidence.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-slate-200/80 bg-white p-3"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <SourceTypeBadge type={item.sourceType} />
                      <VerificationBadge status={item.verificationStatus} />
                      {item.extractedByAi && <Badge tone="violet">AI extracted</Badge>}
                      {item.synthetic && <Badge tone="slate">synthetic</Badge>}
                    </div>
                    <p className="mt-1.5 text-xs font-semibold text-navy-950">
                      {item.title}
                    </p>
                    <p className="mt-0.5 text-[0.64rem] text-slate-400">
                      {item.documentName} ·{" "}
                      <span className="font-mono">{item.pageRef}</span> ·{" "}
                      {formatDateTime(item.capturedAt)}
                    </p>
                    <p className="mt-1.5 line-clamp-3 rounded bg-mist-50 p-2 text-[0.66rem] leading-relaxed text-slate-600">
                      &ldquo;{item.excerpt}&rdquo;
                    </p>
                    <p className="mt-1 font-mono text-[0.56rem] text-slate-300">{item.id}</p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                <ScanLine className="h-4 w-4 text-care-700" /> Provenance rules
              </p>
              <ul className="mt-2 space-y-2 text-[0.68rem] leading-relaxed text-slate-600">
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  Every medication, follow-up and alert carries a source reference or an
                  explicit missing-source marker.
                </li>
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  AI extraction cannot mark itself clinician verified.
                </li>
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  Caregiver views omit clinician-only evidence and notes.
                </li>
              </ul>
            </div>

            <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
              <p className="flex items-center gap-2 text-xs font-semibold text-amber-900">
                <TriangleAlert className="h-4 w-4" /> Ambiguity stays visible
              </p>
              <p className="mt-1.5 text-[0.68rem] leading-relaxed text-amber-900/80">
                Extracted instructions with low confidence are shown as awaiting review rather
                than silently corrected. A clinician must verify them before they are treated
                as confirmed.
              </p>
            </div>
          </div>
        </div>
      )}

      {tab === "ai" && (
        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <SectionCard
            title="Provider-independent explanation boundary"
            description="Optional model output is grounded, server-side and validated. The deterministic product works without it."
            icon={<Brain className="h-4 w-4" />}
            action={
              <Badge tone={aiStatus?.configured ? "teal" : "amber"}>
                {aiStatus?.state ?? "checking"}
              </Badge>
            }
          >
            {aiState.loading ? (
              <LoadingBlock label="Checking AI status" className="py-6" />
            ) : aiState.error ? (
              <ErrorState error={aiState.error} onRetry={aiState.refresh} compact />
            ) : aiStatus ? (
              <div className="space-y-3">
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-lg bg-mist-50 p-3">
                    <p className="text-[0.58rem] uppercase tracking-wide text-slate-400">
                      Provider / model
                    </p>
                    <p className="mt-0.5 text-xs font-semibold text-navy-950">
                      {aiStatus.provider} · {aiStatus.model}
                    </p>
                  </div>
                  <div className="rounded-lg bg-mist-50 p-3">
                    <p className="text-[0.58rem] uppercase tracking-wide text-slate-400">
                      Boundary
                    </p>
                    <p className="mt-0.5 text-xs font-semibold text-navy-950">
                      {aiStatus.serverSideOnly ? "Server-side only" : "Not secured"} ·{" "}
                      {aiStatus.groundedContextReady ? "grounded" : "ungrounded"}
                    </p>
                  </div>
                </div>
                <p className="text-[0.7rem] leading-relaxed text-slate-600">
                  {aiStatus.message}
                </p>

                {!canAskAi ? (
                  <div className="rounded-lg border border-slate-200 bg-mist-50 p-3 text-[0.68rem] leading-relaxed text-slate-500">
                    Caregivers do not hold the <span className="font-mono">summary:read</span>{" "}
                    scope, so model explanation is unavailable for this role. They can still
                    read the shared twin, timeline, schedule and alerts.
                  </div>
                ) : (
                  <div className="rounded-lg border border-slate-200 p-3">
                    <label className="text-[0.62rem] font-semibold text-slate-500">
                      Ask about recorded recovery information
                      <textarea
                        value={question}
                        maxLength={500}
                        rows={3}
                        onChange={(event) => setQuestion(event.target.value)}
                        className="mt-1 block w-full resize-y rounded-lg border border-slate-300 px-2.5 py-2 text-xs text-navy-900 focus:border-care-500 focus:outline-none focus:ring-2 focus:ring-care-500/15"
                      />
                    </label>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => void askAi()}
                        disabled={asking || !aiStatus.configured || !question.trim()}
                        className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-care-600 px-3 text-[0.68rem] font-semibold text-white hover:bg-care-700 disabled:opacity-40"
                      >
                        <Sparkles className="h-3 w-3" />
                        {asking ? "Requesting…" : "Request explanation"}
                      </button>
                      {!aiStatus.configured && (
                        <span className="text-[0.62rem] text-slate-400">
                          Disabled: AI provider is not configured on the server.
                        </span>
                      )}
                    </div>
                    {aiError && (
                      <InlineMessage tone="error" className="mt-2">
                        {aiError}
                      </InlineMessage>
                    )}
                    {explanation && (
                      <div className="mt-3 rounded-lg border border-care-200 bg-care-50/50 p-3">
                        <p className="text-[0.68rem] leading-relaxed text-navy-900">
                          {explanation.answer}
                        </p>
                        <p className="mt-2 text-[0.62rem] text-slate-500">
                          <span className="font-semibold">Uncertainty:</span>{" "}
                          {explanation.uncertainty}
                        </p>
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {explanation.citations.map((citation) => (
                            <span
                              key={citation}
                              className="rounded bg-white px-1.5 py-0.5 font-mono text-[0.56rem] text-slate-500 ring-1 ring-slate-200"
                            >
                              {citation}
                            </span>
                          ))}
                        </div>
                        <p className="mt-1.5 text-[0.58rem] text-slate-400">
                          {explanation.provider} · {explanation.model} · validated before
                          return
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </SectionCard>

          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                <KeyRound className="h-4 w-4 text-care-700" /> Hard boundaries
              </p>
              <ul className="mt-2 space-y-2 text-[0.68rem] leading-relaxed text-slate-600">
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  No diagnosis claims.
                </li>
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  No starting, stopping or changing medication.
                </li>
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  Citations must reference known evidence IDs.
                </li>
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  Synthetic patients only until a production privacy review exists.
                </li>
                <li className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                  Rejected outputs are not shown as guidance.
                </li>
              </ul>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                <Landmark className="h-4 w-4 text-care-700" /> What Phase 1 does not claim
              </p>
              <ul className="mt-2 space-y-1.5 text-[0.66rem] leading-relaxed text-slate-500">
                <li>· No live clinical deployment or regulatory clearance.</li>
                <li>· No production authentication or multi-tenant isolation.</li>
                <li>· No diagnosis, prescription or autonomous clinical action.</li>
                <li>· No model call when no key is configured.</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {tab === "trust" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
            <SectionCard
              title="Twin version history"
              description="Snapshots are written when check-ins, observations or clinical changes occur."
              icon={<GitCommitVertical className="h-4 w-4" />}
              action={<Badge tone="slate">{snapshots.length} snapshots</Badge>}
            >
              {snapshotsState.loading ? (
                <LoadingBlock label="Loading snapshots" className="py-6" />
              ) : snapshotsState.error ? (
                <ErrorState
                  error={snapshotsState.error}
                  onRetry={snapshotsState.refresh}
                  compact
                />
              ) : snapshots.length === 0 ? (
                <EmptyState title="No snapshots recorded" />
              ) : (
                <ol className="relative space-y-2 border-l border-slate-200 pl-3">
                  {snapshots.slice(0, 10).map((snapshot) => (
                    <li key={snapshot.id} className="relative">
                      <span className="absolute -left-[1.05rem] top-1.5 h-1.5 w-1.5 rounded-full bg-care-500" />
                      <p className="text-[0.68rem] font-semibold text-navy-900">
                        v{snapshot.version} · {snapshot.reason}
                      </p>
                      <p className="text-[0.6rem] text-slate-400">
                        {formatDateTime(snapshot.createdAt)} (
                        {formatRelative(snapshot.createdAt)})
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </SectionCard>

            <SectionCard
              title="Safety decision log"
              description="Persisted authorization, provenance and model-output checks."
              icon={<ShieldCheck className="h-4 w-4" />}
            >
              {isCaregiver ? (
                <div className="rounded-lg border border-slate-200 bg-mist-50 p-3 text-[0.68rem] leading-relaxed text-slate-500">
                  Safety decisions are available to the patient and care team only. Caregivers
                  see the outcomes that affect them through alerts and consent status.
                </div>
              ) : decisionsState.loading ? (
                <LoadingBlock label="Loading decisions" className="py-6" />
              ) : decisionsState.error ? (
                <ErrorState
                  error={decisionsState.error}
                  onRetry={decisionsState.refresh}
                  compact
                />
              ) : decisions.length === 0 ? (
                <EmptyState title="No safety decisions recorded" />
              ) : (
                <div className="space-y-2.5">
                  {decisions.slice(0, 6).map((decision) => (
                    <SafetyDecisionCard key={decision.id} decision={decision} compact />
                  ))}
                </div>
              )}
            </SectionCard>
          </div>

          <SectionCard
            title="Audit trail"
            description="Consequential actions with actor, entity and outcome."
            icon={<Fingerprint className="h-4 w-4" />}
            action={<Badge tone="slate">{audit.length} recent</Badge>}
          >
            {isCaregiver ? (
              <AccessRestricted
                title="Audit is restricted for caregivers"
                description="The audit trail is available to the patient and care team only. Caregivers retain attributed observations and their own consent status."
              />
            ) : auditState.loading ? (
              <LoadingBlock label="Loading audit" className="py-6" />
            ) : auditState.error instanceof ApiClientError &&
              auditState.error.status === 403 ? (
              <AccessRestricted
                title="Audit is not available for this role"
                description="The backend refused the audit request. Switch to the patient or clinician identity to inspect it."
              />
            ) : auditState.error ? (
              <ErrorState
                error={auditState.error}
                onRetry={auditState.refresh}
                compact
              />
            ) : audit.length === 0 ? (
              <EmptyState title="No audit entries" />
            ) : (
              <div className="space-y-2">
                {audit.map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-lg border border-slate-200/70 px-3 py-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-1.5">
                      <p className="text-[0.68rem] font-semibold text-navy-900">
                        {entry.action}
                      </p>
                      <Badge tone={entry.outcome === "allowed" ? "teal" : "rose"}>
                        {entry.outcome}
                      </Badge>
                    </div>
                    <p className="mt-0.5 text-[0.6rem] text-slate-400">
                      {entry.actorName} · {entry.actorRole} ·{" "}
                      {formatDateTime(entry.createdAt)}
                    </p>
                    <p className="mt-0.5 truncate font-mono text-[0.55rem] text-slate-300">
                      {entry.entityType}/{entry.entityId}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
      )}
    </div>
  );
}
