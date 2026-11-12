"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  CalendarClock,
  HeartHandshake,
  Pill,
  ShieldCheck,
  Stethoscope,
  UserRound,
  Users,
} from "lucide-react";
import type { ConsentRecord, RecoveryTwin } from "@caretwin/contracts";
import { formatDate, formatDateTime } from "@caretwin/shared";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge, VerificationBadge } from "@/components/ui/badges";
import { LinkButton } from "@/components/ui/button";
import { EmptyState, ErrorState, PageSkeleton } from "@/components/ui/feedback";

type Person = {
  name: string;
  detail: string;
  kind: "clinician" | "caregiver";
  verification?: string;
};

export default function CareTeamPage() {
  const { patientId, selectedUser } = useSession();
  const twinState = useApi<RecoveryTwin>(patientId ? `/patients/${patientId}/twin` : null);
  const consentsState = useApi<ConsentRecord[]>(
    patientId ? `/patients/${patientId}/consents` : null,
  );

  const people = useMemo<Person[]>(() => {
    const twin = twinState.data;
    if (!twin) return [];
    const map = new Map<string, Person>();

    for (const followUp of twin.followUps) {
      if (!followUp.clinicianName) continue;
      map.set(`clin-${followUp.clinicianName}`, {
        name: followUp.clinicianName,
        detail: `${followUp.specialty} · ${followUp.location} · next ${formatDate(followUp.scheduledFor)}`,
        kind: "clinician",
        verification: followUp.verificationStatus,
      });
    }
    for (const medication of twin.medications) {
      if (!medication.prescribedBy) continue;
      const key = `clin-${medication.prescribedBy}`;
      if (!map.has(key)) {
        map.set(key, {
          name: medication.prescribedBy,
          detail: "Prescriber on the documented medication record",
          kind: "clinician",
          verification: medication.verificationStatus,
        });
      }
    }
    for (const record of consentsState.data ?? []) {
      map.set(`cg-${record.granteeUserId}`, {
        name: record.granteeName,
        detail: `${record.granteeRelationship} · ${record.scopes.length} scopes · ${record.status}`,
        kind: "caregiver",
      });
    }
    for (const observation of twin.observations) {
      const key = `cg-${observation.caregiverName}`;
      if (!map.has(key)) {
        map.set(key, {
          name: observation.caregiverName,
          detail: "Recorded caregiver observations",
          kind: "caregiver",
          verification: observation.verificationStatus,
        });
      }
    }
    return Array.from(map.values());
  }, [twinState.data, consentsState.data]);

  if (twinState.loading && !twinState.data) return <PageSkeleton />;
  if (twinState.error) {
    return <ErrorState error={twinState.error} onRetry={twinState.refresh} />;
  }
  if (!twinState.data) return <PageSkeleton />;

  const twin = twinState.data;
  const clinicians = people.filter((person) => person.kind === "clinician");
  const caregivers = people.filter((person) => person.kind === "caregiver");

  return (
    <div>
      <PageHeader
        eyebrow="Care team"
        title="The people in the record"
        description="Everyone listed here comes from documented encounters, prescribed instructions or an active consent grant. CareTwin does not invent care-team members, and shows whether each item is verified."
        actions={
          <LinkButton href="/workspace/consent" variant="secondary" size="sm">
            <ShieldCheck className="h-3.5 w-3.5" /> Consent &amp; sharing
          </LinkButton>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <SectionCard
            title={`Clinicians · ${clinicians.length}`}
            description="Documented follow-ups and prescribers"
            icon={<Stethoscope className="h-4 w-4" />}
          >
            {clinicians.length === 0 ? (
              <EmptyState
                title="No clinicians documented"
                description="Clinicians appear here once a follow-up or prescription is recorded."
              />
            ) : (
              <div className="space-y-2">
                {clinicians.map((person) => (
                  <div
                    key={person.name}
                    className="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-mist-50 p-3"
                  >
                    <div className="flex items-start gap-2.5">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-care-50 text-care-600 ring-1 ring-care-200">
                        <Stethoscope className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-[0.76rem] font-semibold text-navy-950">{person.name}</p>
                        <p className="mt-0.5 text-[0.64rem] text-slate-400">{person.detail}</p>
                      </div>
                    </div>
                    {person.verification && (
                      <VerificationBadge status={person.verification as never} showReviewHint={false} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard
            title={`Caregivers · ${caregivers.length}`}
            description="Consent grantees and observation authors"
            icon={<HeartHandshake className="h-4 w-4" />}
          >
            {caregivers.length === 0 ? (
              <EmptyState
                title="No caregiver access"
                description="Caregiver details are visible only with an active consent grant."
              />
            ) : (
              <div className="space-y-2">
                {caregivers.map((person) => (
                  <div
                    key={person.name}
                    className="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-mist-50 p-3"
                  >
                    <div className="flex items-start gap-2.5">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-50 text-violet-700 ring-1 ring-violet-200">
                        <Users className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-[0.76rem] font-semibold text-navy-950">{person.name}</p>
                        <p className="mt-0.5 text-[0.64rem] capitalize text-slate-400">
                          {person.detail}
                        </p>
                      </div>
                    </div>
                    {person.verification && (
                      <VerificationBadge status={person.verification as never} showReviewHint={false} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>

        <div className="space-y-4">
          <SectionCard
            title="Follow-up schedule"
            description="Documented appointments"
            icon={<CalendarClock className="h-4 w-4" />}
          >
            {twin.followUps.length === 0 ? (
              <EmptyState title="No follow-ups documented" />
            ) : (
              <div className="space-y-2">
                {twin.followUps.map((followUp) => (
                  <div key={followUp.id} className="rounded-lg border border-slate-100 bg-mist-50 p-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[0.7rem] font-semibold text-navy-900">
                        {followUp.title}
                      </p>
                      <Badge tone={followUp.status === "completed" ? "teal" : "blue"}>
                        {followUp.status}
                      </Badge>
                    </div>
                    <p className="mt-0.5 text-[0.62rem] text-slate-400">
                      {formatDateTime(followUp.scheduledFor)}
                    </p>
                    <p className="mt-0.5 text-[0.62rem] text-slate-500">
                      {followUp.clinicianName} · {followUp.location}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard
            title="Medication prescribers"
            description="As documented in the discharge plan"
            icon={<Pill className="h-4 w-4" />}
          >
            <div className="space-y-2">
              {twin.medications.map((medication) => (
                <div
                  key={medication.id}
                  className="flex items-center justify-between gap-2 rounded-lg bg-mist-100 px-2.5 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[0.68rem] font-medium text-navy-800">
                      {medication.name}
                    </p>
                    <p className="text-[0.58rem] text-slate-500">
                      {medication.prescribedBy || "Prescriber not recorded"}
                    </p>
                  </div>
                  <VerificationBadge status={medication.verificationStatus} showReviewHint={false} />
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title="Patient"
            description="Record owner"
            icon={<UserRound className="h-4 w-4" />}
          >
            <div className="flex items-center justify-between gap-2 rounded-lg bg-mist-100 px-3 py-2.5">
              <div>
                <p className="text-[0.76rem] font-semibold text-navy-950">
                  {twin.patient.fullName}
                </p>
                <p className="text-[0.62rem] text-slate-400">
                  {twin.patient.mrn} · {twin.patient.condition}
                </p>
              </div>
              <Badge tone="teal">Patient</Badge>
            </div>
            <p className="mt-2 text-[0.6rem] leading-relaxed text-slate-500">
              Viewing as {selectedUser?.name} ({selectedUser?.role}). Patient isolation
              and consent scopes are enforced by the API.
            </p>
            <Link
              href="/workspace/consent"
              className="mt-2 inline-block text-[0.62rem] font-semibold text-care-600 hover:text-care-700"
            >
              Review sharing scopes
            </Link>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
