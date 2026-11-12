"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  ClipboardCheck,
  FileText,
  Filter,
  History,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { RecoveryEvent, TimelineResponse } from "@caretwin/contracts";
import { cn, formatDate, formatTime } from "@caretwin/shared";
import { eventTypeLabel } from "@caretwin/domain";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader } from "@/components/ui/cards";
import { Badge, SourceChip, VerificationBadge } from "@/components/ui/badges";
import { EmptyState, ErrorState, PageSkeleton } from "@/components/ui/feedback";
import { Tabs } from "@/components/ui/tabs";
import { Input, Select } from "@/components/ui/fields";
import { ApiClientError } from "@/lib/api";

type Tab = "all" | "patient" | "caregiver" | "alerts" | "verified" | "review";

const tabs: Array<{ value: Tab; label: string }> = [
  { value: "all", label: "All events" },
  { value: "patient", label: "Patient reports" },
  { value: "caregiver", label: "Caregiver" },
  { value: "alerts", label: "Alerts" },
  { value: "verified", label: "Verified" },
  { value: "review", label: "Needs review" },
];

function eventIcon(event: RecoveryEvent) {
  if (event.eventType === "safety_alert_raised" || event.eventType === "alert_acknowledged")
    return AlertTriangle;
  if (event.eventType === "checkin_submitted") return ClipboardCheck;
  if (event.eventType === "observation_recorded") return UserRound;
  if (
    event.eventType === "instruction_verified" ||
    event.eventType === "medication_verified"
  )
    return BadgeCheck;
  if (event.sourceType === "discharge_document") return FileText;
  if (event.eventType === "consent_updated") return ShieldCheck;
  return History;
}

function matchesTab(event: RecoveryEvent, tab: Tab) {
  if (tab === "all") return true;
  if (tab === "patient")
    return event.eventType === "checkin_submitted" || event.sourceType === "patient_report";
  if (tab === "caregiver")
    return (
      event.eventType === "observation_recorded" ||
      event.sourceType === "caregiver_report"
    );
  if (tab === "alerts")
    return (
      event.eventType === "safety_alert_raised" || event.eventType === "alert_acknowledged"
    );
  if (tab === "verified") return event.verificationStatus === "clinician_verified";
  return ["awaiting_review", "document_extracted", "ai_generated"].includes(
    event.verificationStatus,
  );
}

export default function TimelinePage() {
  const { patientId } = useSession();
  const state = useApi<TimelineResponse>(
    patientId ? `/patients/${patientId}/timeline?limit=200` : null,
  );
  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");
  const [sourceType, setSourceType] = useState("all");
  const [showPayload, setShowPayload] = useState(false);

  const filtered = useMemo(() => {
    const events = state.data?.events ?? [];
    const needle = search.trim().toLowerCase();
    return events.filter((event) => {
      if (!matchesTab(event, tab)) return false;
      if (sourceType !== "all" && event.sourceType !== sourceType) return false;
      if (!needle) return true;
      return `${event.title} ${event.description} ${event.actorName}`
        .toLowerCase()
        .includes(needle);
    });
  }, [state.data, tab, search, sourceType]);

  const grouped = useMemo(() => {
    const groups: Array<{ date: string; events: RecoveryEvent[] }> = [];
    for (const event of filtered) {
      const key = formatDate(event.occurredAt);
      const group = groups.find((item) => item.date === key);
      if (group) group.events.push(event);
      else groups.push({ date: key, events: [event] });
    }
    return groups;
  }, [filtered]);

  if (state.loading && !state.data) return <PageSkeleton />;
  if (state.error instanceof ApiClientError && state.error.status === 403) {
    return (
      <ErrorState
        error={state.error}
        title="Timeline is not shared with this role"
      />
    );
  }
  if (state.error) return <ErrorState error={state.error} onRetry={state.refresh} />;
  if (!state.data) return <PageSkeleton />;

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Recovery timeline"
        title="What happened, in order, with attribution."
        description="A chronological record of reports, observations, rule alerts, verification and consent changes. Events are not editable."
        actions={
          <Badge tone="slate">
            {filtered.length} of {state.data.total} events
          </Badge>
        }
      />

      <div className="mb-5 space-y-3 rounded-2xl border border-slate-200 bg-white p-3">
        <Tabs items={tabs} value={tab} onChange={setTab} />
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search events, actors or descriptions"
              className="pl-8"
              aria-label="Search timeline"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <Select
              value={sourceType}
              onChange={(event) => setSourceType(event.target.value)}
              aria-label="Filter by source type"
              className="sm:w-52"
            >
              <option value="all">All source types</option>
              <option value="discharge_document">Discharge document</option>
              <option value="patient_report">Patient report</option>
              <option value="caregiver_report">Caregiver report</option>
              <option value="clinician_note">Clinician note</option>
              <option value="monitoring_rule">Monitoring rule</option>
              <option value="system_demo">System / demo</option>
            </Select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-[0.66rem] text-slate-500">
          <input
            type="checkbox"
            checked={showPayload}
            onChange={(event) => setShowPayload(event.target.checked)}
            className="h-3.5 w-3.5 accent-care-600"
          />
          Show raw event payloads (inspectable demo state)
        </label>
      </div>

      {grouped.length === 0 ? (
        <EmptyState
          icon={<History className="h-4 w-4" />}
          title="No events match these filters"
          description="Try clearing the search or selecting a different event category."
        />
      ) : (
        <div className="space-y-6">
          {grouped.map((group) => (
            <div key={group.date}>
              <div className="mb-2 flex items-center gap-2">
                <span className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-slate-400">
                  {group.date}
                </span>
                <span className="h-px flex-1 bg-slate-200" />
                <span className="text-[0.6rem] text-slate-400">
                  {group.events.length} events
                </span>
              </div>
              <div className="relative space-y-2 border-l border-slate-200 pl-4">
                {group.events.map((event) => {
                  const Icon = eventIcon(event);
                  const alertEvent =
                    event.eventType === "safety_alert_raised" ||
                    event.eventType === "alert_acknowledged";
                  return (
                    <div key={event.id} className="relative">
                      <span
                        className={cn(
                          "absolute -left-[1.47rem] top-4 flex h-5 w-5 items-center justify-center rounded-full ring-4 ring-mist-50",
                          alertEvent
                            ? "bg-rose-50 text-rose-600"
                            : event.verificationStatus === "clinician_verified"
                              ? "bg-care-50 text-care-700"
                              : "bg-white text-slate-500 ring-1 ring-slate-200",
                        )}
                      >
                        <Icon className="h-2.5 w-2.5" />
                      </span>
                      <div
                        className={cn(
                          "rounded-xl border bg-white p-3.5",
                          alertEvent ? "border-rose-200" : "border-slate-200/80",
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-navy-950">
                              {event.title}
                            </p>
                            <p className="mt-0.5 text-[0.62rem] text-slate-400">
                              {formatTime(event.occurredAt)} · {event.actorName} ·{" "}
                              {event.actorRole} · {eventTypeLabel(event.eventType)}
                            </p>
                          </div>
                          <VerificationBadge status={event.verificationStatus} />
                        </div>
                        <p className="mt-1.5 text-[0.72rem] leading-relaxed text-slate-600">
                          {event.description}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <SourceChip evidence={event.evidence} />
                          <Badge tone="slate">{event.sourceType.replaceAll("_", " ")}</Badge>
                          {event.reviewStatus !== "not_required" && (
                            <Badge
                              tone={
                                event.reviewStatus === "reviewed" ? "teal" : "amber"
                              }
                            >
                              review: {event.reviewStatus}
                            </Badge>
                          )}
                        </div>
                        {event.evidence?.excerpt && (
                          <details className="mt-2 text-[0.66rem] text-slate-500">
                            <summary className="cursor-pointer font-semibold text-slate-500">
                              Source excerpt
                            </summary>
                            <p className="mt-1 rounded-md bg-mist-50 px-2.5 py-1.5 italic">
                              &ldquo;{event.evidence.excerpt}&rdquo;
                            </p>
                          </details>
                        )}
                        {showPayload && (
                          <pre className="mt-2 overflow-x-auto rounded-md bg-navy-950 p-2 text-[0.6rem] leading-relaxed text-care-200">
                            {JSON.stringify(event.payload, null, 2)}
                          </pre>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
