"use client";

import { useState } from "react";
import {
  HeartHandshake,
  KeyRound,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import type { ConsentRecord, SafetyDecision } from "@caretwin/contracts";
import { formatDateTime, formatRelative } from "@caretwin/shared";
import { ApiClientError, apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge } from "@/components/ui/badges";
import {
  AccessRestricted,
  EmptyState,
  ErrorState,
  InlineMessage,
  PageSkeleton,
} from "@/components/ui/feedback";
import { SafetyDecisionCard } from "@/components/workspace/records";

const scopeLabels: Record<string, string> = {
  "twin:read": "View recovery twin",
  "timeline:read": "Read timeline events",
  "schedule:read": "Read medication & follow-up schedule",
  "observations:write": "Record caregiver observations",
  "alerts:read": "See safety alerts",
  "consents:read": "See who has access",
  "summary:read": "Read clinical summaries",
  "audit:read": "Read audit trail",
  "*": "All scopes (not granted to caregivers)",
};

function ScopeList({ scopes }: { scopes: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {scopes.map((scope) => (
        <span
          key={scope}
          className="rounded bg-mist-50 px-1.5 py-0.5 font-mono text-[0.58rem] text-slate-600"
          title={scopeLabels[scope] ?? scope}
        >
          {scope}
        </span>
      ))}
    </div>
  );
}

export default function ConsentPage() {
  const { patientId, selectedUser } = useSession();
  const state = useApi<ConsentRecord[]>(
    patientId ? `/patients/${patientId}/consents` : null,
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<SafetyDecision | null>(null);

  const isPatient = selectedUser?.role === "patient";
  const consents = state.data ?? [];

  async function update(consent: ConsentRecord) {
    if (!patientId || !selectedUser) return;
    const nextStatus = consent.status === "granted" ? "revoked" : "granted";
    setBusyId(consent.id);
    setError(null);
    setMessage(null);
    try {
      const result = await apiRequest<{
        consent: ConsentRecord;
        eventId: string;
        safetyDecision: SafetyDecision;
      }>(`/patients/${patientId}/consents/${consent.id}`, {
        method: "PATCH",
        userId: selectedUser.id,
        body: { status: nextStatus, reason: reasons[consent.id] ?? "" },
      });
      setDecision(result.safetyDecision);
      setMessage(
        nextStatus === "granted"
          ? `Sharing restored with ${consent.granteeName}. Timeline event ${result.eventId} recorded.`
          : `Sharing revoked for ${consent.granteeName}. Their next request is refused before twin assembly.`,
      );
      setReasons((current) => ({ ...current, [consent.id]: "" }));
      state.refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  if (!isPatient) {
    return (
      <AccessRestricted
        title="Consent is controlled by the patient"
        description="Only Maya Rao can grant or revoke caregiver sharing. Clinicians can review the resulting access boundaries, but cannot change consent on the patient's behalf."
      />
    );
  }

  if (state.loading && !state.data) return <PageSkeleton />;
  if (state.error instanceof ApiClientError && state.error.status === 403) {
    return <AccessRestricted title="Consent access is not available" />;
  }
  if (state.error) return <ErrorState error={state.error} onRetry={state.refresh} />;

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Patient-controlled sharing"
        title="You decide who sees your recovery."
        description="Consent is scoped, revocable and enforced server-side on every request. Revoking access is recorded in the audit trail: the next caregiver request is refused before the twin is assembled."
        actions={
          <Badge tone="teal">
            {consents.filter((item) => item.status === "granted").length} active grant
            {consents.filter((item) => item.status === "granted").length === 1 ? "" : "s"}
          </Badge>
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

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-4">
          {consents.length === 0 ? (
            <EmptyState
              icon={<HeartHandshake className="h-4 w-4" />}
              title="No caregiver consent records"
              description="No one currently has delegated access to this recovery twin."
            />
          ) : (
            consents.map((consent) => {
              const granted = consent.status === "granted";
              return (
                <SectionCard
                  key={consent.id}
                  title={consent.granteeName}
                  description={`${consent.granteeRelationship} · updated ${formatRelative(
                    consent.updatedAt,
                  )}`}
                  icon={<UserRoundCheck className="h-4 w-4" />}
                  action={
                    <Badge tone={granted ? "teal" : "slate"} dot>
                      {consent.status}
                    </Badge>
                  }
                >
                  <div className="space-y-3">
                    <div>
                      <p className="text-[0.6rem] font-bold uppercase tracking-[0.1em] text-slate-400">
                        Granted scopes
                      </p>
                      <div className="mt-1">
                        <ScopeList scopes={consent.scopes} />
                      </div>
                    </div>

                    <div className="grid gap-2 text-[0.68rem] text-slate-500 sm:grid-cols-2">
                      <p>
                        <span className="font-semibold text-slate-600">Granted</span>
                        <br />
                        {formatDateTime(consent.grantedAt)}
                      </p>
                      <p>
                        <span className="font-semibold text-slate-600">Last change</span>
                        <br />
                        {formatDateTime(consent.updatedAt)}
                      </p>
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-mist-50/60 p-3">
                      <label className="text-[0.62rem] font-semibold text-slate-500">
                        Reason (optional, recorded in the timeline)
                        <input
                          type="text"
                          value={reasons[consent.id] ?? ""}
                          maxLength={500}
                          onChange={(event) =>
                            setReasons((current) => ({
                              ...current,
                              [consent.id]: event.target.value,
                            }))
                          }
                          placeholder={
                            granted
                              ? "e.g. I want to manage my care independently"
                              : "e.g. I need help again after discharge"
                          }
                          className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-navy-900 placeholder:text-slate-400 focus:border-care-500 focus:outline-none focus:ring-2 focus:ring-care-500/15"
                        />
                      </label>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => void update(consent)}
                          disabled={busyId === consent.id}
                          className={
                            granted
                              ? "h-8 rounded-lg border border-rose-300 bg-white px-3 text-[0.68rem] font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                              : "h-8 rounded-lg bg-care-600 px-3 text-[0.68rem] font-semibold text-white hover:bg-care-700 disabled:opacity-50"
                          }
                        >
                          {busyId === consent.id
                            ? "Saving…"
                            : granted
                              ? "Revoke sharing"
                              : "Restore sharing"}
                        </button>
                        <span className="text-[0.6rem] text-slate-400">
                          {granted
                            ? "Their current session loses access immediately."
                            : "They regain only the scopes listed above."}
                        </span>
                      </div>
                    </div>
                  </div>
                </SectionCard>
              );
            })
          )}

          {decision && (
            <SectionCard
              title="Latest consent safety decision"
              description="The server records each consent change with its checks."
              icon={<ShieldCheck className="h-4 w-4" />}
            >
              <SafetyDecisionCard decision={decision} />
            </SectionCard>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
              <KeyRound className="h-4 w-4 text-care-700" /> How scoped access works
            </p>
            <ul className="mt-2 space-y-2 text-[0.68rem] leading-relaxed text-slate-600">
              <li className="flex gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                Each grant lists explicit scopes. A caregiver never automatically receives
                clinician summaries, audit trails or write access.
              </li>
              <li className="flex gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                Revocation is checked before the twin is assembled, so the response is a 403
                boundary rather than a filtered view.
              </li>
              <li className="flex gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-care-500" />
                Consent changes create a timeline event and an audit entry.
              </li>
            </ul>
          </div>

          <div className="rounded-2xl border border-care-200 bg-care-50/60 p-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-care-900">
              <ShieldCheck className="h-4 w-4" /> Synthetic demo
            </p>
            <p className="mt-1.5 text-[0.68rem] leading-relaxed text-care-900/80">
              This consent flow operates on synthetic data. No real patient or caregiver
              identity is represented, and no production authentication is present in Phase 1.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
