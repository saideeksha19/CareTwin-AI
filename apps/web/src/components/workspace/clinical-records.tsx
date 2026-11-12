"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FlaskConical, Plus, RefreshCw, Stethoscope, X } from "lucide-react";
import { formatDateTime } from "@caretwin/shared";
import { ApiClientError, apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { fetchReportComparison, type ReportComparison } from "@/lib/documents";
import { Badge, SourceChip, VerificationBadge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/fields";
import {
  AccessRestricted,
  EmptyState,
  ErrorState,
  InlineMessage,
  PageSkeleton,
} from "@/components/ui/feedback";

type LabResult = {
  id: string;
  testCode: string;
  testName: string;
  panel?: string;
  specimen?: string;
  collectedAt: string;
  resultedAt?: string | null;
  valueNumeric?: number | null;
  valueText?: string;
  unit?: string;
  sourceRangeLow?: number | null;
  sourceRangeHigh?: number | null;
  sourceRangeText?: string;
  clinicianRangeLow?: number | null;
  clinicianRangeHigh?: number | null;
  clinicianRangeText?: string;
  comparisonStatus?: string;
  comparisonNote?: string;
  ambiguityNote?: string;
  verificationStatus: string;
  evidence?: any;
  provenance?: any;
};

type ClinicalEncounter = {
  id: string;
  encounterType: string;
  occurredAt: string;
  endedAt?: string | null;
  facility?: string;
  providerName?: string;
  providerSpecialty?: string;
  reason?: string;
  summary: string;
  dischargeInstructions?: string;
  followUpPlan?: string;
  sourceDocument?: string;
  verificationStatus: string;
  evidence?: any;
  provenance?: any;
  links?: Array<{ id: string; entityType: string; entityId: string; label?: string }>;
};

function valueDisplay(lab: LabResult): string {
  if (lab.valueNumeric !== null && lab.valueNumeric !== undefined) {
    return `${lab.valueNumeric}${lab.unit ? ` ${lab.unit}` : ""}`.trim();
  }
  return [lab.valueText, lab.unit].filter(Boolean).join(" ").trim() || "—";
}

function rangeDisplay(lab: LabResult): string {
  if (lab.sourceRangeText) return lab.sourceRangeText;
  if (lab.clinicianRangeText) return lab.clinicianRangeText;
  if (lab.sourceRangeLow != null || lab.sourceRangeHigh != null) {
    const low = lab.sourceRangeLow ?? "—";
    const high = lab.sourceRangeHigh ?? "—";
    return `${low}-${high}${lab.unit ? ` ${lab.unit}` : ""}`;
  }
  if (lab.clinicianRangeLow != null || lab.clinicianRangeHigh != null) {
    const low = lab.clinicianRangeLow ?? "—";
    const high = lab.clinicianRangeHigh ?? "—";
    return `${low}-${high}${lab.unit ? ` ${lab.unit}` : ""}`;
  }
  return "No reference range provided";
}

function toIso(local: string): string {
  // datetime-local gives "YYYY-MM-DDTHH:mm" (no timezone). Treat as local and convert to ISO.
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return local;
  return d.toISOString();
}

function numOrNull(v: string): number | null {
  const t = v.trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

function LabCreateForm({ onCreated }: { onCreated: () => void }) {
  const { patientId, selectedUser } = useSession();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState({
    testCode: "",
    testName: "",
    panel: "",
    specimen: "",
    collectedAt: "",
    resultedAt: "",
    valueNumeric: "",
    valueText: "",
    unit: "",
    sourceRangeLow: "",
    sourceRangeHigh: "",
    sourceRangeText: "",
    comparisonStatus: "unavailable",
    comparisonNote: "",
    ambiguityNote: "",
    verificationStatus: "document_extracted",
    sourceType: "clinician_note",
    evidenceTitle: "",
    evidenceExcerpt: "",
    evidenceDocumentName: "Clinical record",
  });

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function submit() {
    if (!patientId || !selectedUser) return;
    setError(null);
    setSuccess(null);
    if (!form.testCode.trim() || !form.testName.trim()) return setError("Test code and test name are required.");
    if (!form.collectedAt) return setError("Collected date/time is required.");
    if (!form.unit.trim()) return setError("Exact supplied unit is required. Do not infer units.");
    if (!form.valueNumeric.trim() && !form.valueText.trim()) return setError("Provide either a numeric value or a text value.");
    if (form.valueNumeric.trim() && !Number.isFinite(Number(form.valueNumeric))) return setError("Numeric value must be a valid number.");

    setSubmitting(true);
    try {
      await apiRequest(`/patients/${patientId}/labs`, {
        method: "POST",
        userId: selectedUser.id,
        body: {
          testCode: form.testCode.trim(),
          testName: form.testName.trim(),
          panel: form.panel.trim(),
          specimen: form.specimen.trim(),
          collectedAt: toIso(form.collectedAt),
          resultedAt: form.resultedAt ? toIso(form.resultedAt) : null,
          valueNumeric: form.valueNumeric.trim() ? Number(form.valueNumeric) : null,
          valueText: form.valueText.trim(),
          unit: form.unit.trim(),
          sourceRangeLow: numOrNull(form.sourceRangeLow),
          sourceRangeHigh: numOrNull(form.sourceRangeHigh),
          sourceRangeText: form.sourceRangeText.trim(),
          comparisonStatus: form.comparisonStatus,
          comparisonNote: form.comparisonNote.trim(),
          ambiguityNote: form.ambiguityNote.trim(),
          verificationStatus: form.verificationStatus,
          sourceType: form.sourceType,
          evidenceTitle: form.evidenceTitle.trim(),
          evidenceExcerpt: form.evidenceExcerpt.trim(),
          evidenceDocumentName: form.evidenceDocumentName.trim() || "Clinical record",
        },
      });
      setSuccess("Lab result recorded and linked to the timeline/twin with provenance.");
      setForm((f) => ({ ...f, testCode: "", testName: "", valueNumeric: "", valueText: "", comparisonNote: "", ambiguityNote: "", evidenceTitle: "", evidenceExcerpt: "" }));
      setOpen(false);
      onCreated();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-2">
      {success && <InlineMessage tone="success">{success}</InlineMessage>}
      {!open ? (
        <Button type="button" size="sm" variant="secondary" onClick={() => setOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Record lab result
        </Button>
      ) : (
        <div className="rounded-xl border border-care-200 bg-care-50/30 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-navy-950">Create lab result (clinician)</p>
            <button type="button" onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-600"><X className="h-4 w-4" /></button>
          </div>
          <p className="text-[0.66rem] text-slate-500">Enter exact supplied values and units. Provide reference ranges only when supplied by an authoritative source; never inferred.</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Test code *" htmlFor="lab-code"><Input id="lab-code" value={form.testCode} onChange={(e) => set("testCode", e.target.value)} /></Field>
            <Field label="Test name *" htmlFor="lab-name"><Input id="lab-name" value={form.testName} onChange={(e) => set("testName", e.target.value)} /></Field>
            <Field label="Panel" htmlFor="lab-panel"><Input id="lab-panel" value={form.panel} onChange={(e) => set("panel", e.target.value)} /></Field>
            <Field label="Specimen" htmlFor="lab-specimen"><Input id="lab-specimen" value={form.specimen} onChange={(e) => set("specimen", e.target.value)} /></Field>
            <Field label="Collected at *" htmlFor="lab-collected"><Input id="lab-collected" type="datetime-local" value={form.collectedAt} onChange={(e) => set("collectedAt", e.target.value)} /></Field>
            <Field label="Resulted at" htmlFor="lab-resulted"><Input id="lab-resulted" type="datetime-local" value={form.resultedAt} onChange={(e) => set("resultedAt", e.target.value)} /></Field>
            <Field label="Numeric value" htmlFor="lab-value-num"><Input id="lab-value-num" inputMode="decimal" value={form.valueNumeric} onChange={(e) => set("valueNumeric", e.target.value)} /></Field>
            <Field label="Text value" htmlFor="lab-value-text"><Input id="lab-value-text" value={form.valueText} onChange={(e) => set("valueText", e.target.value)} /></Field>
            <Field label="Unit (exact, required) *" htmlFor="lab-unit" hint="Required. Not inferred."><Input id="lab-unit" value={form.unit} onChange={(e) => set("unit", e.target.value)} placeholder="e.g. mg/L" /></Field>
            <Field label="Comparison status" htmlFor="lab-cmp"><Select id="lab-cmp" value={form.comparisonStatus} onChange={(e) => set("comparisonStatus", e.target.value)}><option value="unavailable">unavailable</option><option value="in_range">in_range</option><option value="above_range">above_range</option><option value="below_range">below_range</option><option value="abnormal">abnormal</option></Select></Field>
            <Field label="Source range low (if supplied)" htmlFor="lab-rlo"><Input id="lab-rlo" inputMode="decimal" value={form.sourceRangeLow} onChange={(e) => set("sourceRangeLow", e.target.value)} /></Field>
            <Field label="Source range high (if supplied)" htmlFor="lab-rhi"><Input id="lab-rhi" inputMode="decimal" value={form.sourceRangeHigh} onChange={(e) => set("sourceRangeHigh", e.target.value)} /></Field>
            <Field label="Source range text (if supplied)" htmlFor="lab-rtxt"><Input id="lab-rtxt" value={form.sourceRangeText} onChange={(e) => set("sourceRangeText", e.target.value)} /></Field>
            <Field label="Verification status" htmlFor="lab-ver"><Select id="lab-ver" value={form.verificationStatus} onChange={(e) => set("verificationStatus", e.target.value)}><option value="document_extracted">document_extracted</option><option value="clinician_verified">clinician_verified</option><option value="awaiting_review">awaiting_review</option><option value="patient_reported">patient_reported</option><option value="caregiver_reported">caregiver_reported</option></Select></Field>
          </div>
          <Field label="Comparison/ambiguity note" htmlFor="lab-note"><Textarea id="lab-note" value={form.comparisonNote} onChange={(e) => set("comparisonNote", e.target.value)} /></Field>
          <Field label="Evidence excerpt (provenance)" htmlFor="lab-ev"><Textarea id="lab-ev" value={form.evidenceExcerpt} onChange={(e) => set("evidenceExcerpt", e.target.value)} placeholder="Source excerpt or note supporting this result" /></Field>
          {error && <InlineMessage tone="error">{error}</InlineMessage>}
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="button" size="sm" disabled={submitting} onClick={() => void submit()}>{submitting ? "Saving…" : "Save lab result"}</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function EncounterCreateForm({ onCreated }: { onCreated: () => void }) {
  const { patientId, selectedUser } = useSession();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState({
    encounterType: "",
    occurredAt: "",
    endedAt: "",
    facility: "",
    providerName: "",
    providerSpecialty: "",
    reason: "",
    summary: "",
    dischargeInstructions: "",
    followUpPlan: "",
    sourceDocument: "",
    verificationStatus: "document_extracted",
    evidenceExcerpt: "",
  });

  function set<K extends keyof typeof form>(k: K, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  async function submit() {
    if (!patientId || !selectedUser) return;
    setError(null); setSuccess(null);
    if (!form.encounterType.trim() || form.encounterType.trim().length < 2) return setError("Encounter type is required.");
    if (!form.occurredAt) return setError("Encounter date/time is required.");
    if (!form.summary.trim() || form.summary.trim().length < 3) return setError("Clinical summary is required.");
    if (!form.providerName.trim()) return setError("Clinician/provider name is required.");
    setSubmitting(true);
    try {
      await apiRequest(`/patients/${patientId}/encounters`, {
        method: "POST",
        userId: selectedUser.id,
        body: {
          encounterType: form.encounterType.trim(),
          occurredAt: toIso(form.occurredAt),
          endedAt: form.endedAt ? toIso(form.endedAt) : null,
          facility: form.facility.trim(),
          providerName: form.providerName.trim(),
          providerSpecialty: form.providerSpecialty.trim(),
          reason: form.reason.trim(),
          summary: form.summary.trim(),
          dischargeInstructions: form.dischargeInstructions.trim(),
          followUpPlan: form.followUpPlan.trim(),
          sourceDocument: form.sourceDocument.trim(),
          verificationStatus: form.verificationStatus,
          evidenceExcerpt: form.evidenceExcerpt.trim(),
        },
      });
      setSuccess("Clinical encounter recorded with provenance and linked to the timeline/twin.");
      setOpen(false);
      setForm((f) => ({ ...f, encounterType: "", reason: "", summary: "", dischargeInstructions: "", followUpPlan: "", evidenceExcerpt: "" }));
      onCreated();
    } catch (e) { setError(errorMessage(e)); } finally { setSubmitting(false); }
  }

  return (
    <div className="space-y-2">
      {success && <InlineMessage tone="success">{success}</InlineMessage>}
      {!open ? (
        <Button type="button" size="sm" variant="secondary" onClick={() => setOpen(true)}><Plus className="h-3.5 w-3.5" /> Record encounter</Button>
      ) : (
        <div className="rounded-xl border border-care-200 bg-care-50/30 p-4 space-y-3">
          <div className="flex items-center justify-between"><p className="text-xs font-semibold text-navy-950">Create clinical encounter (clinician)</p><button type="button" onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-600"><X className="h-4 w-4" /></button></div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Encounter type *" htmlFor="enc-type"><Input id="enc-type" value={form.encounterType} onChange={(e) => set("encounterType", e.target.value)} /></Field>
            <Field label="Occurred at *" htmlFor="enc-at"><Input id="enc-at" type="datetime-local" value={form.occurredAt} onChange={(e) => set("occurredAt", e.target.value)} /></Field>
            <Field label="Ended at" htmlFor="enc-end"><Input id="enc-end" type="datetime-local" value={form.endedAt} onChange={(e) => set("endedAt", e.target.value)} /></Field>
            <Field label="Facility" htmlFor="enc-fac"><Input id="enc-fac" value={form.facility} onChange={(e) => set("facility", e.target.value)} /></Field>
            <Field label="Provider/clinician name *" htmlFor="enc-prov"><Input id="enc-prov" value={form.providerName} onChange={(e) => set("providerName", e.target.value)} /></Field>
            <Field label="Provider specialty" htmlFor="enc-spec"><Input id="enc-spec" value={form.providerSpecialty} onChange={(e) => set("providerSpecialty", e.target.value)} /></Field>
            <Field label="Source document" htmlFor="enc-src"><Input id="enc-src" value={form.sourceDocument} onChange={(e) => set("sourceDocument", e.target.value)} /></Field>
            <Field label="Verification status" htmlFor="enc-ver"><Select id="enc-ver" value={form.verificationStatus} onChange={(e) => set("verificationStatus", e.target.value)}><option value="document_extracted">document_extracted</option><option value="clinician_verified">clinician_verified</option><option value="awaiting_review">awaiting_review</option><option value="patient_reported">patient_reported</option></Select></Field>
          </div>
          <Field label="Reason" htmlFor="enc-reason"><Input id="enc-reason" value={form.reason} onChange={(e) => set("reason", e.target.value)} /></Field>
          <Field label="Clinical summary *" htmlFor="enc-sum"><Textarea id="enc-sum" value={form.summary} onChange={(e) => set("summary", e.target.value)} /></Field>
          <Field label="Follow-up plan" htmlFor="enc-fu"><Textarea id="enc-fu" value={form.followUpPlan} onChange={(e) => set("followUpPlan", e.target.value)} /></Field>
          <Field label="Discharge instructions" htmlFor="enc-dc"><Textarea id="enc-dc" value={form.dischargeInstructions} onChange={(e) => set("dischargeInstructions", e.target.value)} /></Field>
          <Field label="Evidence/provenance excerpt" htmlFor="enc-ev"><Textarea id="enc-ev" value={form.evidenceExcerpt} onChange={(e) => set("evidenceExcerpt", e.target.value)} /></Field>
          {error && <InlineMessage tone="error">{error}</InlineMessage>}
          <div className="flex gap-2 justify-end"><Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button><Button type="button" size="sm" disabled={submitting} onClick={() => void submit()}>{submitting ? "Saving…" : "Save encounter"}</Button></div>
        </div>
      )}
    </div>
  );
}

function EncounterDetail({ enc, onClose }: { enc: ClinicalEncounter; onClose: () => void }) {
  return (
    <div className="mt-3 rounded-xl border border-care-200 bg-care-50/30 p-3 text-[0.7rem] text-slate-700 space-y-1.5">
      <div className="flex items-center justify-between"><p className="font-semibold text-navy-950">Encounter detail</p><button onClick={onClose} className="text-slate-500 hover:text-slate-600"><X className="h-3.5 w-3.5" /></button></div>
      <p><span className="font-semibold">Provider:</span> {enc.providerName || "—"} {enc.providerSpecialty ? `· ${enc.providerSpecialty}` : ""}</p>
      <p><span className="font-semibold">Facility:</span> {enc.facility || "—"}</p>
      <p><span className="font-semibold">Date:</span> {formatDateTime(enc.occurredAt)}{enc.endedAt ? ` – ${formatDateTime(enc.endedAt)}` : ""}</p>
      <p><span className="font-semibold">Reason:</span> {enc.reason || "—"}</p>
      <p><span className="font-semibold">Summary:</span> {enc.summary}</p>
      {enc.dischargeInstructions && <p><span className="font-semibold">Discharge instructions:</span> {enc.dischargeInstructions}</p>}
      {enc.followUpPlan && <p><span className="font-semibold">Follow-up plan:</span> {enc.followUpPlan}</p>}
      {enc.sourceDocument && <p><span className="font-semibold">Source document:</span> {enc.sourceDocument}</p>}
      <div className="flex flex-wrap gap-1.5 items-center"><VerificationBadge status={enc.verificationStatus as any} /><SourceChip evidence={enc.evidence} /></div>
      {enc.provenance && <p className="text-[0.62rem] text-slate-500">Provenance: {enc.provenance.actorName} ({enc.provenance.actorRole}) · {enc.provenance.sourceType} · {enc.provenance.verificationStatus}</p>}
    </div>
  );
}

export function ClinicalRecordsView({ mode = "all" }: { mode?: "all" | "labs" | "history" }) {
  const { patientId, selectedUser } = useSession();
  const isClinician = selectedUser?.role === "clinician";
  const labsState = useApi<LabResult[]>(patientId ? `/patients/${patientId}/labs` : null);
  const encountersState = useApi<ClinicalEncounter[]>(patientId ? `/patients/${patientId}/encounters` : null);
  const [openEncounterId, setOpenEncounterId] = useState<string | null>(null);
  const [comparison, setComparison] = useState<ReportComparison | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState<unknown>(null);

  const loadComparison = useCallback(async () => {
    if (!patientId || !selectedUser) return;
    setComparisonLoading(true);
    setComparisonError(null);
    try {
      setComparison(await fetchReportComparison(patientId, selectedUser.id));
    } catch (err) {
      setComparisonError(err);
    } finally {
      setComparisonLoading(false);
    }
  }, [patientId, selectedUser]);

  useEffect(() => {
    void loadComparison();
  }, [loadComparison]);

  const refreshAll = () => { labsState.refresh(); encountersState.refresh(); void loadComparison(); };
  const loading = (labsState.loading && !labsState.data) || (encountersState.loading && !encountersState.data);
  const error = labsState.error || encountersState.error;
  const labs = labsState.data ?? [];
  const encounters = useMemo(
    () => [...(encountersState.data ?? [])].sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime()),
    [encountersState.data],
  );

  if (loading) return <PageSkeleton />;
  if (error instanceof ApiClientError && error.status === 403) {
    return <AccessRestricted title="Clinical records are not shared with this role" description="Lab results and clinical encounters are available only to authorized roles with the required consent scope." />;
  }
  if (error) return <ErrorState error={error} onRetry={refreshAll} />;

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={mode === "labs" ? "Lab reports" : mode === "history" ? "Medical history" : "Clinical records"}
        title={
          mode === "labs"
            ? "Lab results and trends."
            : mode === "history"
              ? "Clinical encounters and history."
              : "Lab results and encounter history."
        }
        description="Exact supplied values, units, source/reference ranges, clinician/date/source attribution and verification are preserved. Missing units or ranges are not inferred. Records are connected to the timeline and Digital Twin with provenance."
        actions={<div className="flex items-center gap-2"><Badge tone="amber">Synthetic demo data</Badge><Button size="sm" variant="ghost" onClick={refreshAll}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button></div>}
      />

      {mode !== "history" && (
      <SectionCard
        className="mb-4"
        title="Report comparison"
        description="Only the same test with the same unit from two different documents is compared. Changes are arithmetic, never a diagnosis."
        icon={<RefreshCw className="h-4 w-4" />}
        action={
          <Badge tone="slate">
            {comparison ? `${comparison.comparisons.length} comparisons` : "loading"}
          </Badge>
        }
      >
        {comparisonLoading && !comparison ? (
          <p className="py-3 text-[0.68rem] text-slate-500">Comparing compatible reports…</p>
        ) : comparisonError ? (
          <ErrorState error={comparisonError} onRetry={() => void loadComparison()} compact />
        ) : !comparison || comparison.comparisons.length === 0 ? (
          <EmptyState
            title="No compatible pair of readings yet"
            description="Upload two reports that both state the same test in the same unit to see a change over time."
          />
        ) : (
          <div className="space-y-2">
            {comparison.comparisons
              .filter((row) => row.difference !== 0 || row.comparable)
              .map((row, index) => (
              <div
                key={`${row.canonicalTest}-${row.previous.documentId}-${row.latest.documentId}-${index}`}
                className="rounded-xl border border-slate-100 bg-mist-50 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[0.72rem] font-semibold text-navy-900">{row.label}</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone={row.comparable ? "teal" : "amber"}>
                      {row.comparable ? "comparable" : "not comparable"}
                    </Badge>
                    <Badge tone={row.verification.bothVerified ? "teal" : "amber"}>
                      {row.verification.bothVerified ? "verified" : "unverified values"}
                    </Badge>
                  </div>
                </div>
                <div className="mt-2 grid gap-2 text-[0.64rem] sm:grid-cols-2">
                  {[
                    ["Previous", row.previous],
                    ["Latest", row.latest],
                  ].map(([label, side]) => {
                    const typed = side as typeof row.previous;
                    return (
                      <div key={label as string} className="rounded-lg bg-mist-100 p-2">
                        <p className="text-[0.52rem] uppercase tracking-[0.12em] text-slate-500">
                          {label as string}
                        </p>
                        <p className="mt-0.5 font-mono text-[0.72rem] text-navy-900">
                          {typed.value} {row.unit}
                        </p>
                        <p className="text-[0.58rem] text-slate-500">
                          {typed.date} · {typed.documentName} · page {typed.pageNumber ?? "?"}
                        </p>
                        {typed.referenceRange && (
                          <p className="text-[0.56rem] text-slate-500">
                            printed range {typed.referenceRange}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="mt-2 text-[0.64rem] text-slate-600">
                  Difference: <span className="font-mono">{row.difference > 0 ? "+" : ""}{row.difference}</span>{" "}
                  {row.unit} ({row.direction})
                  {row.differencePercent !== null ? ` · ${row.differencePercent}%` : ""}
                </p>
                {row.validityReasons.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {row.validityReasons.map((reason) => (
                      <li key={reason} className="text-[0.6rem] text-amber-700">· {reason}</li>
                    ))}
                  </ul>
                )}
                {row.explanation && (
                  <p className="mt-1 text-[0.6rem] leading-relaxed text-slate-500">
                    {row.explanation}
                  </p>
                )}
              </div>
            ))}
            {comparison.unitMismatches.length > 0 && (
              <p className="text-[0.6rem] text-amber-700">
                Not compared because reports use different units:{" "}
                {comparison.unitMismatches.map((item) => `${item.label} (${item.units.join(" / ")})`).join("; ")}
              </p>
            )}
            {comparison.insufficientHistory.length > 0 && (
              <p className="text-[0.6rem] text-slate-500">
                Single reading only: {comparison.insufficientHistory.map((item) => item.label).join(", ")}
              </p>
            )}
          </div>
        )}
      </SectionCard>
      )}

      <div className={mode === "all" ? "grid gap-4 xl:grid-cols-2" : "grid gap-4"}>
        {mode !== "history" && (
        <SectionCard title="Lab results" description="Documented and clinician-recorded results with provenance and verification." icon={<FlaskConical className="h-4 w-4" />} action={<Badge tone="slate">{labs.length} results</Badge>}>
          {isClinician && <div className="mb-3"><LabCreateForm onCreated={refreshAll} /></div>}
          {!isClinician && <p className="mb-3 text-[0.66rem] text-slate-500">Lab result entry is restricted to clinician roles. You can view shared records with provenance.</p>}
          {labs.length === 0 ? (
            <EmptyState icon={<FlaskConical className="h-4 w-4" />} title="No lab results recorded" description="Lab results will appear here with exact supplied values, units, reference ranges and evidence links." />
          ) : (
            <div className="space-y-3">
              {labs.map((lab) => (
                <div key={lab.id} className="rounded-xl border border-slate-200/80 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-navy-950">{lab.testName}</p>
                      <p className="text-[0.68rem] text-slate-500">{lab.testCode}{lab.panel ? ` · ${lab.panel}` : ""}{lab.specimen ? ` · ${lab.specimen}` : ""}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone={["above_range","below_range","abnormal"].includes(lab.comparisonStatus || "") ? "amber" : "teal"}>{(lab.comparisonStatus || "unavailable").replaceAll("_", " ")}</Badge>
                      <VerificationBadge status={lab.verificationStatus as any} />
                    </div>
                  </div>
                  <div className="mt-2 grid gap-2 text-[0.72rem] text-slate-700 sm:grid-cols-2">
                    <p><span className="font-semibold text-navy-900">Value:</span> {valueDisplay(lab)}</p>
                    <p><span className="font-semibold text-navy-900">Reference range:</span> {rangeDisplay(lab)}</p>
                    <p><span className="font-semibold text-navy-900">Collected:</span> {formatDateTime(lab.collectedAt)}</p>
                    <p><span className="font-semibold text-navy-900">Resulted:</span> {lab.resultedAt ? formatDateTime(lab.resultedAt) : "—"}</p>
                  </div>
                  {(lab.comparisonNote || lab.ambiguityNote) && <p className="mt-2 text-[0.68rem] leading-relaxed text-slate-500">{[lab.comparisonNote, lab.ambiguityNote].filter(Boolean).join(" ")}</p>}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <SourceChip evidence={lab.evidence} />
                    {lab.provenance?.actorName && <span className="text-[0.62rem] text-slate-500">Recorded by {lab.provenance.actorName} · {lab.provenance.actorRole}</span>}
                  </div>
                  <p className="mt-1 text-[0.6rem] text-slate-500">Units and reference ranges are shown exactly as supplied; none inferred.</p>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
        )}

        {mode !== "labs" && (
        <SectionCard title="Clinical encounters" description="Encounter history in chronological order with clinician, date, source and verification." icon={<Stethoscope className="h-4 w-4" />} action={<Badge tone="slate">{encounters.length} encounters</Badge>}>
          {isClinician && <div className="mb-3"><EncounterCreateForm onCreated={refreshAll} /></div>}
          {!isClinician && <p className="mb-3 text-[0.66rem] text-slate-500">Encounter entry is restricted to clinician roles. You can view shared encounter history and details.</p>}
          {encounters.length === 0 ? (
            <EmptyState icon={<Stethoscope className="h-4 w-4" />} title="No clinical encounters recorded" description="Clinical encounters and summaries will appear here with preserved provenance." />
          ) : (
            <div className="space-y-3">
              {encounters.map((enc) => (
                <div key={enc.id} className="rounded-xl border border-slate-200/80 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-navy-950">{enc.encounterType}</p>
                      <p className="text-[0.68rem] text-slate-500">{enc.providerName || "Clinical team"}{enc.providerSpecialty ? ` · ${enc.providerSpecialty}` : ""}{enc.facility ? ` · ${enc.facility}` : ""}</p>
                    </div>
                    <div className="flex items-center gap-1.5"><VerificationBadge status={enc.verificationStatus as any} /></div>
                  </div>
                  <p className="mt-1 text-[0.68rem] text-slate-500">{formatDateTime(enc.occurredAt)}{enc.endedAt ? ` – ${formatDateTime(enc.endedAt)}` : ""}</p>
                  {enc.reason && <p className="mt-2 text-[0.72rem] text-slate-700"><span className="font-semibold text-navy-900">Reason:</span> {enc.reason}</p>}
                  <p className="mt-1.5 text-[0.72rem] leading-relaxed text-slate-600">{enc.summary}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <SourceChip evidence={enc.evidence} />
                    {enc.sourceDocument && <span className="text-[0.62rem] text-slate-500">Source: {enc.sourceDocument}</span>}
                    <button type="button" className="text-[0.66rem] font-semibold text-care-700 hover:text-care-800" onClick={() => setOpenEncounterId(openEncounterId === enc.id ? null : enc.id)}>{openEncounterId === enc.id ? "Hide details" : "View details"}</button>
                  </div>
                  {openEncounterId === enc.id && <EncounterDetail enc={enc} onClose={() => setOpenEncounterId(null)} />}
                </div>
              ))}
            </div>
          )}
        </SectionCard>
        )}
      </div>
    </div>
  );
}
