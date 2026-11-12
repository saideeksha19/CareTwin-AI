"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FlaskConical,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import type { CheckinResult, CheckinSymptomInput } from "@caretwin/contracts";
import { cn } from "@caretwin/shared";
import { apiRequest, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import { AlertCard } from "@/components/workspace/alert-card";
import { SafetyDecisionCard } from "@/components/workspace/records";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badges";
import { Field, Input, RangeField, Textarea } from "@/components/ui/fields";
import { InlineMessage } from "@/components/ui/feedback";

type Feeling = "better" | "same" | "worse";
type Adherence = "all" | "missed_one" | "missed_multiple";

const symptomOptions = [
  { code: "cough", label: "Cough" },
  { code: "fever", label: "Fever" },
  { code: "chest_pain", label: "Chest pain" },
  { code: "breathlessness", label: "Breathlessness" },
  { code: "fatigue", label: "Fatigue" },
  { code: "headache", label: "Headache" },
  { code: "nausea", label: "Nausea" },
  { code: "dizziness", label: "Dizziness" },
];

const feelingOptions: Array<{ value: Feeling; label: string; hint: string }> = [
  { value: "better", label: "Better", hint: "Improving" },
  { value: "same", label: "About the same", hint: "Stable" },
  { value: "worse", label: "Worse", hint: "Declining" },
];

const adherenceOptions: Array<{ value: Adherence; label: string; missed: number }> = [
  { value: "all", label: "All doses taken", missed: 0 },
  { value: "missed_one", label: "Missed one dose", missed: 1 },
  { value: "missed_multiple", label: "Missed multiple", missed: 2 },
];

export function CheckinForm({ onSubmitted }: { onSubmitted?: () => void }) {
  const { patientId, selectedUser } = useSession();
  const [feeling, setFeeling] = useState<Feeling>("same");
  const [pain, setPain] = useState(3);
  const [temperature, setTemperature] = useState("");
  const [breathlessness, setBreathlessness] = useState(3);
  const [adherence, setAdherence] = useState<Adherence>("all");
  const [missedDoses, setMissedDoses] = useState(0);
  const [selected, setSelected] = useState<Record<string, number>>({
    cough: 4,
    fatigue: 5,
  });
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CheckinResult | null>(null);

  const symptomPayload = useMemo<CheckinSymptomInput[]>(
    () =>
      Object.entries(selected).map(([code, severity]) => ({
        code,
        label: symptomOptions.find((option) => option.code === code)?.label ?? code,
        severity,
      })),
    [selected],
  );

  function changeAdherence(next: Adherence) {
    setAdherence(next);
    const option = adherenceOptions.find((item) => item.value === next);
    setMissedDoses(next === "missed_multiple" ? 2 : (option?.missed ?? 0));
  }

  function resetForm() {
    setFeeling("same");
    setPain(3);
    setTemperature("");
    setBreathlessness(3);
    setAdherence("all");
    setMissedDoses(0);
    setSelected({ cough: 4, fatigue: 5 });
    setNotes("");
    setError(null);
    setResult(null);
  }

  function prefillWorsening() {
    setFeeling("worse");
    setPain(6);
    setTemperature("38.8");
    setBreathlessness(8);
    setAdherence("missed_multiple");
    setMissedDoses(2);
    setSelected({ cough: 6, fever: 7, chest_pain: 8, fatigue: 7 });
    setNotes(
      "Fever overnight, chest pain when breathing deeply, and more breathless walking to the kitchen. Missed two antibiotic doses.",
    );
    setError(null);
    setResult(null);
  }

  function prefillStable() {
    setFeeling("better");
    setPain(2);
    setTemperature("37.1");
    setBreathlessness(2);
    setAdherence("all");
    setMissedDoses(0);
    setSelected({ cough: 3, fatigue: 3 });
    setNotes(
      "Breathing feels easier today. Completed all antibiotic doses and walked twice.",
    );
    setError(null);
    setResult(null);
  }

  async function submitCheckin() {
    if (!patientId || !selectedUser) return;
    setError(null);

    let temperatureC: number | null = null;
    if (temperature.trim() !== "") {
      temperatureC = Number(temperature);
      if (!Number.isFinite(temperatureC) || temperatureC < 30 || temperatureC > 45) {
        setError("Temperature must be between 30 and 45 °C, or left blank.");
        return;
      }
    }
    if (adherence === "missed_multiple" && missedDoses < 2) {
      setError("Missed multiple doses requires at least 2 missed doses.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await apiRequest<CheckinResult>(
        `/patients/${patientId}/checkins`,
        {
          method: "POST",
          userId: selectedUser.id,
          body: {
            overallFeeling: feeling,
            painScore: pain,
            temperatureC,
            breathlessnessScore: breathlessness,
            adherence,
            missedDoses,
            symptoms: symptomPayload,
            notes: notes.trim(),
          },
        },
      );
      setResult(response);
      onSubmitted?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3">
        <FlaskConical className="h-4 w-4 text-care-600" />
        <p className="text-xs font-semibold text-navy-950">Demo scenario shortcuts</p>
        <p className="text-[0.66rem] text-slate-500">
          These only prefill the synthetic form. Nothing is submitted until you press the
          button.
        </p>
        <div className="ml-auto flex gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={prefillStable}>
            Stable day
          </Button>
          <Button type="button" size="sm" variant="danger" onClick={prefillWorsening}>
            Worsening day
          </Button>
        </div>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submitCheckin();
        }}
        className="space-y-4"
      >
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-xs font-semibold text-navy-950">1 · How does today feel?</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {feelingOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setFeeling(option.value)}
                aria-pressed={feeling === option.value}
                className={cn(
                  "rounded-xl border px-3 py-2.5 text-left transition-colors",
                  feeling === option.value
                    ? "border-care-500 bg-care-50 ring-1 ring-care-500/30"
                    : "border-slate-200 hover:border-slate-300",
                )}
              >
                <span className="block text-xs font-semibold text-navy-950">
                  {option.label}
                </span>
                <span className="mt-0.5 block text-[0.64rem] text-slate-500">
                  {option.hint}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-5 rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold text-navy-950">2 · Symptoms & vitals</p>
            <RangeField
              label="Pain score"
              value={pain}
              onChange={setPain}
              leftLabel="No pain"
              rightLabel="Severe"
            />
            <RangeField
              label="Breathlessness"
              value={breathlessness}
              onChange={setBreathlessness}
              leftLabel="Breathing easy"
              rightLabel="At rest"
            />
            <Field
              label="Temperature (°C)"
              htmlFor="temperature"
              hint="Leave blank if not measured."
            >
              <Input
                id="temperature"
                inputMode="decimal"
                value={temperature}
                onChange={(event) => setTemperature(event.target.value)}
                placeholder="e.g. 37.2"
              />
            </Field>
          </div>

          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-semibold text-navy-950">3 · Medication adherence</p>
            <div className="space-y-2">
              {adherenceOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => changeAdherence(option.value)}
                  aria-pressed={adherence === option.value}
                  className={cn(
                    "flex w-full items-center justify-between rounded-lg border px-3 py-2 text-xs transition-colors",
                    adherence === option.value
                      ? "border-care-500 bg-care-50 font-semibold text-care-900"
                      : "border-slate-200 text-slate-600 hover:border-slate-300",
                  )}
                >
                  {option.label}
                  <span className="font-mono text-[0.62rem] text-slate-400">
                    {option.missed} missed
                  </span>
                </button>
              ))}
            </div>
            <Field
              label="Missed doses"
              htmlFor="missed-doses"
              hint="Count only doses that were not taken."
            >
              <Input
                id="missed-doses"
                type="number"
                min={0}
                max={20}
                value={missedDoses}
                onChange={(event) => setMissedDoses(Number(event.target.value))}
                disabled={adherence === "all"}
              />
            </Field>
            <InlineMessage tone="info">
              Adherence is self-reported and stays attributed to you. It is not treated as a
              verified medication administration record.
            </InlineMessage>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-xs font-semibold text-navy-950">
            4 · Select any symptoms you are experiencing
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {symptomOptions.map((symptom) => {
              const active = symptom.code in selected;
              return (
                <div
                  key={symptom.code}
                  className={cn(
                    "rounded-xl border p-2.5",
                    active ? "border-care-300 bg-care-50/50" : "border-slate-200",
                  )}
                >
                  <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-navy-900">
                    <input
                      type="checkbox"
                      checked={active}
                      onChange={(event) => {
                        setSelected((current) => {
                          const next = { ...current };
                          if (event.target.checked) next[symptom.code] = 3;
                          else delete next[symptom.code];
                          return next;
                        });
                      }}
                      className="h-3.5 w-3.5 accent-care-600"
                    />
                    {symptom.label}
                  </label>
                  {active && (
                    <>
                      <input
                        type="range"
                        min={0}
                        max={10}
                        value={selected[symptom.code] ?? 3}
                        onChange={(event) =>
                          setSelected((current) => ({
                            ...current,
                            [symptom.code]: Number(event.target.value),
                          }))
                        }
                        className="mt-2 w-full"
                        aria-label={`${symptom.label} severity`}
                      />
                      <p className="mt-0.5 text-right font-mono text-[0.6rem] text-slate-500">
                        {selected[symptom.code] ?? 3}/10
                      </p>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <Field
            label="5 · Anything else you want your care team to know?"
            htmlFor="checkin-notes"
            hint="Optional. Up to 2,000 characters."
          >
            <Textarea
              id="checkin-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              maxLength={2000}
              placeholder="Sleep, appetite, mobility, worries, or context for the numbers above"
            />
          </Field>
        </div>

        {error && (
          <InlineMessage tone="error" title="Check-in was not accepted">
            {error}
          </InlineMessage>
        )}

        <div className="sticky bottom-3 z-10 flex flex-col gap-2 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-1.5 text-[0.66rem] leading-relaxed text-slate-500">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-care-600" />
            Submitting creates evidence, a timeline event, rule alerts and a twin snapshot.
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={resetForm}>
              <RotateCcw className="h-3.5 w-3.5" /> Reset
            </Button>
            <Button type="submit" disabled={submitting}>
              <ClipboardCheck className="h-4 w-4" />
              {submitting ? "Submitting…" : "Submit daily check-in"}
            </Button>
          </div>
        </div>
      </form>

      {result && (
        <div className="space-y-3 rounded-2xl border border-care-200 bg-care-50/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-semibold text-care-900">
              <CheckCircle2 className="h-4 w-4" /> Check-in recorded
            </p>
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="teal">Twin v{result.twinVersion}</Badge>
              <Badge tone={result.alerts.length > 0 ? "amber" : "teal"}>
                {result.alerts.length} new rule alert
                {result.alerts.length === 1 ? "" : "s"}
              </Badge>
              {result.deduplicatedAlerts.length > 0 && (
                <Badge tone="blue">
                  {result.deduplicatedAlerts.length} existing alert
                  {result.deduplicatedAlerts.length === 1 ? "" : "s"} retained
                </Badge>
              )}
            </div>
          </div>
          <p className="text-xs leading-relaxed text-slate-600">
            Your report is stored as patient-reported information. It is not a diagnosis. If
            symptoms feel severe or are worsening quickly, contact emergency services or your
            care team now.
          </p>
          <SafetyDecisionCard decision={result.safetyDecision} compact />
          {result.deduplicatedAlerts.length > 0 && (
            <div className="rounded-xl border border-sky-200 bg-sky-50 px-3.5 py-3 text-xs text-sky-900">
              <p className="font-semibold">
                Existing unresolved alert retained instead of creating a duplicate
              </p>
              <p className="mt-0.5 text-sky-800">
                {result.deduplicatedAlerts
                  .map((alert) => alert.title)
                  .join(", ")}
                . The original alert and its provenance remain in Safety alerts
                until a clinician resolves it.
              </p>
            </div>
          )}
          {result.alerts.length > 0 && (
            <div className="space-y-2">
              <p className="flex items-center gap-1.5 text-[0.68rem] font-semibold text-amber-800">
                <AlertTriangle className="h-3.5 w-3.5" /> Alerts raised by deterministic rules
              </p>
              {result.alerts.map((alert) => (
                <AlertCard key={alert.id} alert={alert} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
