import { ChevronRight, Fingerprint, Link2, UserRound } from "lucide-react";
import type { EvidenceSource, Provenance } from "@caretwin/contracts";
import { formatDateTime } from "@caretwin/shared";
import { RoleBadge, SourceChip, VerificationBadge } from "@/components/ui/badges";

export function ProvenanceDetails({
  provenance,
  evidence,
  compact = false,
}: {
  provenance?: Provenance;
  evidence?: EvidenceSource | null;
  compact?: boolean;
}) {
  if (!provenance) return null;
  return (
    <details className="group mt-2 rounded-lg border border-slate-200 bg-mist-50 text-xs [&_summary::-webkit-details-marker]:hidden">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-slate-600">
        <span className="flex min-w-0 items-center gap-2">
          <Fingerprint className="h-3.5 w-3.5 shrink-0 text-care-500" />
          <span className="truncate font-medium">Provenance & attribution</span>
        </span>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform group-open:rotate-90" />
      </summary>
      <div className="grid gap-2 border-t border-slate-200 px-3 py-3 text-[0.68rem] text-slate-600 sm:grid-cols-2">
        <div>
          <p className="font-semibold uppercase tracking-wide text-slate-500">Author</p>
          <p className="mt-0.5 flex items-center gap-1.5 font-medium text-navy-950">
            <UserRound className="h-3 w-3" /> {provenance.actorName ?? "Unknown"}
          </p>
          <div className="mt-1">
            <RoleBadge role={provenance.actorRole ?? "system"} />
          </div>
        </div>
        <div>
          <p className="font-semibold uppercase tracking-wide text-slate-500">Verification</p>
          <div className="mt-1">
            <VerificationBadge status={provenance.verificationStatus} />
          </div>
        </div>
        <div>
          <p className="font-semibold uppercase tracking-wide text-slate-500">Source</p>
          <div className="mt-1">
            <SourceChip evidence={evidence} />
          </div>
          {evidence && (
            <p className="mt-1 line-clamp-2 text-slate-500">{evidence.title}</p>
          )}
        </div>
        <div>
          <p className="font-semibold uppercase tracking-wide text-slate-500">Recorded</p>
          <p className="mt-0.5 font-medium text-navy-950">
            {formatDateTime(provenance.recordedAt)}
          </p>
          <p className="mt-1 flex items-center gap-1 text-slate-500">
            <Link2 className="h-3 w-3" />
            {provenance.sourceId ?? "No source identifier"}
          </p>
        </div>
        {!compact && (
          <>
            <div>
              <p className="font-semibold uppercase tracking-wide text-slate-500">
                AI extraction
              </p>
              <p className="mt-0.5 font-medium text-navy-950">
                {provenance.extractedByAi ? "Yes — source extraction" : "No"}
              </p>
            </div>
            <div>
              <p className="font-semibold uppercase tracking-wide text-slate-500">
                Human review
              </p>
              <p className="mt-0.5 font-medium text-navy-950">
                {provenance.reviewedBy ?? "Not reviewed"}
              </p>
            </div>
          </>
        )}
      </div>
    </details>
  );
}
