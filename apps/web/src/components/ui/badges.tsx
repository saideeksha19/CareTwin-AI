import type { ReactNode } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  Bot,
  Circle,
  Clock3,
  FileText,
  FlaskConical,
  HeartPulse,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { cn } from "@caretwin/shared";
import type {
  AlertSeverity,
  EvidenceSource,
  SourceType,
  TwinStatus,
  UserRole,
  VerificationStatus,
} from "@caretwin/contracts";
import {
  twinStatusLabel,
  verificationLabel,
  verificationTone,
} from "@caretwin/domain";
import { mustShowReviewBadge } from "@caretwin/safety";

type Tone = "slate" | "teal" | "amber" | "rose" | "blue" | "violet" | "emerald" | "navy";

const tones: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-600 ring-slate-200",
  teal: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  rose: "bg-rose-50 text-rose-700 ring-rose-200",
  blue: "bg-sky-50 text-sky-700 ring-sky-200",
  violet: "bg-violet-50 text-violet-700 ring-violet-200",
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  navy: "bg-mist-100 text-navy-900 ring-slate-200",
};

export function Badge({
  children,
  tone = "slate",
  className,
  dot = false,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.64rem] font-semibold ring-1 ring-inset",
        tones[tone],
        className,
      )}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />}
      {children}
    </span>
  );
}

export function StatusPill({ status }: { status: TwinStatus }) {
  const tone = status === "on_track" ? "teal" : status === "needs_attention" ? "amber" : "rose";
  const Icon = status === "on_track" ? ShieldCheck : AlertTriangle;
  return (
    <Badge tone={tone} dot={false}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {twinStatusLabel(status)}
    </Badge>
  );
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const map: Record<AlertSeverity, { tone: Tone; label: string }> = {
    info: { tone: "blue", label: "Info" },
    moderate: { tone: "amber", label: "Moderate" },
    urgent: { tone: "rose", label: "Urgent" },
    critical: { tone: "rose", label: "Critical" },
  };
  return <Badge tone={map[severity].tone} dot>{map[severity].label}</Badge>;
}

export function RoleBadge({ role }: { role: UserRole | "system" }) {
  const map: Record<string, { tone: Tone; label: string }> = {
    patient: { tone: "teal", label: "Patient" },
    caregiver: { tone: "violet", label: "Caregiver" },
    clinician: { tone: "blue", label: "Clinician" },
    system: { tone: "slate", label: "System" },
  };
  const item = map[role] ?? map.system;
  return <Badge tone={item.tone}>{item.label}</Badge>;
}

const verificationIcons: Record<VerificationStatus, ReactNode> = {
  clinician_verified: <BadgeCheck className="h-3 w-3" />,
  document_extracted: <FileText className="h-3 w-3" />,
  patient_reported: <UserRound className="h-3 w-3" />,
  caregiver_reported: <HeartPulse className="h-3 w-3" />,
  ai_generated: <Bot className="h-3 w-3" />,
  simulated_demo: <FlaskConical className="h-3 w-3" />,
  awaiting_review: <Clock3 className="h-3 w-3" />,
  rejected: <AlertTriangle className="h-3 w-3" />,
};

export function VerificationBadge({
  status,
  showReviewHint = true,
}: {
  status: VerificationStatus;
  showReviewHint?: boolean;
}) {
  const tone = verificationTone(status);
  const toneMap = {
    verified: "teal",
    review: "amber",
    reported: "blue",
    ai: "violet",
    neutral: "slate",
  } as const;
  return (
    <Badge tone={toneMap[tone]}>
      {verificationIcons[status]}
      {verificationLabel(status)}
      {showReviewHint && mustShowReviewBadge(status) && (
        <span className="sr-only">Requires review before trusted use</span>
      )}
    </Badge>
  );
}

const sourceLabels: Record<SourceType, string> = {
  discharge_document: "Discharge document",
  patient_report: "Patient report",
  caregiver_report: "Caregiver report",
  clinician_note: "Clinician note",
  system_demo: "System / demo",
  monitoring_rule: "Monitoring rule",
  ai_output: "AI output",
};

export function SourceChip({
  evidence,
  className,
}: {
  evidence?: EvidenceSource | null;
  className?: string;
}) {
  if (!evidence) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-2 py-1 text-[0.64rem] font-medium text-slate-500",
          className,
        )}
      >
        <Circle className="h-2.5 w-2.5" /> No linked source
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-md border border-slate-200 bg-mist-50 px-2 py-1 text-[0.64rem] font-medium text-slate-600",
        className,
      )}
      title={`${evidence.title} · ${evidence.pageRef}`}
    >
      <FileText className="h-3 w-3 shrink-0 text-care-500" />
      <span className="truncate">{sourceLabels[evidence.sourceType]}</span>
      <span className="shrink-0 text-slate-400">·</span>
      <span className="shrink-0 font-mono text-[0.6rem] text-slate-500">
        {evidence.pageRef}
      </span>
    </span>
  );
}

export function SourceTypeBadge({ type }: { type: SourceType }) {
  return <Badge tone="slate">{sourceLabels[type]}</Badge>;
}

export function MaturityBadge({ status }: { status: string }) {
  const map: Record<string, { tone: Tone; label: string }> = {
    working_deterministic: { tone: "teal", label: "Working · deterministic" },
    working_permissions: { tone: "teal", label: "Working · permissions" },
    architecturally_prepared: { tone: "blue", label: "Architecturally prepared" },
    requires_ai_configuration: { tone: "amber", label: "Needs AI configuration" },
  };
  const item = map[status] ?? { tone: "slate" as Tone, label: status };
  return <Badge tone={item.tone}>{item.label}</Badge>;
}

export function AlertSeverityDot({ severity }: { severity: AlertSeverity }) {
  const color =
    severity === "critical"
      ? "bg-rose-500"
      : severity === "urgent"
        ? "bg-rose-400"
        : severity === "moderate"
          ? "bg-amber-400"
          : "bg-sky-400";
  return <span className={cn("h-2 w-2 rounded-full", color)} aria-hidden="true" />;
}
