"use client";

import { useState } from "react";
import {
  Activity,
  BellRing,
  Brain,
  ClipboardList,
  FileSearch,
  Fingerprint,
  GitCommitVertical,
  Play,
  ShieldCheck,
  SlidersHorizontal,
  Stethoscope,
} from "lucide-react";
import type {
  AuditEvent,
  ClinicalSummary,
  MonitoringRule,
  MonitoringSweepResult,
  RecoveryTwin,
  SafetyAlert,
  SafetyDecision,
} from "@caretwin/contracts";
import { formatDateTime, formatRelative } from "@caretwin/shared";
import { ApiClientError, apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { LinkButton } from "@/components/ui/button";
import {
  Badge,
  SeverityBadge,
  StatusPill,
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
import { AlertCard } from "@/components/workspace/alert-card";
import {
  MedicationRow,
  SafetyDecisionCard,
} from "@/components/workspace/records";

type Tab = "review" | "monitoring" | "safety" | "summary";

export default function ClinicianPage() {
  const { selectedUser, patientId } = useSession();
  const isClinician = selectedUser?.role === "clinician";
  const twinState = useApi<RecoveryTwin>(
    patientId ? `/patients/${patientId}/twin` : null,
    isClinician,
  );
  const alertsState = useApi<SafetyAlert[]>(
    patientId ? `/patients/${patientId}/alerts` : null,
    isClinician,
  );
  const rulesState = useApi<MonitoringRule[]>(
    patientId ? `/patients/${patientId}/monitoring-rules` : null,
    isClinician,
  );
  const decisionsState = useApi<SafetyDecision[]>(
    patientId ? `/patients/${patientId}/safety-decisions` : null,
    isClinician,
  );
  const summaryState = useApi<ClinicalSummary>(
    patientId ? `/patients/${patientId}/clinical-summary` : null,
    isClinician,
  );
  const auditState = useApi<AuditEvent[]>(
    patientId ? `/patients/${patientId}/audit?limit=30` : null,
    isClinician,
  );

  const [tab, setTab] = useState<Tab>("review");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sweep, setSweep] = useState<MonitoringSweepResult | null>(null);
  const [ruleDrafts, setRuleDrafts] = useState<Record<string, string>>({});

  function refreshAll() {
    twinState.refresh();
    alertsState.refresh();
    rulesState.refresh();
    decisionsState.refresh();
    summaryState.refresh();
    auditState.refresh();
  }

  async function acknowledge(alertId: string, note: string) {
    if (!patientId || !selectedUser) return;
    setBusyId(alertId);
    setError(null);
    setMessage(null);
    try {
      const result = await apiRequest<{ eventId: string }>(
        `/patients/${patientId}/alerts/${alertId}/acknowledge`,
        { method: "POST", userId: selectedUser.id, body: { note } },
      );
      setMessage(`Alert acknowledged and linked to event ${result.eventId}.`);
      refreshAll();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  async function verifyMedication(medicationId: string, note: string) {
    if (!patientId || !selectedUser) return;
    setBusyId(medicationId);
    setError(null);
    setMessage(null);
    try {
      const result = await apiRequest<{ twinVersion: number }>(
        `/patients/${patientId}/medications/${medicationId}/verify`,
        { method: "POST", userId: selectedUser.id, body: { note } },
      );
      setMessage(`Instruction verified. Twin version is now v${result.twinVersion}.`);
      refreshAll();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  async function runSweep() {
    if (!patientId || !selectedUser) return;
    setBusyId("sweep");
    setError(null);
    setMessage(null);
    try {
      const result = await apiRequest<MonitoringSweepResult>(
        `/patients/${patientId}/monitoring/run`,
        { method: "POST", userId: selectedUser.id, body: {} },
      );
      setSweep(result);
      setMessage(
        `${result.message} ${result.rulesEvaluated} rules evaluated, gap ${
          result.checkinGapHours ?? "n/a"
        } h.`,
      );
      refreshAll();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  async function updateRule(rule: MonitoringRule, body: { threshold?: number; enabled?: boolean }) {
    if (!patientId || !selectedUser) return;
    setBusyId(rule.id);
    setError(null);
    setMessage(null);
    try {
      const result = await apiRequest<{
        rule: MonitoringRule;
        safetyDecision: SafetyDecision;
      }>(`/patients/${patientId}/monitoring-rules/${rule.id}`, {
        method: "PATCH",
        userId: selectedUser.id,
        body,
      });
      setMessage(
        `Rule ${result.rule.code} updated. Safety decision ${result.safetyDecision.outcome}.`,
      );
      setRuleDrafts((current) => {
        const next = { ...current };
        delete next[rule.id];
        return next;
      });
      rulesState.refresh();
      decisionsState.refresh();
      auditState.refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  if (!isClinician) {
    return (
      <AccessRestricted
        title="Clinical workspace requires a clinician identity"
        description="The review queue, monitoring rules, clinical summary, audit trail and safety decisions are restricted to the clinician role. Switch to Dr. Nandini Iyer in demo access to inspect them."
        showConsentLink={selectedUser?.role === "patient"}
      />
    );
  }

  if (twinState.loading && !twinState.data) return <PageSkeleton />;
  if (twinState.error instanceof ApiClientError && twinState.error.status === 403) {
    return <AccessRestricted title="Clinical access is not available" />;
  }
  if (twinState.error) return <ErrorState error={twinState.error} onRetry={twinState.refresh} />;
  if (!twinState.data) return <PageSkeleton />;

  const twin = twinState.data;
  const alerts = alertsState.data ?? [];
  const openAlerts = alerts.filter((alert) => alert.status === "open");
  const awaitingMeds = twin.medications.filter(
    (medication) =>
      medication.verificationStatus === "awaiting_review" ||
      medication.verificationStatus === "document_extracted",
  );
  const rules = rulesState.data ?? [];
  const decisions = decisionsState.data ?? [];
  const audit = auditState.data ?? [];
  const reviewCount = openAlerts.length + awaitingMeds.length;

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Clinical overview"
        title={`${twin.patient.fullName} · reviewed from the evidence up.`}
        description="Acknowledge rule alerts, confirm ambiguous instructions, run deterministic monitoring and inspect the safety decision log. No action here creates a diagnosis or prescription."
        actions={
          <>
            <StatusPill status={twin.status} />
            <LinkButton href="/workspace/intelligence" variant="secondary" size="sm">
              <Brain className="h-3.5 w-3.5" /> AI & audit boundary
            </LinkButton>
          </>
        }
      />

      {message && (
        <InlineMessage tone="success" className="mb-4">
          {message}
        </InlineMessage>
      )}
      {error && (
        <InlineMessage tone="error" className="mb-4">
          {error}
        </InlineMessage>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Review queue",
            value: reviewCount,
            hint: `${openAlerts.length} alerts · ${awaitingMeds.length} instructions`,
            icon: ClipboardList,
            tone: reviewCount ? "amber" : "teal",
          },
          {
            label: "Twin status",
            value: twin.status.replaceAll("_", " "),
            hint: `Version ${twin.version} · ${formatRelative(twin.updatedAt)}`,
            icon: Activity,
            tone: twin.status === "on_track" ? "teal" : "rose",
          },
          {
            label: "Milestones",
            value: `${twin.progress.completed}/${twin.progress.total}`,
            hint: "Documented recovery checkpoints",
            icon: ShieldCheck,
            tone: "blue",
          },
          {
            label: "Evidence awaiting review",
            value: twin.dataQuality.awaitingReview,
            hint: `${twin.dataQuality.totalEvidence} total linked sources`,
            icon: FileSearch,
            tone: twin.dataQuality.awaitingReview ? "amber" : "teal",
          },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <p className="text-[0.6rem] font-bold uppercase tracking-[0.12em] text-slate-400">
                {item.label}
              </p>
              <item.icon className="h-4 w-4 text-slate-300" />
            </div>
            <p className="mt-1.5 text-lg font-semibold capitalize text-navy-950">
              {item.value}
            </p>
            <p className="mt-0.5 text-[0.64rem] text-slate-500">{item.hint}</p>
          </div>
        ))}
      </div>

      <Tabs
        className="mb-4"
        items={[
          { value: "review", label: "Review queue", count: reviewCount },
          { value: "monitoring", label: "Monitoring rules", count: rules.length },
          { value: "safety", label: "Safety & audit", count: decisions.length },
          { value: "summary", label: "Clinical summary" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "review" && (
        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <SectionCard
            title="Open rule alerts"
            description="Deterministic flags with provenance. Acknowledging is a review action, not a diagnosis."
            icon={<BellRing className="h-4 w-4" />}
            action={<Badge tone={openAlerts.length ? "rose" : "teal"}>{openAlerts.length} open</Badge>}
          >
            {alertsState.loading ? (
              <LoadingBlock label="Loading alerts" className="py-6" />
            ) : openAlerts.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck className="h-4 w-4" />}
                title="No open alerts"
                description="All deterministic rule alerts have been acknowledged or none are open."
              />
            ) : (
              <div className="space-y-2.5">
                {openAlerts.map((alert) => (
                  <AlertCard
                    key={alert.id}
                    alert={alert}
                    canAcknowledge
                    onAcknowledge={(note) => void acknowledge(alert.id, note)}
                    acknowledging={busyId === alert.id}
                  />
                ))}
              </div>
            )}
          </SectionCard>

          <div className="space-y-4">
            <SectionCard
              title="Instructions awaiting review"
              description="Review the extracted text against its page reference before verifying."
              icon={<ClipboardList className="h-4 w-4" />}
            >
              {awaitingMeds.length === 0 ? (
                <EmptyState
                  icon={<ShieldCheck className="h-4 w-4" />}
                  title="No instructions awaiting review"
                />
              ) : (
                <div className="space-y-2.5">
                  {awaitingMeds.map((medication) => (
                    <MedicationRow
                      key={medication.id}
                      medication={medication}
                      canVerify
                      onVerify={(note) => void verifyMedication(medication.id, note)}
                      verifying={busyId === medication.id}
                    />
                  ))}
                </div>
              )}
            </SectionCard>

            <SectionCard
              title="Caregiver observations"
              description="Context from authorized caregivers, attributed and unverified."
              icon={<Stethoscope className="h-4 w-4" />}
            >
              {twin.observations.length === 0 ? (
                <EmptyState title="No observations recorded" />
              ) : (
                <div className="space-y-2">
                  {twin.observations.slice(0, 4).map((observation) => (
                    <div key={observation.id} className="rounded-lg bg-mist-50 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[0.68rem] font-semibold text-navy-900">
                          {observation.caregiverName} ·{" "}
                          {observation.category.replaceAll("_", " ")}
                        </p>
                        <VerificationBadge status={observation.verificationStatus} />
                      </div>
                      <p className="mt-1 text-[0.7rem] leading-relaxed text-slate-600">
                        {observation.note}
                      </p>
                      <p className="mt-1 text-[0.6rem] text-slate-400">
                        {formatDateTime(observation.observedAt)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
        </div>
      )}

      {tab === "monitoring" && (
        <div className="space-y-4">
          <SectionCard
            title="Deterministic monitoring sweep"
            description="Evaluates the check-in gap rule. Alert creation is deterministic and recorded as an event."
            icon={<Play className="h-4 w-4" />}
            action={
              <button
                onClick={() => void runSweep()}
                disabled={busyId === "sweep"}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-care-600 px-3 text-xs font-semibold text-white hover:bg-care-700 disabled:opacity-60"
              >
                <Play className="h-3 w-3" />
                {busyId === "sweep" ? "Running…" : "Run sweep"}
              </button>
            }
          >
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-lg bg-mist-50 p-3">
                <p className="text-[0.6rem] uppercase tracking-wide text-slate-400">Rules</p>
                <p className="mt-0.5 text-lg font-semibold text-navy-950">
                  {sweep?.rulesEvaluated ?? rules.length}
                </p>
              </div>
              <div className="rounded-lg bg-mist-50 p-3">
                <p className="text-[0.6rem] uppercase tracking-wide text-slate-400">
                  Check-in gap
                </p>
                <p className="mt-0.5 text-lg font-semibold text-navy-950">
                  {sweep?.checkinGapHours != null ? `${sweep.checkinGapHours} h` : "—"}
                </p>
              </div>
              <div className="rounded-lg bg-mist-50 p-3">
                <p className="text-[0.6rem] uppercase tracking-wide text-slate-400">
                  New alerts
                </p>
                <p className="mt-0.5 text-lg font-semibold text-navy-950">
                  {sweep?.alertsCreated.length ?? 0}
                </p>
              </div>
            </div>
            {sweep && (
              <div className="mt-3 space-y-2">
                <p className="text-[0.68rem] leading-relaxed text-slate-500">
                  Evaluated {formatDateTime(sweep.evaluatedAt)}.{" "}
                  {sweep.alertsCreated.length === 0
                    ? "No new alerts were created."
                    : `${sweep.alertsCreated.length} alert(s) require review.`}
                </p>
                {sweep.alertsCreated.map((alert) => (
                  <AlertCard key={alert.id} alert={alert} />
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard
            title="Clinician-configured rules"
            description="Thresholds live in the database. Changing one is a clinician action with a safety decision and audit entry."
            icon={<SlidersHorizontal className="h-4 w-4" />}
          >
            {rulesState.loading ? (
              <LoadingBlock label="Loading rules" className="py-6" />
            ) : rules.length === 0 ? (
              <EmptyState title="No monitoring rules" />
            ) : (
              <div className="space-y-2.5">
                {rules.map((rule) => {
                  const draft = ruleDrafts[rule.id] ?? String(rule.threshold);
                  const isBusy = busyId === rule.id;
                  return (
                    <div
                      key={rule.id}
                      className="rounded-xl border border-slate-200/80 bg-white p-3.5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-xs font-semibold text-navy-950">
                            {rule.name}
                          </p>
                          <p className="mt-0.5 text-[0.64rem] text-slate-500">
                            <span className="font-mono">{rule.code}</span> ·{" "}
                            {rule.kind.replaceAll("_", " ")} · updated{" "}
                            {formatRelative(rule.updatedAt)}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <SeverityBadge severity={rule.severity} />
                          <Badge tone={rule.enabled ? "teal" : "slate"}>
                            {rule.enabled ? "enabled" : "disabled"}
                          </Badge>
                        </div>
                      </div>
                      <p className="mt-1.5 text-[0.68rem] leading-relaxed text-slate-500">
                        {rule.description}
                      </p>
                      <div className="mt-2.5 flex flex-wrap items-end gap-2">
                        <label className="text-[0.62rem] font-semibold text-slate-500">
                          Threshold
                          <input
                            type="number"
                            value={draft}
                            min={0}
                            step="0.1"
                            onChange={(event) =>
                              setRuleDrafts((current) => ({
                                ...current,
                                [rule.id]: event.target.value,
                              }))
                            }
                            className="mt-0.5 block w-24 rounded-lg border border-slate-300 px-2 py-1.5 font-mono text-xs focus:border-care-500 focus:outline-none focus:ring-2 focus:ring-care-500/15"
                          />
                        </label>
                        <button
                          onClick={() =>
                            void updateRule(rule, { threshold: Number(draft) })
                          }
                          disabled={isBusy || Number(draft) === rule.threshold}
                          className="h-8 rounded-lg border border-slate-300 px-2.5 text-[0.68rem] font-semibold text-navy-900 hover:bg-slate-50 disabled:opacity-40"
                        >
                          Save threshold
                        </button>
                        <button
                          onClick={() => void updateRule(rule, { enabled: !rule.enabled })}
                          disabled={isBusy}
                          className="h-8 rounded-lg border border-slate-300 px-2.5 text-[0.68rem] font-semibold text-navy-900 hover:bg-slate-50 disabled:opacity-40"
                        >
                          {rule.enabled ? "Disable" : "Enable"}
                        </button>
                        <span className="ml-auto text-[0.6rem] text-slate-400">
                          Configured by {rule.configuredBy}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>
        </div>
      )}

      {tab === "safety" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard
            title="Safety decisions"
            description="Every consequential operation persists the checks that allowed or rejected it."
            icon={<ShieldCheck className="h-4 w-4" />}
          >
            {decisionsState.loading ? (
              <LoadingBlock label="Loading decisions" className="py-6" />
            ) : decisions.length === 0 ? (
              <EmptyState title="No safety decisions recorded" />
            ) : (
              <div className="space-y-2.5">
                {decisions.slice(0, 8).map((decision) => (
                  <SafetyDecisionCard key={decision.id} decision={decision} compact />
                ))}
              </div>
            )}
          </SectionCard>

          <div className="space-y-4">
            <SectionCard
              title="Audit trail"
              description="What was touched, by whom, with what outcome."
              icon={<Fingerprint className="h-4 w-4" />}
              action={<LinkButton href="/workspace/intelligence" variant="ghost" size="sm">Full audit</LinkButton>}
            >
              {auditState.loading ? (
                <LoadingBlock label="Loading audit" className="py-6" />
              ) : audit.length === 0 ? (
                <EmptyState title="No audit entries" />
              ) : (
                <div className="space-y-2">
                  {audit.slice(0, 8).map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-start justify-between gap-2 border-b border-slate-100 pb-2 last:border-0 last:pb-0"
                    >
                      <div>
                        <p className="text-[0.68rem] font-semibold text-navy-900">
                          {entry.action}
                        </p>
                        <p className="text-[0.6rem] text-slate-400">
                          {entry.actorName} · {entry.actorRole} ·{" "}
                          {formatDateTime(entry.createdAt)}
                        </p>
                      </div>
                      <Badge tone={entry.outcome === "allowed" ? "teal" : "rose"}>
                        {entry.outcome}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>

            <SectionCard
              title="Snapshot chain"
              description="Versioned state for audit and review."
              icon={<GitCommitVertical className="h-4 w-4" />}
            >
              <p className="text-[0.7rem] leading-relaxed text-slate-500">
                Twin v{twin.version} · {twin.progress.completed} of{" "}
                {twin.progress.total} milestones complete. Open the twin to inspect every
                snapshot reason.
              </p>
              <LinkButton href="/workspace/twin" variant="secondary" size="sm" className="mt-2">
                Open twin history
              </LinkButton>
            </SectionCard>
          </div>
        </div>
      )}

      {tab === "summary" && (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <SectionCard
            title="Deterministic clinical summary"
            description="Generated from recorded data with evidence references. Not an AI diagnosis."
            icon={<ClipboardList className="h-4 w-4" />}
            action={
              <div className="flex items-center gap-1.5">
                <Badge tone="blue">deterministic</Badge>
                <button
                  onClick={summaryState.refresh}
                  className="text-[0.66rem] font-semibold text-care-700 hover:text-care-800"
                >
                  Regenerate
                </button>
              </div>
            }
          >
            {summaryState.loading ? (
              <LoadingBlock label="Generating summary" className="py-6" />
            ) : summaryState.error ? (
              <ErrorState
                error={summaryState.error}
                onRetry={summaryState.refresh}
                compact
              />
            ) : summaryState.data ? (
              <div className="space-y-3">
                {summaryState.data.sections.map((section) => (
                  <div
                    key={section.title}
                    className="rounded-lg border border-slate-200 p-3"
                  >
                    <p className="text-[0.68rem] font-bold uppercase tracking-[0.1em] text-care-700">
                      {section.title}
                    </p>
                    <p className="mt-1 text-[0.72rem] leading-relaxed text-slate-700">
                      {section.finding}
                    </p>
                    {section.evidenceRefs.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {section.evidenceRefs.map((ref) => (
                          <span
                            key={ref}
                            className="rounded bg-mist-50 px-1.5 py-0.5 font-mono text-[0.58rem] text-slate-500"
                          >
                            {ref}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                <p className="text-[0.6rem] text-slate-400">
                  Generated {formatDateTime(summaryState.data.generatedAt)} ·{" "}
                  {summaryState.data.mode}
                </p>
              </div>
            ) : null}
          </SectionCard>

          <div className="space-y-4">
            <SectionCard
              title="Safety notes"
              description="Included with every generated summary."
              icon={<ShieldCheck className="h-4 w-4" />}
            >
              <ul className="space-y-2">
                {(summaryState.data?.safetyNotes ?? []).map((note) => (
                  <li key={note} className="flex items-start gap-2 text-[0.68rem] leading-relaxed text-slate-600">
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                    {note}
                  </li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard
              title="Evidence used"
              description="Open the evidence graph for page-level excerpts."
              icon={<FileSearch className="h-4 w-4" />}
            >
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(twin.dataQuality.sourcesByType).map(([type, count]) => (
                  <Badge key={type} tone="slate">
                    {type.replaceAll("_", " ")} · {count}
                  </Badge>
                ))}
              </div>
              <LinkButton href="/workspace/twin" variant="secondary" size="sm" className="mt-3">
                Inspect evidence
              </LinkButton>
            </SectionCard>
          </div>
        </div>
      )}
    </div>
  );
}
