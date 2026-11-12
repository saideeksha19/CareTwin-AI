"use client";

import { useState } from "react";
import { AlertTriangle, Check, ChevronRight, Clock3, ShieldCheck } from "lucide-react";
import type { SafetyAlert } from "@caretwin/contracts";
import { cn, formatDateTime, formatRelative } from "@caretwin/shared";
import { Button } from "@/components/ui/button";
import { Badge, SeverityBadge, SourceChip } from "@/components/ui/badges";

export function AlertCard({
  alert,
  canAcknowledge = false,
  onAcknowledge,
  acknowledging = false,
  canResolve = false,
  onResolve,
  resolving = false,
}: {
  alert: SafetyAlert;
  canAcknowledge?: boolean;
  onAcknowledge?: (note: string) => void;
  acknowledging?: boolean;
  canResolve?: boolean;
  onResolve?: (note: string) => void;
  resolving?: boolean;
}) {
  const [note, setNote] = useState("");
  const [resolveNote, setResolveNote] = useState("");
  const [open, setOpen] = useState(false);

  return (
    <div
      className={cn(
        "rounded-xl border bg-white",
        alert.status === "open" && alert.severity === "critical"
          ? "border-rose-300"
          : alert.status === "open"
            ? "border-slate-200"
            : "border-slate-200/70 bg-mist-50/40",
      )}
    >
      <div className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 items-start gap-2.5">
            <span
              className={cn(
                "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                alert.severity === "critical" || alert.severity === "urgent"
                  ? "bg-rose-50 text-rose-600"
                  : alert.severity === "moderate"
                    ? "bg-amber-50 text-amber-600"
                    : "bg-sky-50 text-sky-600",
              )}
            >
              <AlertTriangle className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-navy-950">{alert.title}</p>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.66rem] text-slate-500">
                <span className="font-mono">{alert.ruleId}</span>
                <span>·</span>
                <span className="inline-flex items-center gap-1">
                  <Clock3 className="h-3 w-3" /> {formatRelative(alert.createdAt)}
                </span>
                <span>·</span>
                <span>{alert.category.replaceAll("_", " ")}</span>
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <SeverityBadge severity={alert.severity} />
            <Badge
              tone={
                alert.status === "open"
                  ? "rose"
                  : alert.status === "acknowledged"
                    ? "blue"
                    : "slate"
              }
              dot
            >
              {alert.status}
            </Badge>
          </div>
        </div>

        <p className="mt-2.5 text-xs leading-relaxed text-slate-600">{alert.rationale}</p>

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <SourceChip evidence={alert.evidence} />
          {alert.acknowledgedBy && (
            <Badge tone="blue">
              <Check className="h-3 w-3" /> Ack by {alert.acknowledgedBy}
            </Badge>
          )}
          {alert.resolvedBy && (
            <Badge tone="teal">
              <ShieldCheck className="h-3 w-3" /> Resolved by {alert.resolvedBy}
            </Badge>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between gap-2">
          <button
            onClick={() => setOpen((value) => !value)}
            className="inline-flex items-center gap-1 text-[0.66rem] font-semibold text-slate-500 hover:text-navy-900"
            aria-expanded={open}
          >
            <ChevronRight
              className={cn("h-3 w-3 transition-transform", open && "rotate-90")}
            />
            Why this fired
          </button>
          <span className="text-[0.62rem] text-slate-400">
            {formatDateTime(alert.createdAt)}
          </span>
        </div>

        {open && (
          <div className="mt-2 space-y-2 rounded-lg border border-slate-200/70 bg-mist-50 px-3 py-2 text-[0.68rem] leading-relaxed text-slate-600">
            <p>
              <span className="font-semibold text-navy-900">Rule:</span>{" "}
              <span className="font-mono">{alert.ruleId}</span> ·{" "}
              <span className="font-semibold text-navy-900">Severity:</span>{" "}
              {alert.severity}
            </p>
            <p>
              <span className="font-semibold text-navy-900">Rationale:</span>{" "}
              {alert.rationale}
            </p>
            {alert.evidence && (
              <>
                <p>
                  <span className="font-semibold text-navy-900">Evidence:</span>{" "}
                  {alert.evidence.title} — {alert.evidence.pageRef}
                </p>
                <p className="rounded bg-white px-2 py-1.5 italic">
                  &ldquo;{alert.evidence.excerpt}&rdquo;
                </p>
              </>
            )}
          </div>
        )}

        {alert.status !== "open" && (
          <p className="mt-2 flex items-start gap-1.5 rounded-lg border border-care-100 bg-care-50/60 px-3 py-2 text-[0.68rem] leading-relaxed text-care-900">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-care-600" />
            <span>
              {alert.status === "resolved"
                ? alert.resolvedBy
                  ? `Resolved by ${alert.resolvedBy}: `
                  : "Resolved: "
                : alert.acknowledgedBy
                  ? `Acknowledged by ${alert.acknowledgedBy}: `
                  : "Acknowledged: "}
              {alert.resolutionNote ||
                (alert.status === "resolved"
                  ? "Resolution recorded."
                  : "Review recorded; the concern remains open until resolved.")}
            </span>
          </p>
        )}

        {canAcknowledge && alert.status === "open" && onAcknowledge && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <label
              htmlFor={`ack-note-${alert.id}`}
              className="text-[0.65rem] font-semibold text-slate-600"
            >
              Acknowledgment note (optional)
            </label>
            <textarea
              id={`ack-note-${alert.id}`}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="What was reviewed or what happens next?"
              className="mt-1 min-h-14 w-full rounded-lg border border-slate-300 px-2.5 py-2 text-xs focus:border-care-500 focus:outline-none focus:ring-2 focus:ring-care-500/15"
              maxLength={1000}
            />
            <div className="mt-1.5 flex justify-end">
              <Button
                size="sm"
                variant="secondary"
                disabled={acknowledging}
                onClick={() => {
                  onAcknowledge(note);
                  setNote("");
                }}
              >
                <Check className="h-3.5 w-3.5" />
                {acknowledging ? "Acknowledging..." : "Acknowledge alert"}
              </Button>
            </div>
          </div>
        )}

        {canResolve && alert.status === "acknowledged" && onResolve && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <label
              htmlFor={`resolve-note-${alert.id}`}
              className="text-[0.65rem] font-semibold text-slate-600"
            >
              Resolution rationale (required)
            </label>
            <textarea
              id={`resolve-note-${alert.id}`}
              value={resolveNote}
              onChange={(event) => setResolveNote(event.target.value)}
              placeholder="Why is this concern resolved, and what follow-up was completed?"
              className="mt-1 min-h-14 w-full rounded-lg border border-slate-300 px-2.5 py-2 text-xs focus:border-care-500 focus:outline-none focus:ring-2 focus:ring-care-500/15"
              maxLength={1000}
            />
            <div className="mt-1.5 flex justify-end">
              <Button
                size="sm"
                variant="primary"
                disabled={resolving || resolveNote.trim().length < 3}
                onClick={() => {
                  onResolve(resolveNote.trim());
                  setResolveNote("");
                }}
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                {resolving ? "Resolving..." : "Resolve alert"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
