"use client";

import Link from "next/link";
import {
  BellRing,
  CalendarClock,
  ClipboardList,
  Eye,
  HeartHandshake,
  HeartPulse,
  LockKeyhole,
  Pill,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { RecoveryTwin } from "@caretwin/contracts";
import { formatDateTime, formatRelative } from "@caretwin/shared";
import { ApiClientError } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { LinkButton } from "@/components/ui/button";
import {
  Badge,
  SeverityBadge,
  SourceChip,
  StatusPill,
  VerificationBadge,
} from "@/components/ui/badges";
import { ProgressRing } from "@/components/ui/progress";
import {
  AccessRestricted,
  EmptyState,
  ErrorState,
  PageSkeleton,
} from "@/components/ui/feedback";
import { ObservationForm } from "@/components/workspace/observation-form";
import { MedicationRow } from "@/components/workspace/records";

const sharedScopes = [
  ["twin:read", "Recovery twin"],
  ["timeline:read", "Recovery timeline"],
  ["schedule:read", "Medications & follow-ups"],
  ["observations:write", "Submit observations"],
  ["alerts:read", "Safety alerts"],
  ["consents:read", "Consent record"],
];

export default function CaregiverPage() {
  const { selectedUser, patientId } = useSession();
  const state = useApi<RecoveryTwin>(
    patientId ? `/patients/${patientId}/twin` : null,
    selectedUser?.role === "caregiver",
  );

  if (state.loading && !state.data) return <PageSkeleton />;

  if (state.error instanceof ApiClientError && state.error.status === 403) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          eyebrow="Caregiver workspace"
          title="No active sharing for this caregiver."
          description="This is the expected API-level consent boundary, not a loading failure. The patient controls caregiver scopes."
        />
        <AccessRestricted
          title="Sharing is revoked for this identity"
          description={`${selectedUser?.name ?? "This caregiver"} still has a demo account, but the patient's active consent is missing or revoked. The backend returns 403 before any twin data is assembled, so the interface cannot leak hidden information.`}
        />
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {[
            {
              icon: LockKeyhole,
              title: "Enforced server-side",
              body: "The 403 comes from the FastAPI access layer, not a hidden frontend button.",
            },
            {
              icon: ShieldCheck,
              title: "Scoped, not all-or-nothing",
              body: "Active caregivers receive only the intersection of relationship and consent scopes.",
            },
            {
              icon: Users,
              title: "Patient-controlled",
              body: "Switch to Maya to see the consent record and restore or revoke sharing.",
            },
          ].map((item) => (
            <div key={item.title} className="rounded-xl border border-slate-200 bg-white p-4">
              <item.icon className="h-4 w-4 text-care-700" />
              <p className="mt-2 text-xs font-semibold text-navy-950">{item.title}</p>
              <p className="mt-1 text-[0.68rem] leading-relaxed text-slate-500">
                {item.body}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <LinkButton href="/demo" variant="secondary" size="sm">
            Switch demo role
          </LinkButton>
          <LinkButton href="/workspace/consent" variant="ghost" size="sm">
            Open consent view
          </LinkButton>
        </div>
      </div>
    );
  }

  if (state.error) return <ErrorState error={state.error} onRetry={state.refresh} />;
  if (!state.data) return <PageSkeleton />;

  const twin = state.data;
  const latestCheckin = twin.recentCheckIns[0];
  const openAlerts = twin.openAlerts;
  const upcoming = twin.followUps.filter((item) => item.status !== "completed");

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Caregiver overview"
        title={`Supporting ${twin.patient.preferredName}'s recovery.`}
        description="A consent-scoped view for practical support. Observations you record are attributed to you and never treated as clinical verification."
        actions={
          <>
            <LinkButton href="/workspace/timeline" variant="secondary" size="sm">
              <Eye className="h-3.5 w-3.5" /> Shared timeline
            </LinkButton>
            <LinkButton href="/workspace/consent" variant="ghost" size="sm">
              What is shared
            </LinkButton>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1.45fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={twin.status} />
                <Badge tone="violet">Caregiver-scoped</Badge>
                <Badge tone="slate">Twin v{twin.version}</Badge>
              </div>
              <p className="mt-3 font-display text-xl font-semibold text-navy-950">
                {twin.patient.fullName} · Day {twin.patient.postDischargeDay}
              </p>
              <p className="mt-1 text-xs text-slate-600">{twin.patient.condition}</p>
              <p className="mt-2 max-w-lg text-[0.7rem] leading-relaxed text-slate-500">
                {twin.visibility.note}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="teal">{twin.progress.completed}/{twin.progress.total} milestones</Badge>
                <Badge tone={openAlerts.length ? "amber" : "teal"}>
                  {openAlerts.length} open alert{openAlerts.length === 1 ? "" : "s"}
                </Badge>
                {latestCheckin && (
                  <Badge tone="slate">
                    Last check-in {formatRelative(latestCheckin.submittedAt)}
                  </Badge>
                )}
              </div>
            </div>
            <ProgressRing
              completed={twin.progress.completed}
              total={twin.progress.total}
              status={twin.status}
              size={92}
            />
          </div>

          <div className="mt-4 grid gap-2 border-t border-slate-100 pt-4 sm:grid-cols-2">
            <div className="rounded-lg bg-mist-50 p-3">
              <p className="flex items-center gap-1.5 text-[0.6rem] font-bold uppercase tracking-[0.12em] text-slate-500">
                <CalendarClock className="h-3 w-3" /> Next follow-up
              </p>
              <p className="mt-1 text-xs font-semibold text-navy-950">
                {twin.nextFollowUp?.title ?? "None recorded"}
              </p>
              {twin.nextFollowUp && (
                <p className="mt-0.5 text-[0.66rem] text-slate-500">
                  {formatDateTime(twin.nextFollowUp.scheduledFor)}
                </p>
              )}
            </div>
            <div className="rounded-lg bg-mist-50 p-3">
              <p className="flex items-center gap-1.5 text-[0.6rem] font-bold uppercase tracking-[0.12em] text-slate-500">
                <HeartHandshake className="h-3 w-3" /> Your role
              </p>
              <p className="mt-1 text-xs font-semibold text-navy-950">
                Practical support & observation
              </p>
              <p className="mt-0.5 text-[0.66rem] text-slate-500">
                You cannot author patient check-ins or verify clinical instructions.
              </p>
            </div>
          </div>
        </div>

        <SectionCard
          title="What is shared with you"
          description="The intersection of the care relationship and active patient consent."
          icon={<ShieldCheck className="h-4 w-4" />}
        >
          <div className="space-y-1.5">
            {sharedScopes.map(([scope, label]) => (
              <div
                key={scope}
                className="flex items-center justify-between gap-2 rounded-lg bg-mist-50 px-3 py-1.5"
              >
                <span className="text-[0.68rem] font-medium text-navy-900">{label}</span>
                <Badge tone="teal">granted</Badge>
              </div>
            ))}
            <p className="pt-1 text-[0.64rem] leading-relaxed text-slate-400">
              Audit trail and clinical safety-decision logs are not included in caregiver
              scope. The API enforces that boundary.
            </p>
          </div>
        </SectionCard>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.35fr]">
        <SectionCard
          title="Record an observation"
          description="Something you noticed — not a diagnosis or a clinical instruction."
          icon={<ClipboardList className="h-4 w-4" />}
        >
          <ObservationForm onSubmitted={state.refresh} />
        </SectionCard>

        <div className="space-y-4">
          <SectionCard
            title="Shared safety alerts"
            description="You can see open concerns but cannot acknowledge or resolve them."
            icon={<BellRing className="h-4 w-4" />}
          >
            {openAlerts.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck className="h-4 w-4" />}
                title="No open alerts"
                description="No deterministic rule has produced an open alert."
              />
            ) : (
              <div className="space-y-2">
                {openAlerts.map((alert) => (
                  <div key={alert.id} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="text-xs font-semibold text-navy-950">{alert.title}</p>
                      <SeverityBadge severity={alert.severity} />
                    </div>
                    <p className="mt-1 text-[0.68rem] leading-relaxed text-slate-600">
                      {alert.rationale}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <SourceChip evidence={alert.evidence} />
                      <span className="text-[0.6rem] text-slate-400">
                        {formatDateTime(alert.createdAt)}
                      </span>
                    </div>
                  </div>
                ))}
                <p className="text-[0.64rem] leading-relaxed text-slate-400">
                  If you are worried now, contact the care team or emergency services rather
                  than waiting for app review.
                </p>
              </div>
            )}
          </SectionCard>

          <SectionCard
            title="Latest patient check-in"
            description={
              latestCheckin
                ? `Submitted ${formatDateTime(latestCheckin.submittedAt)}`
                : "No check-in yet"
            }
            icon={<HeartPulse className="h-4 w-4" />}
            action={
              latestCheckin ? (
                <VerificationBadge status={latestCheckin.verificationStatus} />
              ) : undefined
            }
          >
            {latestCheckin ? (
              <div className="space-y-2">
                <div className="grid grid-cols-3 gap-2 text-center">
                  {[
                    ["Pain", `${latestCheckin.painScore}/10`],
                    ["Breathless", `${latestCheckin.breathlessnessScore}/10`],
                    [
                      "Temp",
                      latestCheckin.temperatureC ? `${latestCheckin.temperatureC}°C` : "—",
                    ],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg bg-mist-50 py-1.5">
                      <p className="text-[0.55rem] uppercase tracking-wide text-slate-400">
                        {label}
                      </p>
                      <p className="text-xs font-semibold text-navy-950">{value}</p>
                    </div>
                  ))}
                </div>
                <p className="text-[0.7rem] leading-relaxed text-slate-600">
                  Feeling {latestCheckin.overallFeeling} · adherence{" "}
                  {latestCheckin.adherence.replaceAll("_", " ")}
                  {latestCheckin.missedDoses
                    ? ` · ${latestCheckin.missedDoses} missed`
                    : ""}
                </p>
                {latestCheckin.notes && (
                  <p className="rounded-lg bg-mist-50 px-2.5 py-2 text-[0.68rem] italic text-slate-500">
                    &ldquo;{latestCheckin.notes}&rdquo;
                  </p>
                )}
              </div>
            ) : (
              <EmptyState title="No patient check-in yet" />
            )}
          </SectionCard>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SectionCard
          title="Recent observations"
          description="Attributed context from caregivers."
          icon={<Users className="h-4 w-4" />}
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
                    <span className="text-[0.6rem] text-slate-400">
                      {formatRelative(observation.observedAt)}
                    </span>
                  </div>
                  <p className="mt-1 text-[0.7rem] leading-relaxed text-slate-600">
                    {observation.note}
                  </p>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Shared medication schedule"
          description="Read-only. You cannot verify instructions."
          icon={<Pill className="h-4 w-4" />}
        >
          <div className="space-y-2.5">
            {twin.medications.map((medication) => (
              <MedicationRow key={medication.id} medication={medication} />
            ))}
          </div>
        </SectionCard>
      </div>

      <div className="mt-4 flex flex-col gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-[0.68rem] leading-relaxed text-slate-500 sm:flex-row sm:items-center sm:justify-between">
        <p>
          Shared schedule includes{" "}
          {upcoming.length > 0
            ? `${upcoming.length} upcoming follow-up${upcoming.length === 1 ? "" : "s"}`
            : "no upcoming follow-ups"}{" "}
          and {twin.medications.length} medication instruction
          {twin.medications.length === 1 ? "" : "s"}.
        </p>
        <Link
          href="/workspace/schedule"
          className="text-[0.68rem] font-semibold text-care-700 hover:text-care-800"
        >
          Open full shared schedule
        </Link>
      </div>
    </div>
  );
}
