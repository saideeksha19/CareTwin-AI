"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ClipboardCheck,
  Fingerprint,
  GitCommitVertical,
  PhoneCall,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import type { RecoveryTwin } from "@caretwin/contracts";
import { formatDateTime, formatRelative } from "@caretwin/shared";
import { useSession } from "@/lib/session";
import { workspaceHome } from "@/lib/nav";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge, VerificationBadge } from "@/components/ui/badges";
import { AccessRestricted, LoadingBlock } from "@/components/ui/feedback";
import { CheckinForm } from "@/components/workspace/checkin-form";

export default function CheckInPage() {
  const { selectedUser, patientId } = useSession();
  const router = useRouter();
  const twinState = useApi<RecoveryTwin>(patientId ? `/patients/${patientId}/twin` : null);

  useEffect(() => {
    if (selectedUser && selectedUser.role !== "patient") {
      router.replace(workspaceHome(selectedUser.role));
    }
  }, [selectedUser, router]);

  const latest = useMemo(
    () => twinState.data?.recentCheckIns[0] ?? null,
    [twinState.data],
  );

  if (!selectedUser || selectedUser.role !== "patient") {
    if (selectedUser) {
      return (
        <AccessRestricted
          title="Only the patient can submit a daily check-in"
          description="Caregivers can record attributed observations, and clinicians review alerts and verify instructions. A patient check-in is a self-report and cannot be authored by another role."
        />
      );
    }
    return <LoadingBlock label="Opening check-in" />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Daily check-in"
        title="Tell your care team how today is going."
        description="Structured self-report, evaluated against clinician-configured rules. This is not a diagnosis, and it does not replace urgent care."
        actions={
          latest && (
            <Badge tone="slate">
              Last check-in {formatRelative(latest.submittedAt)}
            </Badge>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr]">
        <div>
          <CheckinForm onSubmitted={twinState.refresh} />
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-rose-200 bg-rose-50/60 p-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-rose-800">
              <PhoneCall className="h-4 w-4" /> If this is an emergency
            </p>
            <p className="mt-1.5 text-[0.72rem] leading-relaxed text-rose-900/80">
              If symptoms feel severe or are worsening quickly — such as severe breathing
              difficulty, unrelenting chest pain, confusion, or fainting — contact local
              emergency services or your care team now. Do not wait for app-based review.
            </p>
          </div>

          <SectionCard
            title="What happens on submit"
            description="A deterministic, inspectable chain."
            icon={<GitCommitVertical className="h-4 w-4" />}
          >
            <ol className="space-y-3">
              {[
                {
                  title: "Attributed evidence is created",
                  body: "Your report becomes a patient-reported evidence source with a timestamp.",
                },
                {
                  title: "Safety validation runs",
                  body: "Role, bounds and determinism checks are recorded as a safety decision.",
                },
                {
                  title: "Rules evaluate the report",
                  body: "Six clinician-configured rules can create open alerts with provenance.",
                },
                {
                  title: "Twin version increments",
                  body: "A snapshot captures the new recovery state for audit.",
                },
              ].map((step, index) => (
                <li key={step.title} className="flex gap-2.5">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-care-50 font-mono text-[0.6rem] font-bold text-care-700">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-[0.7rem] font-semibold text-navy-950">
                      {step.title}
                    </p>
                    <p className="mt-0.5 text-[0.66rem] leading-relaxed text-slate-500">
                      {step.body}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </SectionCard>

          {latest && (
            <SectionCard
              title="Previous check-in"
              description={formatDateTime(latest.submittedAt)}
              icon={<ClipboardCheck className="h-4 w-4" />}
              action={<VerificationBadge status={latest.verificationStatus} />}
            >
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ["Pain", `${latest.painScore}/10`],
                  ["Breathless", `${latest.breathlessnessScore}/10`],
                  ["Temp", latest.temperatureC ? `${latest.temperatureC}°C` : "—"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-mist-50 py-2">
                    <p className="text-[0.55rem] uppercase tracking-wide text-slate-400">
                      {label}
                    </p>
                    <p className="text-sm font-semibold text-navy-950">{value}</p>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[0.7rem] leading-relaxed text-slate-600">
                {latest.overallFeeling} · {latest.adherence.replaceAll("_", " ")}
                {latest.missedDoses > 0 ? ` · ${latest.missedDoses} missed` : ""}
              </p>
              {latest.notes && (
                <p className="mt-1.5 rounded-lg bg-mist-50 px-2.5 py-2 text-[0.66rem] italic text-slate-500">
                  &ldquo;{latest.notes}&rdquo;
                </p>
              )}
            </SectionCard>
          )}

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
              <ShieldCheck className="h-4 w-4 text-care-700" /> Safety note
            </p>
            <p className="mt-1.5 text-[0.68rem] leading-relaxed text-slate-500">
              Rule alerts are flags, not diagnoses. A clinician reviews them. You can view
              the same alerts and their evidence in{" "}
              <Link
                href="/workspace/alerts"
                className="font-semibold text-care-700 hover:text-care-800"
              >
                Safety alerts
              </Link>
              .
            </p>
            <p className="mt-2 flex items-center gap-1.5 text-[0.62rem] text-slate-400">
              <Fingerprint className="h-3 w-3" /> Synthetic demo patient · not clinical use
            </p>
          </div>

          <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-mist-50 px-3 py-2.5 text-[0.66rem] leading-relaxed text-slate-500">
            <Stethoscope className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
            Your care team sees your report with a patient-reported badge, not as a
            verified clinical finding.
          </div>

          {twinState.data && twinState.data.openAlerts.length > 0 && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-[0.68rem] leading-relaxed text-amber-900">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {twinState.data.openAlerts.length} open alert
              {twinState.data.openAlerts.length === 1 ? "" : "s"} currently require review.
              Submitting another check-in adds new information; it does not close existing
              alerts.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
