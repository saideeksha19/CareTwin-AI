"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  CalendarClock,
  ClipboardCheck,
  FileSearch,
  Fingerprint,
  GitCommitVertical,
  Orbit,
  Pill,
  ShieldCheck,
  Users,
} from "lucide-react";
import type {
  EvidenceSource,
  RecoveryTwin,
  TwinSnapshotMeta,
} from "@caretwin/contracts";
import { formatDate, formatDateTime, formatRelative } from "@caretwin/shared";
import { twinStatusDescription } from "@caretwin/domain";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { Card, SectionCard } from "@/components/ui/cards";
import { LinkButton } from "@/components/ui/button";
import {
  Badge,
  SourceChip,
  SourceTypeBadge,
  StatusPill,
  VerificationBadge,
} from "@/components/ui/badges";
import { ProgressBar, ProgressRing } from "@/components/ui/progress";
import {
  AccessRestricted,
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageSkeleton,
} from "@/components/ui/feedback";
import { ApiClientError } from "@/lib/api";
import {
  FollowUpRow,
  MedicationRow,
  MilestoneRow,
} from "@/components/workspace/records";
import { TwinVideo } from "@/components/twin/twin-video";
import { formatValueWithUnit } from "@/lib/documents";

export default function TwinPage() {
  const { patientId, selectedUser } = useSession();
  const twinState = useApi<RecoveryTwin>(patientId ? `/patients/${patientId}/twin` : null);
  const snapshotsState = useApi<TwinSnapshotMeta[]>(
    patientId ? `/patients/${patientId}/snapshots` : null,
  );
  const timelineState = useApi<{ events: Array<{ id: string; title: string; occurredAt: string; actorName: string }> }>(
    patientId ? `/patients/${patientId}/timeline?limit=8` : null,
  );

  const evidenceIndex = useMemo<Record<string, EvidenceSource>>(() => {
    const index: Record<string, EvidenceSource> = {};
    for (const item of twinState.data?.evidence ?? []) index[item.id] = item;
    return index;
  }, [twinState.data]);

  if (twinState.loading && !twinState.data) return <PageSkeleton />;

  if (twinState.error instanceof ApiClientError && twinState.error.status === 403) {
    return (
      <AccessRestricted
        title="This twin is not shared with this role"
        description="The server denied access to the recovery twin for this demo identity. Caregiver visibility depends on an active patient consent with the twin:read scope."
        showConsentLink={selectedUser?.role === "patient"}
      />
    );
  }
  if (twinState.error) {
    return <ErrorState error={twinState.error} onRetry={twinState.refresh} />;
  }
  if (!twinState.data) return <PageSkeleton />;

  const twin = twinState.data as RecoveryTwin & {
    clinicalDocuments?: Array<{
      id: string;
      originalFilename: string;
      documentType: string;
      extractionStatus: string;
      pageCount: number | null;
      uploadedAt: string;
      verifiedCount: number;
      pendingReviewCount: number;
    }>;
    documentFindings?: {
      verified: Array<{
        id: string;
        documentId: string;
        documentName: string;
        label: string;
        itemType: string;
        valueText: string | null;
        unit: string;
        referenceRange: string;
        pageNumber: number | null;
        verifiedBy: string | null;
        verifiedAt: string | null;
      }>;
      verifiedCount: number;
      pendingReviewCount: number;
      note: string;
    };
    bodyRegionNote?: string;
  };
  const awaitingMeds = twin.medications.filter(
    (item) =>
      item.verificationStatus === "awaiting_review" ||
      item.verificationStatus === "document_extracted",
  );
  const verifiedEvidence = twin.evidence.filter(
    (item) => item.verificationStatus === "clinician_verified",
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="flex items-center gap-2 text-[0.58rem] font-semibold uppercase tracking-[0.22em] text-care-600">
            <span className="h-px w-6 bg-care-300" aria-hidden="true" />
            Patient Digital Twin
          </p>
          <h1 className="mt-2 font-display text-[1.7rem] font-semibold tracking-tight text-navy-950 md:text-[2rem]">
            {twin.patient.fullName}&rsquo;s <span className="holo-text">recovery twin</span>
          </h1>
          <p className="mt-1.5 max-w-2xl text-[0.82rem] leading-relaxed text-slate-500">
            A versioned projection of documented instructions, reports, observations and
            alerts. The twin animation is illustrative; it does not infer disease from
            appearance.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <LinkButton href="/workspace/timeline" variant="secondary" size="sm">
            <Activity className="h-3.5 w-3.5" /> Timeline
          </LinkButton>
          {selectedUser?.role === "patient" && (
            <LinkButton href="/workspace/check-in" size="sm">
              <ClipboardCheck className="h-3.5 w-3.5" /> Check in
            </LinkButton>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------ immersive stage */}
      <Card className="relative overflow-hidden border-care-200">
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <div className="absolute inset-x-0 top-0 h-44 bg-[radial-gradient(ellipse_at_top,rgba(34,211,238,0.16),transparent_70%)]" />
          <div className="absolute inset-x-0 bottom-0 h-64 bg-[radial-gradient(ellipse_at_bottom,rgba(99,102,241,0.16),transparent_70%)]" />
          <div className="dot-grid absolute inset-0 opacity-[0.16]" />
        </div>

        <div className="relative z-10 grid gap-0 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)_minmax(0,19rem)]">
          {/* left */}
          <div className="space-y-3 border-slate-100 p-4 lg:border-r">
            <div>
              <p className="text-[0.55rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Twin identity
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <StatusPill status={twin.status} />
                <Badge tone="slate">Version {twin.version}</Badge>
                <Badge tone="amber">Synthetic</Badge>
              </div>
              <p className="mt-2 text-[0.8rem] font-semibold text-navy-950">
                {twin.patient.preferredName} · day {twin.patient.postDischargeDay}
              </p>
              <p className="mt-0.5 text-[0.68rem] text-slate-500">
                {twin.patient.condition}
              </p>
              <p className="mt-0.5 text-[0.62rem] text-slate-500">
                Discharged {formatDate(twin.patient.dischargedOn)} · {twin.patient.mrn}
              </p>
            </div>

            <div className="rounded-xl border border-slate-100 bg-mist-50 p-3">
              <div className="flex items-center justify-between">
                <p className="text-[0.55rem] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Care plan
                </p>
                <span className="font-mono text-[0.62rem] text-care-700">
                  {twin.progress.completed}/{twin.progress.total}
                </span>
              </div>
              <ProgressBar
                className="mt-2"
                value={
                  twin.progress.total
                    ? (twin.progress.completed / twin.progress.total) * 100
                    : 0
                }
                tone={
                  twin.status === "on_track"
                    ? "teal"
                    : twin.status === "needs_attention"
                      ? "amber"
                      : "rose"
                }
              />
              <p className="mt-2 text-[0.62rem] leading-relaxed text-slate-500">
                {twinStatusDescription(twin.status)}
              </p>
            </div>

            <div className="space-y-2">
              {[
                ["Open alerts", String(twin.openAlerts.length)],
                ["Awaiting review", String(twin.dataQuality.awaitingReview)],
                ["Verified evidence", `${twin.dataQuality.verifiedEvidence}/${twin.dataQuality.totalEvidence}`],
                ["Updated", formatRelative(twin.updatedAt)],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex items-center justify-between rounded-lg bg-mist-50 px-2.5 py-1.5 text-[0.64rem]"
                >
                  <span className="text-slate-500">{label}</span>
                  <span className="font-mono font-semibold text-navy-900">{value}</span>
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-slate-100 bg-mist-50 p-3">
              <p className="flex items-center gap-1.5 text-[0.55rem] font-semibold uppercase tracking-[0.14em] text-slate-500">
                <ShieldCheck className="h-3 w-3" /> Visibility
              </p>
              <p className="mt-1.5 text-[0.64rem] leading-relaxed text-slate-500">
                {twin.visibility.note}
              </p>
              <div className="mt-2 flex items-center gap-1.5">
                <Badge tone="blue">{twin.visibility.role}</Badge>
                <Badge tone={twin.visibility.filtered ? "amber" : "teal"}>
                  {twin.visibility.filtered ? "Consent filtered" : "Full scope"}
                </Badge>
              </div>
            </div>
          </div>

          {/* center */}
          <div className="relative order-first flex min-h-[34rem] flex-col lg:order-none">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <p className="text-[0.58rem] font-semibold uppercase tracking-[0.18em] text-care-700">
                Digital twin animation
              </p>
              <span className="hidden text-[0.55rem] uppercase tracking-[0.14em] text-slate-500 sm:inline">
                Synthetic · illustrative animation
              </span>
            </div>
            <div className="relative min-h-[26rem] flex-1 overflow-hidden bg-gradient-to-br from-[#0b1b33] via-[#0a1626] to-[#06101f]">
              <TwinVideo />
            </div>
            <div className="border-t border-slate-100 px-4 py-2.5">
              <p className="text-[0.58rem] leading-relaxed text-slate-500">
                This synthetic twin animation is illustrative only. It is not a live scan
                or a patient-specific anatomical model, and it does not reflect real
                internal organs. Health status comes only from documented records and
                clinician-configured rules.
              </p>
            </div>
          </div>

          {/* right */}
          <div className="space-y-3 border-slate-100 p-4 lg:border-l">
            <div>
              <p className="text-[0.55rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Verified indicators
              </p>
              <div className="mt-2 space-y-2">
                {verifiedEvidence.length ? (
                  verifiedEvidence.slice(0, 3).map((evidence) => (
                    <div
                      key={evidence.id}
                      className="rounded-lg border border-slate-100 bg-mist-50 p-2.5"
                    >
                      <p className="text-[0.66rem] font-semibold text-navy-900">
                        {evidence.title}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-1">
                        <SourceTypeBadge type={evidence.sourceType} />
                        <Badge tone="slate">{evidence.pageRef}</Badge>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="rounded-lg border border-slate-100 bg-mist-50 px-2.5 py-2 text-[0.64rem] text-slate-500">
                    No clinician-verified evidence yet. Extracted items remain
                    unverified until reviewed.
                  </p>
                )}
              </div>
            </div>

            <div>
              <p className="text-[0.55rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Documented changes
              </p>
              <div className="mt-2 space-y-2">
                {timelineState.data?.events.length ? (
                  timelineState.data.events.slice(0, 5).map((event) => (
                    <div key={event.id} className="flex gap-2">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-care-300" />
                      <div className="min-w-0">
                        <p className="truncate text-[0.64rem] font-medium text-navy-800">
                          {event.title}
                        </p>
                        <p className="text-[0.55rem] text-slate-500">
                          {event.actorName} · {formatRelative(event.occurredAt)}
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-[0.64rem] text-slate-500">No events yet.</p>
                )}
              </div>
              <Link
                href="/workspace/timeline"
                className="mt-2 inline-block text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
              >
                Full timeline
              </Link>
            </div>

            {awaitingMeds.length > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                <p className="text-[0.55rem] font-semibold uppercase tracking-[0.14em] text-amber-700">
                  Needs review
                </p>
                <p className="mt-1 text-[0.62rem] leading-relaxed text-amber-700">
                  {awaitingMeds.length} medication instruction
                  {awaitingMeds.length === 1 ? "" : "s"} extracted from documents are
                  awaiting clinician confirmation.
                </p>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* ------------------------------------------------------ clinical detail */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard
          title="Recovery plan & milestones"
          description={twin.plan.summary}
          icon={<Orbit className="h-4 w-4" />}
          action={<Badge tone="teal">{twin.plan.status.replaceAll("_", " ")}</Badge>}
        >
          <div>
            {twin.milestones.map((milestone) => (
              <MilestoneRow key={milestone.id} milestone={milestone} />
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="Medication instructions"
          description="Documented instructions keep their source and review state"
          icon={<Pill className="h-4 w-4" />}
          action={
            awaitingMeds.length > 0 ? (
              <Badge tone="amber">{awaitingMeds.length} awaiting review</Badge>
            ) : (
              <Badge tone="teal">All reviewed</Badge>
            )
          }
        >
          <div className="space-y-2.5">
            {twin.medications.map((medication) => (
              <MedicationRow key={medication.id} medication={medication} />
            ))}
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard
          title="Follow-ups"
          description="Appointments documented in the discharge plan"
          icon={<CalendarClock className="h-4 w-4" />}
        >
          <div className="space-y-2.5">
            {twin.followUps.map((followUp) => (
              <FollowUpRow key={followUp.id} followUp={followUp} />
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="Recent check-ins"
          description="Patient-reported, attributed, not clinician verified"
          icon={<ClipboardCheck className="h-4 w-4" />}
        >
          {twin.recentCheckIns.length === 0 ? (
            <EmptyState title="No check-ins yet" />
          ) : (
            <div className="space-y-3">
              {twin.recentCheckIns.map((checkin) => (
                <div key={checkin.id} className="rounded-xl border border-slate-100 bg-mist-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[0.68rem] font-semibold text-navy-900">
                      {formatDateTime(checkin.submittedAt)}
                    </p>
                    <VerificationBadge status={checkin.verificationStatus} />
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                    {[
                      ["Pain", `${checkin.painScore}/10`],
                      ["Breathless", `${checkin.breathlessnessScore}/10`],
                      ["Temp", checkin.temperatureC ? `${checkin.temperatureC}°C` : "—"],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md bg-mist-100 py-1.5">
                        <p className="text-[0.52rem] uppercase tracking-wide text-slate-500">
                          {label}
                        </p>
                        <p className="text-xs font-semibold text-navy-950">{value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {checkin.symptoms.map((symptom) => (
                      <Badge key={symptom.code} tone="slate">
                        {symptom.label} {symptom.severity}/10
                      </Badge>
                    ))}
                    <SourceChip
                      evidence={
                        checkin.evidenceId ? evidenceIndex[checkin.evidenceId] : null
                      }
                    />
                  </div>
                  {checkin.notes && (
                    <p className="mt-2 text-[0.66rem] leading-relaxed text-slate-500">
                      &ldquo;{checkin.notes}&rdquo;
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard
        title="Verified document findings"
        description={
          twin.documentFindings?.note ??
          "Only clinician-verified extractions are shown as twin facts."
        }
        icon={<FileSearch className="h-4 w-4" />}
        action={
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="teal">
              {twin.documentFindings?.verifiedCount ?? 0} verified
            </Badge>
            <Badge tone="amber">
              {twin.documentFindings?.pendingReviewCount ?? 0} awaiting review
            </Badge>
          </div>
        }
      >
        {(twin.documentFindings?.verified ?? []).length === 0 ? (
          <EmptyState
            title="No clinician-verified document findings yet"
            description="A clinician verifies extracted items on the Medical Documents page before they become twin facts."
          />
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {(twin.documentFindings?.verified ?? []).map((finding) => (
              <div
                key={finding.id}
                className="rounded-lg border border-slate-100 bg-mist-50 p-2.5"
              >
                <div className="flex flex-wrap items-center justify-between gap-1.5">
                  <p className="text-[0.66rem] font-semibold text-navy-900">{finding.label}</p>
                  <Badge tone="teal">verified</Badge>
                </div>
                <p className="mt-0.5 font-mono text-[0.68rem] text-navy-800">
                  {formatValueWithUnit(finding.valueText, finding.unit)}
                </p>
                {finding.referenceRange && (
                  <p className="text-[0.56rem] text-slate-500">
                    printed range {finding.referenceRange}
                  </p>
                )}
                <p className="mt-1 text-[0.56rem] text-slate-500">
                  {finding.documentName} · page {finding.pageNumber ?? "?"}
                  {finding.verifiedBy ? ` · verified by ${finding.verifiedBy}` : ""}
                </p>
              </div>
            ))}
          </div>
        )}
        {twin.bodyRegionNote && (
          <p className="mt-3 text-[0.58rem] leading-relaxed text-slate-500">
            {twin.bodyRegionNote}
          </p>
        )}
        {(twin.clinicalDocuments ?? []).length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-2.5">
            <p className="text-[0.54rem] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Recent documents
            </p>
            <ul className="mt-1 space-y-1">
              {(twin.clinicalDocuments ?? []).slice(0, 6).map((doc) => (
                <li
                  key={doc.id}
                  className="flex flex-wrap items-center justify-between gap-1.5 text-[0.6rem] text-slate-500"
                >
                  <span className="truncate">{doc.originalFilename}</span>
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-[0.55rem] text-slate-500">
                      {doc.pageCount ?? "?"}p
                    </span>
                    <Badge tone={doc.pendingReviewCount ? "amber" : "teal"}>
                      {doc.pendingReviewCount
                        ? `${doc.pendingReviewCount} pending`
                        : `${doc.verifiedCount} verified`}
                    </Badge>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </SectionCard>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
        <SectionCard
          title="Caregiver observations"
          description="Attributed caregiver-reported context"
          icon={<Users className="h-4 w-4" />}
        >
          {twin.observations.length === 0 ? (
            <EmptyState title="No observations recorded" />
          ) : (
            <div className="space-y-2.5">
              {twin.observations.map((observation) => (
                <div key={observation.id} className="rounded-lg bg-mist-100 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[0.66rem] font-semibold text-navy-900">
                      {observation.caregiverName} ·{" "}
                      {observation.category.replaceAll("_", " ")}
                    </p>
                    <VerificationBadge status={observation.verificationStatus} />
                  </div>
                  <p className="mt-1 text-[0.68rem] leading-relaxed text-slate-500">
                    {observation.note}
                  </p>
                  <p className="mt-1 text-[0.58rem] text-slate-500">
                    {formatDateTime(observation.observedAt)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Evidence graph"
          description={`${twin.dataQuality.totalEvidence} sources · ${twin.dataQuality.verifiedEvidence} clinician verified · ${twin.dataQuality.awaitingReview} awaiting review`}
          icon={<FileSearch className="h-4 w-4" />}
        >
          <div className="space-y-2.5">
            {twin.evidence.map((evidence) => (
              <div key={evidence.id} className="rounded-lg border border-slate-100 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-[0.68rem] font-semibold text-navy-900">
                    {evidence.title}
                  </p>
                  <VerificationBadge status={evidence.verificationStatus} />
                </div>
                <p className="mt-1 line-clamp-2 text-[0.66rem] leading-relaxed text-slate-500">
                  {evidence.excerpt}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <SourceTypeBadge type={evidence.sourceType} />
                  <Badge tone="slate">{evidence.pageRef}</Badge>
                  {evidence.extractedByAi && <Badge tone="violet">AI extraction</Badge>}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
        <SectionCard
          title="Snapshot history"
          description="Consequential changes increment the twin version"
          icon={<GitCommitVertical className="h-4 w-4" />}
        >
          {snapshotsState.loading ? (
            <LoadingBlock label="Loading snapshots" className="py-6" />
          ) : snapshotsState.data?.length ? (
            <div className="space-y-2">
              {snapshotsState.data.slice(0, 6).map((snapshot) => (
                <div key={snapshot.id} className="flex items-start justify-between gap-2 border-b border-slate-100 pb-2 last:border-0 last:pb-0">
                  <div>
                    <p className="text-[0.68rem] font-semibold text-navy-900">
                      v{snapshot.version} · {snapshot.reason}
                    </p>
                    <p className="text-[0.58rem] text-slate-500">
                      {formatDateTime(snapshot.createdAt)}
                    </p>
                  </div>
                  <Badge tone="slate">{snapshot.id}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No snapshots yet" />
          )}
        </SectionCard>

        <Card className="p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-care-600" />
            <p className="text-[0.72rem] font-semibold text-navy-950">Consent & visibility</p>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg bg-mist-100 p-3">
              <p className="text-[0.55rem] uppercase tracking-[0.14em] text-slate-500">
                Role
              </p>
              <p className="mt-0.5 text-[0.78rem] font-semibold capitalize text-navy-950">
                {twin.visibility.role}
              </p>
            </div>
            <div className="rounded-lg bg-mist-100 p-3">
              <p className="text-[0.55rem] uppercase tracking-[0.14em] text-slate-500">
                Consent filtered
              </p>
              <p className="mt-0.5 text-[0.78rem] font-semibold text-navy-950">
                {twin.visibility.filtered ? "Yes" : "No"}
              </p>
            </div>
          </div>
          <p className="mt-2 rounded-lg bg-mist-50 px-3 py-2 text-[0.66rem] leading-relaxed text-slate-500">
            {twin.visibility.note}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <LinkButton href="/workspace/consent" variant="secondary" size="sm">
              View consent state
            </LinkButton>
            <LinkButton href="/workspace/alerts" variant="ghost" size="sm">
              <ShieldCheck className="h-3.5 w-3.5" /> Review alerts
            </LinkButton>
          </div>
        </Card>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[0.66rem] leading-relaxed text-amber-700 sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-start gap-2">
          <Fingerprint className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {twin.syntheticDisclaimer}
        </p>
        <span className="shrink-0 uppercase tracking-[0.16em] text-amber-600">
          Not a diagnostic device
        </span>
      </div>
    </div>
  );
}
