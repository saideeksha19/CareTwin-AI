"use client";

import { useState } from "react";
import { CheckCircle2, Eye, Send } from "lucide-react";
import type { ObservationCategory, ObservationResult } from "@caretwin/contracts";
import { apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { SafetyDecisionCard } from "@/components/workspace/records";
import { Button } from "@/components/ui/button";
import { Badge, VerificationBadge } from "@/components/ui/badges";
import { Field, Select, Textarea } from "@/components/ui/fields";
import { InlineMessage } from "@/components/ui/feedback";

const categories: Array<{ value: ObservationCategory; label: string }> = [
  { value: "general", label: "General wellbeing" },
  { value: "mobility", label: "Mobility & activity" },
  { value: "appetite", label: "Appetite & hydration" },
  { value: "medication_support", label: "Medication support" },
  { value: "symptom", label: "Observed symptom" },
  { value: "appointment", label: "Appointment support" },
];

export function ObservationForm({ onSubmitted }: { onSubmitted?: () => void }) {
  const { patientId, selectedUser } = useSession();
  const [category, setCategory] = useState<ObservationCategory>("general");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ObservationResult | null>(null);

  async function submit() {
    if (!patientId || !selectedUser) return;
    if (note.trim().length < 3) {
      setError("Describe what you observed in at least 3 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const response = await apiRequest<ObservationResult>(
        `/patients/${patientId}/observations`,
        {
          method: "POST",
          userId: selectedUser.id,
          body: { category, note: note.trim() },
        },
      );
      setResult(response);
      setNote("");
      onSubmitted?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="space-y-3">
        <Field label="Observation category" htmlFor="observation-category">
          <Select
            id="observation-category"
            value={category}
            onChange={(event) => setCategory(event.target.value as ObservationCategory)}
          >
            {categories.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="What did you observe?"
          htmlFor="observation-note"
          hint="Attributed to you as caregiver-reported information. Not a clinical verification."
        >
          <Textarea
            id="observation-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={2000}
            placeholder="Example: Maya needed to pause twice on the walk to the kitchen and appeared more breathless than yesterday."
          />
        </Field>
        {error && <InlineMessage tone="error">{error}</InlineMessage>}
        <div className="flex justify-end">
          <Button onClick={() => void submit()} disabled={submitting} size="sm">
            <Send className="h-3.5 w-3.5" />
            {submitting ? "Recording…" : "Record observation"}
          </Button>
        </div>
      </div>

      {result && (
        <div className="space-y-2 rounded-xl border border-care-200 bg-care-50/40 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-care-900">
              <CheckCircle2 className="h-3.5 w-3.5" /> Observation recorded
            </p>
            <div className="flex gap-1.5">
              <VerificationBadge status={result.observation.verificationStatus} />
              <Badge tone="slate">{result.observation.category.replaceAll("_", " ")}</Badge>
            </div>
          </div>
          <p className="flex items-start gap-1.5 text-[0.7rem] leading-relaxed text-slate-600">
            <Eye className="mt-0.5 h-3 w-3 shrink-0" /> {result.observation.note}
          </p>
          <SafetyDecisionCard decision={result.safetyDecision} compact />
        </div>
      )}
    </div>
  );
}
