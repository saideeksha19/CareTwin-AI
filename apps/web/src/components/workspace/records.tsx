"use client";

import { useState } from "react";
import { CheckCircle2, Circle, Clock3, FileWarning, Pill } from "lucide-react";
import type {
  FollowUp,
  MedicationInstruction,
  Milestone,
  SafetyDecision,
} from "@caretwin/contracts";
import { cn, formatDate, formatDateTime } from "@caretwin/shared";
import { Badge, SourceChip, VerificationBadge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";

const milestoneTone: Record<string, "teal" | "amber" | "slate" | "rose" | "blue"> = {
  completed: "teal",
  in_progress: "blue",
  pending: "slate",
  overdue: "rose",
  not_applicable: "slate",
};

export function MilestoneRow({ milestone }: { milestone: Milestone }) {
  const tone = milestoneTone[milestone.status] ?? "slate";
  return (
    <div className="flex gap-3 border-b border-slate-100 py-3 last:border-0 last:pb-0 first:pt-0">
      <span
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-1",
          milestone.status === "completed"
            ? "bg-care-50 text-care-600 ring-care-200"
            : milestone.status === "overdue"
              ? "bg-rose-50 text-rose-600 ring-rose-200"
              : "bg-mist-50 text-slate-400 ring-slate-200",
        )}
      >
        {milestone.status === "completed" ? (
          <CheckCircle2 className="h-3.5 w-3.5" />
        ) : milestone.status === "in_progress" ? (
          <Clock3 className="h-3.5 w-3.5" />
        ) : (
          <Circle className="h-3 w-3" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p
            className={cn(
              "text-xs font-semibold",
              milestone.status === "completed" ? "text-slate-500" : "text-navy-950",
            )}
          >
            {milestone.title}
          </p>
          <div className="flex items-center gap-1.5">
            <Badge tone={tone}>{milestone.status.replaceAll("_", " ")}</Badge>
            <VerificationBadge status={milestone.verificationStatus} showReviewHint={false} />
          </div>
        </div>
        <p className="mt-0.5 text-[0.7rem] leading-relaxed text-slate-500">
          {milestone.description}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[0.64rem] text-slate-400">
          <span>Due {formatDate(milestone.dueDate)}</span>
          {milestone.completedAt && <span>Completed {formatDate(milestone.completedAt)}</span>}
          <SourceChip evidence={milestone.evidence} />
        </div>
      </div>
    </div>
  );
}

export function MedicationRow({
  medication,
  canVerify = false,
  onVerify,
  verifying = false,
}: {
  medication: MedicationInstruction;
  canVerify?: boolean;
  onVerify?: (note: string) => void;
  verifying?: boolean;
}) {
  const [note, setNote] = useState("");
  const needsReview =
    medication.verificationStatus === "awaiting_review" ||
    medication.verificationStatus === "document_extracted";

  return (
    <div className="rounded-xl border border-slate-200/80 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-mist-100 text-care-700">
            <Pill className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-semibold text-navy-950">{medication.name}</p>
            <p className="text-[0.7rem] text-slate-500">
              {medication.dosage} · {medication.route} · {medication.frequency} ·{" "}
              {medication.duration}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <VerificationBadge status={medication.verificationStatus} />
          {needsReview && (
            <Badge tone="amber">
              <FileWarning className="h-3 w-3" /> Review
            </Badge>
          )}
        </div>
      </div>
      <p className="mt-2.5 text-xs leading-relaxed text-slate-600">
        {medication.instructions}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <SourceChip evidence={medication.evidence} />
        <span className="text-[0.64rem] text-slate-400">
          Prescribed by {medication.prescribedBy}
        </span>
      </div>
      {canVerify && needsReview && onVerify && (
        <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3 sm:flex-row sm:items-center">
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Review note (optional)"
            maxLength={1000}
            className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs focus:border-care-500 focus:outline-none focus:ring-2 focus:ring-care-500/15"
            aria-label={`Verification note for ${medication.name}`}
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={verifying}
            onClick={() => {
              onVerify(note);
              setNote("");
            }}
            className="shrink-0"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {verifying ? "Verifying…" : "Verify against source"}
          </Button>
        </div>
      )}
    </div>
  );
}

export function FollowUpRow({ followUp }: { followUp: FollowUp }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-xl border border-slate-200/80 bg-white p-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p className="text-sm font-semibold text-navy-950">{followUp.title}</p>
        <p className="mt-0.5 text-[0.7rem] text-slate-500">
          {followUp.clinicianName} · {followUp.specialty}
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {formatDateTime(followUp.scheduledFor)} · {followUp.location}
        </p>
        <p className="mt-1 text-[0.7rem] leading-relaxed text-slate-500">{followUp.notes}</p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <SourceChip evidence={followUp.evidence} />
          <VerificationBadge status={followUp.verificationStatus} showReviewHint={false} />
        </div>
      </div>
      <Badge tone={followUp.status === "completed" ? "teal" : "blue"}>{followUp.status}</Badge>
    </div>
  );
}

export function SafetyDecisionCard({
  decision,
  compact = false,
}: {
  decision: SafetyDecision;
  compact?: boolean;
}) {
  const tone =
    decision.outcome === "allowed"
      ? "teal"
      : decision.outcome === "allowed_with_alerts"
        ? "amber"
        : "rose";
  return (
    <div className={cn("rounded-xl border border-slate-200/80 bg-white p-4", compact && "p-3")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-care-50 text-care-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
          </span>
          Safety decision · {decision.operation}
        </p>
        <Badge tone={tone}>{decision.outcome.replaceAll("_", " ")}</Badge>
      </div>
      <div className="mt-2.5 space-y-1.5">
        {decision.checks.map((check) => (
          <div key={check.code} className="flex items-start gap-2 text-[0.7rem]">
            <span
              className={cn(
                "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full",
                check.passed ? "bg-care-50 text-care-700" : "bg-rose-50 text-rose-600",
              )}
            >
              {check.passed ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <FileWarning className="h-3 w-3" />
              )}
            </span>
            <span className="text-slate-600">
              <span className="font-semibold text-navy-900">{check.label}:</span>{" "}
              {check.detail}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[0.6rem] text-slate-400">
        {decision.id} · {decision.actorName} · {formatDateTime(decision.createdAt)}
      </p>
    </div>
  );
}
