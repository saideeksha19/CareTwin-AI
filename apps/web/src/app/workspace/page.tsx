"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowUpRight,
  BellRing,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  FileText,
  HeartPulse,
  Orbit,
  ShieldCheck,
  Sparkles,
  Users,
  Waves,
} from "lucide-react";
import type {
  ConsentRecord,
  RecoveryTwin,
  TimelineResponse,
} from "@caretwin/contracts";
import { formatDate, formatRelative } from "@caretwin/shared";
import { useSession } from "@/lib/session";
import { workspaceHome } from "@/lib/nav";
import { useApi } from "@/lib/use-api";
import { Card, SectionCard } from "@/components/ui/cards";
import { LinkButton } from "@/components/ui/button";
import {
  Badge,
  SeverityBadge,
  StatusPill,
  VerificationBadge,
} from "@/components/ui/badges";
import { ProgressBar, ProgressRing } from "@/components/ui/progress";
import {
  EmptyState,
  ErrorState,
  PageSkeleton,
  SafetyFooterNote,
} from "@/components/ui/feedback";
import { TwinVideo } from "@/components/twin/twin-video";
import {
  type DocumentSummary,
  type GuidanceRecord,
} from "@/lib/documents";

function StatChip({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-care-50 text-care-600">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[0.52rem] font-semibold uppercase tracking-[0.14em] text-slate-500">
          {label}
        </p>
        <p className="truncate text-[0.72rem] font-semibold text-navy-900">{value}</p>
      </div>
    </div>
  );
}

export default function PatientOverviewPage() {
  const { selectedUser, patientId } = useSession();
  const router = useRouter();
  const twinState = useApi<RecoveryTwin>(patientId ? `/patients/${patientId}/twin` : null);
  const timelineState = useApi<TimelineResponse>(
    patientId ? `/patients/${patientId}/timeline?limit=6` : null,
  );
  const documentsState = useApi<DocumentSummary[]>(
    patientId ? `/patients/${patientId}/documents` : null,
  );
  const consentsState = useApi<ConsentRecord[]>(
    patientId ? `/patients/${patientId}/consents` : null,
  );
  const guidanceState = useApi<GuidanceRecord[]>(
    patientId ? `/patients/${patientId}/guidance/history` : null,
  );

  useEffect(() => {
    if (selectedUser && selectedUser.role !== "patient") {
      router.replace(workspaceHome(selectedUser.role));
    }
  }, [selectedUser, router]);

  if (!selectedUser || selectedUser.role !== "patient") {
    return <PageSkeleton />;
  }
  if (twinState.loading && !twinState.data) return <PageSkeleton />;
  if (twinState.error) {
    return <ErrorState error={twinState.error} onRetry={twinState.refresh} />;
  }
  if (!twinState.data) return <PageSkeleton />;

  const twin = twinState.data;
  const latestCheckin = twin.recentCheckIns[0];
  const latestObservation = twin.observations[0];
  const documents = documentsState.data ?? [];
  const latestDoc = documents[0];
  const consents = consentsState.data ?? [];
  const activeConsents = consents.filter((record) => record.status === "granted");
  const guidanceRun = guidanceState.data?.[0];
  const verifiedCount = twin.dataQuality.verifiedEvidence;
  const totalEvidence = twin.dataQuality.totalEvidence;
  const openMilestones = twin.milestones.filter(
    (item) => item.status === "in_progress" || item.status === "pending",
  );

  return (
    <div className="space-y-4">
      {/* ------------------------------------------------------------ header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-[0.58rem] font-semibold uppercase tracking-[0.22em] text-care-600">
            <span className="h-px w-6 bg-care-300" aria-hidden="true" />
            Patient dashboard
          </p>
          <h1 className="mt-2 font-display text-[1.7rem] font-semibold leading-tight tracking-tight text-navy-950 md:text-[2.1rem]">
            Your recovery <span className="text-care-700">overview.</span>
          </h1>
          <p className="mt-1.5 max-w-2xl text-[0.82rem] leading-relaxed text-slate-500">
            {twin.patient.fullName} · {twin.plan.title} · day{" "}
            {twin.patient.postDischargeDay} post-discharge. Every panel below is read
            from the documented record — synthetic demo data only.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <LinkButton href="/workspace/twin" variant="secondary" size="sm">
            <Orbit className="h-3.5 w-3.5" /> Open digital twin
          </LinkButton>
          <LinkButton href="/workspace/check-in" size="sm">
            <ClipboardCheck className="h-3.5 w-3.5" /> Daily check-in
          </LinkButton>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <StatChip
          label="Twin status"
          value={
            twin.status === "on_track"
              ? "On track · monitoring active"
              : twin.status === "needs_attention"
                ? `Needs attention · ${twin.openAlerts.length} open alerts`
                : "Critical · review required"
          }
          icon={<Waves className="h-4 w-4" />}
        />
        <StatChip label="Twin version" value={`v${twin.version} · ${formatRelative(twin.updatedAt)}`} icon={<Orbit className="h-4 w-4" />} />
        <StatChip label="Open alerts" value={`${twin.openAlerts.length} requiring human review`} icon={<BellRing className="h-4 w-4" />} />
        <StatChip label="Clinician verified" value={`${verifiedCount} of ${totalEvidence} evidence items`} icon={<ShieldCheck className="h-4 w-4" />} />
      </div>

      {/* --------------------------------------------------------------- grid */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,16.5rem)_minmax(0,1fr)_minmax(0,18.5rem)]">
        {/* left rail */}
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[0.55rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Patient twin
              </p>
              <StatusPill status={twin.status} />
            </div>
            <div className="mt-3 flex items-center gap-3">
              <span className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-care-50 text-sm font-bold text-care-800 ring-1 ring-care-200">
                {twin.patient.fullName
                  .split(" ")
                  .map((part) => part[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-navy-950">
                  {twin.patient.fullName}
                </p>
                <p className="truncate font-mono text-[0.62rem] text-slate-500">
                  {twin.patient.mrn}
                </p>
              </div>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-[0.66rem]">
              {[
                ["Age", `${twin.patient.age}`],
                ["Sex", twin.patient.sex],
                ["Condition", twin.patient.condition],
                ["Language", twin.patient.primaryLanguage],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-mist-100 px-2 py-1.5">
                  <dt className="text-[0.52rem] uppercase tracking-[0.12em] text-slate-500">
                    {label}
                  </dt>
                  <dd className="mt-0.5 truncate font-medium capitalize text-navy-800">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 flex items-center justify-between rounded-lg border border-slate-100 bg-mist-50 px-2.5 py-2">
              <span className="text-[0.62rem] text-slate-500">Care plan progress</span>
              <span className="font-mono text-[0.68rem] font-semibold text-care-700">
                {twin.progress.completed}/{twin.progress.total}
              </span>
            </div>
            <ProgressBar
              className="mt-2"
              value={twin.progress.total ? (twin.progress.completed / twin.progress.total) * 100 : 0}
              tone={twin.status === "on_track" ? "teal" : twin.status === "needs_attention" ? "amber" : "rose"}
            />
          </Card>

          <SectionCard
            title="Documented signals"
            description="Latest patient-reported check-in"
            icon={<HeartPulse className="h-4 w-4" />}
            action={<VerificationBadge status="patient_reported" showReviewHint={false} />}
          >
            {latestCheckin ? (
              <div className="space-y-3">
                {[
                  { label: "Pain", value: latestCheckin.painScore, max: 10, unit: "/10" },
                  { label: "Breathlessness", value: latestCheckin.breathlessnessScore, max: 10, unit: "/10" },
                ].map((signal) => (
                  <div key={signal.label}>
                    <div className="flex items-baseline justify-between text-[0.66rem]">
                      <span className="text-slate-500">{signal.label}</span>
                      <span className="font-mono font-semibold text-navy-950">
                        {signal.value}
                        <span className="text-slate-500">{signal.unit}</span>
                      </span>
                    </div>
                    <ProgressBar
                      className="mt-1.5"
                      value={(signal.value / signal.max) * 100}
                      tone={signal.value >= 7 ? "rose" : signal.value >= 4 ? "amber" : "teal"}
                    />
                  </div>
                ))}
                <div className="flex items-center justify-between rounded-lg bg-mist-100 px-2.5 py-1.5 text-[0.66rem]">
                  <span className="text-slate-500">Temperature</span>
                  <span className="font-mono font-semibold text-navy-950">
                    {latestCheckin.temperatureC ? `${latestCheckin.temperatureC} °C` : "Not reported"}
                  </span>
                </div>
                <p className="text-[0.6rem] leading-relaxed text-slate-500">
                  Submitted {formatRelative(latestCheckin.submittedAt)} by{" "}
                  {latestCheckin.submittedBy}. Reported values, not measured by CareTwin.
                </p>
              </div>
            ) : (
              <EmptyState
                title="No check-in yet"
                description="A structured daily report creates patient-reported evidence."
                action={
                  <LinkButton href="/workspace/check-in" size="sm">
                    Start check-in
                  </LinkButton>
                }
              />
            )}
          </SectionCard>

          <SectionCard
            title="Open care plan"
            description="Clinician-documented milestones"
            icon={<CheckCircle2 className="h-4 w-4" />}
            action={
              <Link
                href="/workspace/schedule"
                className="text-[0.64rem] font-semibold text-care-600 hover:text-care-700"
              >
                Schedule
              </Link>
            }
          >
            {openMilestones.length ? (
              <div className="space-y-2">
                {openMilestones.slice(0, 3).map((milestone) => (
                  <div key={milestone.id} className="rounded-lg border border-slate-100 bg-mist-50 p-2.5">
                    <p className="text-[0.68rem] font-semibold text-navy-900">
                      {milestone.title}
                    </p>
                    <p className="mt-0.5 text-[0.6rem] text-slate-500">
                      Due {formatDate(milestone.dueDate)} · {milestone.status.replaceAll("_", " ")}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No open milestones" />
            )}
          </SectionCard>
        </div>

        {/* centerpiece */}
        <Card className="relative order-first flex min-h-[34rem] flex-col overflow-hidden border-care-200 xl:order-none">
          <div className="pointer-events-none absolute inset-0" aria-hidden="true">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.07),transparent_65%)]" />
            <div className="dot-grid absolute inset-0 opacity-[0.12]" />
          </div>

          <div className="relative z-10 flex flex-col gap-2 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-display text-[0.98rem] font-semibold tracking-tight text-navy-950">
                Your digital twin
              </h2>
              <p className="mt-0.5 text-[0.66rem] text-slate-500">
                Illustrative twin animation of your documented recovery state
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-care-300 shadow-sm" />
              <span className="text-[0.58rem] font-semibold uppercase tracking-[0.14em] text-care-700">
                {twin.patient.fullName} · {twin.patient.mrn}
              </span>
            </div>
          </div>

          <div className="relative z-10 min-h-[22rem] flex-1 overflow-hidden bg-gradient-to-br from-[#0b1b33] via-[#0a1626] to-[#06101f]">
            <TwinVideo />
          </div>

          <div className="relative z-10 grid grid-cols-2 gap-2 border-t border-slate-100 px-4 py-3 sm:grid-cols-4">
            {[
              {
                label: "Pain",
                value: latestCheckin ? `${latestCheckin.painScore}/10` : "—",
                sub: "patient-reported",
              },
              {
                label: "Temperature",
                value:
                  latestCheckin?.temperatureC != null
                    ? `${latestCheckin.temperatureC}°C`
                    : "—",
                sub: "patient-reported",
              },
              {
                label: "Breathlessness",
                value: latestCheckin ? `${latestCheckin.breathlessnessScore}/10` : "—",
                sub: "patient-reported",
              },
              {
                label: "Adherence",
                value: latestCheckin ? latestCheckin.adherence.replaceAll("_", " ") : "—",
                sub: "self-reported",
              },
            ].map((tile) => (
              <div
                key={tile.label}
                className="rounded-xl border border-slate-100 bg-white px-3 py-2"
              >
                <p className="text-[0.52rem] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  {tile.label}
                </p>
                <p className="mt-0.5 truncate font-display text-[0.95rem] font-semibold capitalize text-navy-950">
                  {tile.value}
                </p>
                <p className="text-[0.52rem] uppercase tracking-[0.1em] text-slate-500">
                  {tile.sub}
                </p>
              </div>
            ))}
          </div>

          <div className="relative z-10 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-2.5">
            <p className="text-[0.6rem] text-slate-500">
              Drag to rotate · scroll to zoom · pause and reset from the model controls.
            </p>
            <Link
              href="/workspace/twin"
              className="inline-flex items-center gap-1 text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
            >
              Twin detail <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
        </Card>

        {/* right intelligence rail */}
        <div className="space-y-4">
          <SectionCard
            title="Health insights"
            description="Deterministic rules, not AI judgment"
            icon={<Sparkles className="h-4 w-4" />}
            tone="glow"
          >
            <p className="text-[0.74rem] font-semibold leading-snug text-navy-900">
              {twin.status === "on_track"
                ? "Recovery is following the documented plan."
                : twin.status === "needs_attention"
                  ? "Some documented signals need a human review."
                  : "A critical rule alert remains open."}
            </p>
            <p className="mt-1.5 text-[0.66rem] leading-relaxed text-slate-500">
              {twin.statusReason}
            </p>
            <div className="mt-3 flex items-center justify-between rounded-lg border border-slate-100 bg-mist-50 px-2.5 py-2">
              <span className="text-[0.62rem] text-slate-500">Awaiting review</span>
              <span className="font-mono text-[0.7rem] font-semibold text-amber-700">
                {twin.dataQuality.awaitingReview} items
              </span>
            </div>
          </SectionCard>

          <SectionCard
            title="Monitoring status"
            description="Clinician-configured thresholds"
            icon={<BellRing className="h-4 w-4" />}
            action={
              <Link
                href="/workspace/alerts"
                className="text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
              >
                All
              </Link>
            }
          >
            {twin.openAlerts.length === 0 ? (
              <div className="flex items-center gap-2.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                <p className="text-[0.66rem] text-emerald-800">
                  No open rule alert. Monitoring remains active.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {twin.openAlerts.slice(0, 2).map((alert) => (
                  <div key={alert.id} className="rounded-lg border border-slate-100 bg-mist-50 p-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[0.68rem] font-semibold text-navy-900">
                        {alert.title}
                      </p>
                      <SeverityBadge severity={alert.severity} />
                    </div>
                    <p className="mt-1 line-clamp-2 text-[0.62rem] leading-relaxed text-slate-500">
                      {alert.rationale}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard
            title="Recent activity"
            description="Immutable recovery events"
            icon={<Activity className="h-4 w-4" />}
            action={
              <Link
                href="/workspace/timeline"
                className="text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
              >
                Timeline
              </Link>
            }
          >
            {timelineState.data?.events.length ? (
              <div className="space-y-2.5">
                {timelineState.data.events.slice(0, 4).map((event) => (
                  <div key={event.id} className="flex gap-2.5">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-care-500 shadow-sm" />
                    <div className="min-w-0">
                      <p className="truncate text-[0.66rem] font-semibold text-navy-900">
                        {event.title}
                      </p>
                      <p className="text-[0.58rem] text-slate-500">
                        {event.actorName} · {formatRelative(event.occurredAt)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No events yet" />
            )}
          </SectionCard>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-[0.55rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Clinician reviewed
              </p>
              <ShieldCheck className="h-3.5 w-3.5 text-care-500" />
            </div>
            <div className="mt-2 flex items-end gap-3">
              <ProgressRing
                completed={verifiedCount}
                total={Math.max(totalEvidence, 1)}
                status={twin.status}
                size={72}
                stroke={6}
                ariaLabel={`Clinician-verified evidence: ${verifiedCount} of ${totalEvidence} items`}
              />
              <div className="min-w-0 pb-1">
                <p className="text-[0.7rem] font-semibold text-navy-950">
                  {verifiedCount} verified sources
                </p>
                <p className="mt-0.5 text-[0.6rem] leading-relaxed text-slate-500">
                  {twin.dataQuality.awaitingReview} still await clinician review.
                  Unverified items are never shown as confirmed.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* ------------------------------------------------------- bottom panels */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SectionCard
          title="Document intelligence"
          description="Uploads, OCR and extraction state"
          icon={<FileText className="h-4 w-4" />}
          action={
            <Link
              href="/workspace/documents"
              className="text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
            >
              Manage
            </Link>
          }
        >
          {documentsState.loading ? (
            <div className="skeleton h-16 rounded-lg" />
          ) : latestDoc ? (
            <div>
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-[0.7rem] font-semibold text-navy-900">
                  {latestDoc.originalFilename}
                </p>
                <Badge
                  tone={
                    latestDoc.extractionStatus === "completed"
                      ? "teal"
                      : latestDoc.extractionStatus === "pending"
                        ? "blue"
                        : "amber"
                  }
                >
                  {latestDoc.extractionStatus.replaceAll("_", " ")}
                </Badge>
              </div>
              <p className="mt-1 text-[0.62rem] text-slate-500">
                {documents.length} document{documents.length === 1 ? "" : "s"} ·{" "}
                {latestDoc.pageCount ?? 0} page{latestDoc.pageCount === 1 ? "" : "s"} ·{" "}
                {latestDoc.extractionMethod || "method unavailable"}
              </p>
              <p className="mt-2 text-[0.6rem] leading-relaxed text-slate-500">
                Scanned pages are OCR-extracted and stay unverified until a clinician
                reviews them.
              </p>
            </div>
          ) : (
            <EmptyState
              icon={<FileSearch className="h-4 w-4" />}
              title="No documents yet"
              description="Upload a discharge summary or lab report to build evidence."
              action={
                <LinkButton href="/workspace/documents" size="sm" variant="secondary">
                  Upload document
                </LinkButton>
              }
            />
          )}
        </SectionCard>

        <SectionCard
          title="Clinical timeline"
          description="What changed, and who changed it"
          icon={<Activity className="h-4 w-4" />}
          action={
            <Link
              href="/workspace/timeline"
              className="text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
            >
              Open
            </Link>
          }
        >
          {timelineState.data?.events.length ? (
            <div className="space-y-2">
              {timelineState.data.events.slice(0, 3).map((event) => (
                <div key={event.id} className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-[0.68rem] font-medium text-navy-800">
                      {event.title}
                    </p>
                    <p className="text-[0.58rem] text-slate-500">
                      {formatRelative(event.occurredAt)} · {event.actorRole}
                    </p>
                  </div>
                  <Badge tone="slate">{event.verificationStatus.replaceAll("_", " ")}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No timeline events" />
          )}
        </SectionCard>

        <SectionCard
          title="Evidence-grounded guidance"
          description="Explains documented evidence only"
          icon={<Sparkles className="h-4 w-4" />}
          action={
            <Link
              href="/workspace/guidance"
              className="text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
            >
              Ask
            </Link>
          }
        >
          {guidanceRun ? (
            <div>
              <p className="text-[0.68rem] font-semibold capitalize text-navy-800">
                {guidanceRun.guidanceType.replaceAll("_", " ")}
              </p>
              <p className="mt-1 line-clamp-3 text-[0.62rem] leading-relaxed text-slate-500">
                {guidanceRun.answer}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <Badge tone={guidanceRun.grounded ? "teal" : "amber"}>
                  {guidanceRun.grounded ? "Grounded" : "Ungrounded"}
                </Badge>
                <Badge tone="slate">{guidanceRun.citations.length} citations</Badge>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<Sparkles className="h-4 w-4" />}
              title="No guidance generated yet"
              description="Guidance quotes verified sources and lists unverified items separately."
              action={
                <LinkButton href="/workspace/guidance" size="sm" variant="secondary">
                  Generate guidance
                </LinkButton>
              }
            />
          )}
        </SectionCard>

        <SectionCard
          title="Care team"
          description="Documented clinicians and follow-ups"
          icon={<Users className="h-4 w-4" />}
          action={
            <Link
              href="/workspace/care-team"
              className="text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
            >
              View
            </Link>
          }
        >
          {twin.nextFollowUp ? (
            <div>
              <p className="text-[0.7rem] font-semibold text-navy-900">
                {twin.nextFollowUp.title}
              </p>
              <p className="mt-1 text-[0.64rem] text-slate-500">
                {twin.nextFollowUp.clinicianName} · {twin.nextFollowUp.specialty}
              </p>
              <p className="mt-1 flex items-center gap-1.5 text-[0.62rem] text-care-700">
                <CalendarClock className="h-3 w-3" />
                {formatDate(twin.nextFollowUp.scheduledFor)} ·{" "}
                {twin.nextFollowUp.location}
              </p>
              <div className="mt-2">
                <VerificationBadge status={twin.nextFollowUp.verificationStatus} showReviewHint={false} />
              </div>
            </div>
          ) : (
            <EmptyState title="No follow-up documented" />
          )}
        </SectionCard>
      </div>

      {/* -------------------------------------------------------- consent strip */}
      <Card className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-care-200 bg-care-50 text-care-600">
            <ShieldCheck className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[0.72rem] font-semibold text-navy-950">
              Privacy &amp; consent status
            </p>
            <p className="mt-0.5 text-[0.64rem] leading-relaxed text-slate-500">
              {consentsState.error
                ? "Consent details are not available to this session."
                : `${activeConsents.length} active sharing agreement${activeConsents.length === 1 ? "" : "s"} · ${
                    activeConsents.reduce((total, record) => total + record.scopes.length, 0)
                  } scopes granted. Enforced server-side at the API boundary.`}
            </p>
          </div>
        </div>
        <LinkButton href="/workspace/consent" variant="secondary" size="sm">
          Manage consent
        </LinkButton>
      </Card>

      {latestObservation && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-3">
          <p className="flex flex-wrap items-center gap-1.5 text-[0.58rem] font-bold uppercase tracking-[0.14em] text-violet-700">
            <Users className="h-3 w-3" /> Latest caregiver observation
            <VerificationBadge status={latestObservation.verificationStatus} />
          </p>
          <p className="mt-1.5 text-[0.72rem] leading-relaxed text-slate-600">
            <span className="font-semibold text-navy-950">{latestObservation.caregiverName}</span>{" "}
            · {latestObservation.category.replaceAll("_", " ")} ·{" "}
            {formatRelative(latestObservation.observedAt)}: {latestObservation.note}
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2 rounded-xl border border-slate-100 bg-mist-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <SafetyFooterNote />
        <span className="shrink-0 text-[0.6rem] uppercase tracking-[0.16em] text-slate-500">
          Synthetic demo data only
        </span>
      </div>
    </div>
  );
}
