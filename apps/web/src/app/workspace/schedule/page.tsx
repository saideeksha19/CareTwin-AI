"use client";

import { useState } from "react";
import {
  CalendarClock,
  ClipboardList,
  Clock3,
  MapPin,
  Pill,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import type { RecoveryTwin } from "@caretwin/contracts";
import { formatDate, formatDateTime } from "@caretwin/shared";
import { ApiClientError, apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge, VerificationBadge } from "@/components/ui/badges";
import {
  AccessRestricted,
  ErrorState,
  InlineMessage,
  PageSkeleton,
  SafetyFooterNote,
} from "@/components/ui/feedback";
import { FollowUpRow, MedicationRow } from "@/components/workspace/records";

export default function SchedulePage() {
  const { patientId, selectedUser } = useSession();
  const state = useApi<RecoveryTwin>(patientId ? `/patients/${patientId}/twin` : null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function verify(medicationId: string, note: string) {
    if (!patientId || !selectedUser) return;
    setVerifyingId(medicationId);
    setError(null);
    setMessage(null);
    try {
      const result = await apiRequest<{ twinVersion: number }>(
        `/patients/${patientId}/medications/${medicationId}/verify`,
        { method: "POST", userId: selectedUser.id, body: { note } },
      );
      setMessage(`Instruction verified. Twin version is now v${result.twinVersion}.`);
      state.refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setVerifyingId(null);
    }
  }

  if (state.loading && !state.data) return <PageSkeleton />;
  if (state.error instanceof ApiClientError && state.error.status === 403) {
    return (
      <AccessRestricted
        title="The schedule is not shared with this role"
        description="Medication and follow-up instructions are consent-scoped. This demo identity does not have the schedule:read scope."
      />
    );
  }
  if (state.error) return <ErrorState error={state.error} onRetry={state.refresh} />;
  if (!state.data) return <PageSkeleton />;

  const twin = state.data;
  const isClinician = selectedUser?.role === "clinician";
  const awaiting = twin.medications.filter(
    (item) =>
      item.verificationStatus === "awaiting_review" ||
      item.verificationStatus === "document_extracted",
  );
  const upcoming = twin.followUps.filter((item) => item.status !== "completed");
  const completed = twin.followUps.filter((item) => item.status === "completed");

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Medications & follow-ups"
        title="The documented recovery schedule."
        description="Instructions come from the discharge packet. Extracted items stay flagged until a clinician verifies them against the source."
        actions={
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="slate">{twin.medications.length} medications</Badge>
            <Badge tone="slate">{upcoming.length} upcoming</Badge>
            {awaiting.length > 0 && <Badge tone="amber">{awaiting.length} to review</Badge>}
          </div>
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

      {isClinician && awaiting.length > 0 && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="flex items-center gap-2 text-xs font-semibold text-amber-900">
            <ClipboardList className="h-4 w-4" /> Clinical review queue
          </p>
          <p className="mt-1 text-[0.7rem] leading-relaxed text-amber-900/80">
            {awaiting.length} medication instruction
            {awaiting.length === 1 ? "" : "s"} were extracted from a document and have not
            been verified. Review the source excerpt before verifying.
          </p>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.25fr_1fr]">
        <SectionCard
          title="Medication instructions"
          description="Dose, route, frequency and duration as documented — not an AI recommendation."
          icon={<Pill className="h-4 w-4" />}
          action={<Badge tone={awaiting.length ? "amber" : "teal"}>
            {awaiting.length ? `${awaiting.length} awaiting review` : "All reviewed"}
          </Badge>}
        >
          <div className="space-y-2.5">
            {twin.medications.map((medication) => (
              <MedicationRow
                key={medication.id}
                medication={medication}
                canVerify={isClinician}
                onVerify={(note) => void verify(medication.id, note)}
                verifying={verifyingId === medication.id}
              />
            ))}
          </div>
          <div className="mt-4 flex items-start gap-2 rounded-lg bg-mist-50 px-3 py-2 text-[0.66rem] leading-relaxed text-slate-500">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-care-600" />
            CareTwin never changes a medication or dose. Verification only confirms that an
            extracted instruction matches its cited source.
          </div>
        </SectionCard>

        <div className="space-y-4">
          <SectionCard
            title="Upcoming follow-ups"
            description="Scheduled from documented discharge instructions."
            icon={<CalendarClock className="h-4 w-4" />}
          >
            {upcoming.length === 0 ? (
              <p className="text-xs text-slate-500">No upcoming follow-ups recorded.</p>
            ) : (
              <div className="space-y-2.5">
                {upcoming.map((followUp) => (
                  <FollowUpRow key={followUp.id} followUp={followUp} />
                ))}
              </div>
            )}
          </SectionCard>

          {twin.nextFollowUp && (
            <div className="rounded-2xl border border-care-200 bg-care-50/50 p-4">
              <p className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-care-800">
                Next appointment
              </p>
              <p className="mt-1.5 text-sm font-semibold text-navy-950">
                {twin.nextFollowUp.title}
              </p>
              <div className="mt-2 space-y-1 text-[0.7rem] text-slate-600">
                <p className="flex items-center gap-1.5">
                  <Clock3 className="h-3 w-3 text-care-700" />
                  {formatDateTime(twin.nextFollowUp.scheduledFor)}
                </p>
                <p className="flex items-center gap-1.5">
                  <Stethoscope className="h-3 w-3 text-care-700" />
                  {twin.nextFollowUp.clinicianName} · {twin.nextFollowUp.specialty}
                </p>
                <p className="flex items-center gap-1.5">
                  <MapPin className="h-3 w-3 text-care-700" />
                  {twin.nextFollowUp.location}
                </p>
              </div>
              <div className="mt-2 flex items-center gap-1.5">
                <VerificationBadge status={twin.nextFollowUp.verificationStatus} />
              </div>
            </div>
          )}

          {completed.length > 0 && (
            <SectionCard
              title="Completed visits"
              description="Historical follow-up records."
              icon={<CalendarClock className="h-4 w-4" />}
            >
              <div className="space-y-2">
                {completed.map((followUp) => (
                  <div
                    key={followUp.id}
                    className="flex items-start justify-between gap-2 rounded-lg bg-mist-50 px-3 py-2"
                  >
                    <div>
                      <p className="text-[0.7rem] font-semibold text-navy-900">
                        {followUp.title}
                      </p>
                      <p className="text-[0.62rem] text-slate-500">
                        {formatDate(followUp.scheduledFor)} · {followUp.clinicianName}
                      </p>
                    </div>
                    <Badge tone="teal">completed</Badge>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <SafetyFooterNote />
          </div>
        </div>
      </div>
    </div>
  );
}
