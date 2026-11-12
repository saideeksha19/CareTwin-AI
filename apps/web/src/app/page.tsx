import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  Fingerprint,
  GitCommitVertical,
  KeyRound,
  Layers,
  LockKeyhole,
  Orbit,
  ShieldCheck,
  Stethoscope,
  Users,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { LinkButton } from "@/components/ui/button";
import { Badge, RoleBadge, SourceChip, VerificationBadge } from "@/components/ui/badges";
import { TwinVideo } from "@/components/twin/twin-video";


const principles = [
  {
    icon: Fingerprint,
    title: "Evidence before inference",
    body: "Every milestone, instruction and alert points back to a source page, patient report or clinician note. Provenance is part of the data model, not a tooltip.",
  },
  {
    icon: ShieldCheck,
    title: "Deterministic safety first",
    body: "Monitoring runs on clinician-configured thresholds. The AI boundary may explain evidence, but it cannot create alerts, decisions or verified facts.",
  },
  {
    icon: LockKeyhole,
    title: "Consent at the API boundary",
    body: "Role scopes are enforced server-side. A revoked caregiver receives a clean access boundary, not a UI that merely hides data.",
  },
];

const capabilities = [
  {
    icon: Orbit,
    title: "Patient Recovery Digital Twin",
    body: "A versioned, current-state projection of recovery: plan, milestones, medications, check-ins, observations, alerts and linked evidence.",
    tag: "Working",
  },
  {
    icon: FileSearch,
    title: "Provenance-linked evidence graph",
    body: "Discharge pages, check-in submissions and caregiver observations remain attributable, reviewable and visibly synthetic where applicable.",
    tag: "Working",
  },
  {
    icon: Activity,
    title: "Rule-based monitoring",
    body: "Six seeded deterministic rules evaluate check-ins for fever, breathlessness, chest pain, adherence gaps, pain escalation and check-in gaps.",
    tag: "Working",
  },
  {
    icon: Layers,
    title: "Immutable recovery timeline",
    body: "Every meaningful action produces a timestamped event with actor, role, source type, verification status and payload.",
    tag: "Working",
  },
  {
    icon: GitCommitVertical,
    title: "Twin snapshots & audit",
    body: "State is versioned as recovery changes. Safety decisions and audit entries record what was allowed, why, and by whom.",
    tag: "Working",
  },
  {
    icon: BrainCircuit,
    title: "Provider-independent AI boundary",
    body: "A server-side explanation interface with strict grounding and output validation. Ships unconfigured, and reports that honestly.",
    tag: "Prepared",
  },
];

const roles = [
  {
    role: "patient" as const,
    name: "Maya Rao",
    detail: "Owns the record. Checks in daily, tracks medications, controls sharing.",
    note: "Full recovery workspace",
  },
  {
    role: "caregiver" as const,
    name: "Arjun Rao",
    detail: "Granted a defined slice of the twin, schedule, alerts and observation workflow.",
    note: "Consent-scoped sharing",
  },
  {
    role: "clinician" as const,
    name: "Dr. Nandini Iyer",
    detail: "Reviews alerts, confirms ambiguous instructions, runs monitoring and reports.",
    note: "Clinical review workflow",
  },
];

function HeroPreview() {
  return (
    <div className="relative">
      <div className="absolute -inset-6 rounded-[2rem] bg-care-400/10 blur-2xl" aria-hidden="true" />
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_30px_80px_-40px_rgba(15,23,42,0.35)]">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
          <span className="flex items-center gap-2 text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-care-700">
            <span className="h-1.5 w-1.5 rounded-full bg-care-500 shadow-[0_0_8px_rgba(37,99,235,0.55)]" />
            Illustrative twin animation
          </span>
          <span className="text-[0.58rem] text-slate-500">Continuous rotation · synthetic demo</span>
        </div>
        <div className="relative h-[24rem] bg-gradient-to-br from-[#0b1b33] via-[#0a1626] to-[#06101f]">
          <TwinVideo />
        </div>
        <div className="grid grid-cols-3 gap-2 border-t border-slate-100 bg-white px-3 py-2.5">
          {[
            ["Day", "4 post-discharge"],
            ["Open alerts", "2 rule alerts"],
            ["Twin version", "v5 · 12 events"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-100 bg-mist-50 px-2 py-1.5">
              <p className="text-[0.5rem] uppercase tracking-[0.12em] text-slate-500">{label}</p>
              <p className="mt-0.5 truncate text-[0.66rem] font-semibold text-navy-900">{value}</p>
            </div>
          ))}
        </div>
        <p className="border-t border-slate-100 px-4 py-2 text-[0.52rem] uppercase tracking-[0.14em] text-slate-500">
          Illustrative anatomy · synthetic demo data
        </p>
      </div>
      <div className="absolute -bottom-4 -left-4 hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-lg sm:flex">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-care-50 text-care-700">
          <ShieldCheck className="h-3.5 w-3.5" />
        </span>
        <span className="text-[0.66rem] font-semibold text-navy-900">
          Deterministic rule · not AI judgment
        </span>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="ct-landing min-h-screen bg-mist-50">
      <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-mist-50/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 md:px-6">
          <Brand />
          <nav className="hidden items-center gap-6 text-xs font-semibold text-slate-600 md:flex">
            <a href="#capabilities" className="hover:text-navy-900">
              Capabilities
            </a>
            <a href="#evidence" className="hover:text-navy-900">
              Evidence model
            </a>
            <a href="#safety" className="hover:text-navy-900">
              Safety
            </a>
            <a href="#roles" className="hover:text-navy-900">
              Roles
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <span className="hidden text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-slate-400 lg:inline">
              Phase 1 demo
            </span>
            <LinkButton href="/demo" size="sm">
              Enter demo <ArrowRight className="h-3.5 w-3.5" />
            </LinkButton>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden border-b border-slate-200/70 bg-gradient-to-b from-white via-care-50/40 to-mist-50">
        <div className="grid-lines absolute inset-0 opacity-30" aria-hidden="true" />
        <div
          className="absolute -left-40 top-10 h-96 w-96 rounded-full bg-care-300/25 blur-[120px]"
          aria-hidden="true"
        />
        <div
          className="absolute -right-32 bottom-0 h-96 w-96 rounded-full bg-sky-200/40 blur-[130px]"
          aria-hidden="true"
        />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-4 pb-20 pt-16 md:px-6 md:pb-24 md:pt-20 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div className="animate-fade-up">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-care-200 bg-care-50 px-3 py-1 text-[0.66rem] font-semibold uppercase tracking-[0.14em] text-care-700">
                <span className="h-1.5 w-1.5 rounded-full bg-care-500 animate-pulse-soft" />
                Recovery Digital Twin
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-[0.66rem] font-medium text-slate-500">
                Synthetic patient · no login
              </span>
            </div>
            <h1 className="mt-6 max-w-xl font-display text-4xl font-semibold leading-[1.06] tracking-tight text-balance md:text-[3.4rem]">
              Your health. Your digital twin.{" "}
              <span className="bg-gradient-to-r from-care-600 to-care-400 bg-clip-text text-transparent">
                Always with you.
              </span>
            </h1>
            <p className="mt-5 max-w-lg text-[0.95rem] leading-relaxed text-slate-600">
              CareTwin AI turns a fragmented discharge packet into a living recovery
              twin — versioned, consent-scoped, provenance-linked and monitored by
              deterministic rules. Built for the uncertain days after hospital.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <LinkButton href="/demo" size="lg">
                Open the recovery demo <ArrowRight className="h-4 w-4" />
              </LinkButton>
              <a
                href="#capabilities"
                className="inline-flex h-12 items-center gap-2 rounded-xl border border-slate-300 bg-white px-5 text-sm font-semibold text-navy-800 transition-colors hover:border-care-300 hover:text-care-700"
              >
                Explore the system
              </a>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-[0.68rem] text-slate-500">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-care-600" /> Working check-in workflow
              </span>
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-care-600" /> Server-enforced consent
              </span>
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-care-600" /> Honest AI state
              </span>
            </div>
          </div>
          <div className="animate-fade-up [animation-delay:120ms]">
            <HeroPreview />
          </div>
        </div>
      </section>

      <section className="border-b border-slate-200/70 bg-white">
        <div className="mx-auto grid max-w-6xl divide-y divide-slate-100 px-4 py-8 sm:grid-cols-2 sm:divide-x sm:divide-y-0 md:px-6 lg:grid-cols-4">
          {[
            ["1 patient record", "3 role-aware demo users"],
            ["12 seeded events", "Twin version 5 at seed"],
            ["6 monitoring rules", "2 open alerts from check-in"],
            ["1 evidence graph", "Every fact keeps its source"],
          ].map(([primary, secondary]) => (
            <div key={primary} className="px-2 py-4 sm:px-6">
              <p className="font-display text-lg font-semibold tracking-tight text-navy-950">
                {primary}
              </p>
              <p className="mt-0.5 text-[0.7rem] text-slate-500">{secondary}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="capabilities" className="mx-auto max-w-6xl px-4 py-20 md:px-6">
        <div className="max-w-2xl">
          <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-care-700">
            Phase 1 · What actually works
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-navy-950 md:text-4xl">
            A system of record for recovery — not a chat window.
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-600">
            Each capability below is implemented in the running demo. Prepared
            interfaces are labeled as prepared; nothing is presented as more mature
            than it is.
          </p>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.title}
                className="group relative flex flex-col rounded-2xl border border-slate-200/80 bg-white p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-care-200 hover:shadow-[0_18px_40px_-30px_rgba(4,19,32,0.35)]"
              >
                <div className="flex items-start justify-between">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-care-50 text-care-700 ring-1 ring-care-100">
                    <Icon className="h-4.5 w-4.5" />
                  </span>
                  <Badge tone={item.tag === "Working" ? "teal" : "blue"}>{item.tag}</Badge>
                </div>
                <h3 className="mt-4 text-sm font-semibold text-navy-950">{item.title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{item.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section id="evidence" className="border-y border-slate-200/70 bg-white">
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 md:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-care-700">
              The provenance model
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-navy-950 md:text-4xl">
              Every claim has an author, a source and a review state.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              Discharge instructions arrive as documents. Check-ins arrive as patient
              reports. Caregiver notes are observations, not facts. CareTwin keeps those
              distinctions visible instead of flattening them into confident prose.
            </p>
            <div className="mt-6 space-y-2.5">
              {[
                "Source page references survive into the UI",
                "Unreviewed instructions stay labeled awaiting_review",
                "AI-generated extraction never becomes verified by assertion",
                "Synthetic demo data is marked everywhere it appears",
              ].map((line) => (
                <p key={line} className="flex items-start gap-2 text-xs text-slate-700">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-care-600" />
                  {line}
                </p>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-mist-50/70 p-5">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
              <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                <FileSearch className="h-4 w-4 text-care-700" /> Discharge summary · Page 3
              </p>
              <VerificationBadge status="awaiting_review" />
            </div>
            <blockquote className="mt-4 border-l-2 border-care-300 pl-3 text-sm leading-relaxed text-slate-700">
              &ldquo;Salbutamol 100 mcg inhaler, 2 puffs as needed for breathlessness.
              Spacer use was noted but delivery technique was not specified. Seek urgent
              review for worsening breathlessness, chest pain, or persistent fever.&rdquo;
            </blockquote>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <SourceChip
                evidence={{
                  id: "src_discharge_p3",
                  sourceType: "discharge_document",
                  title: "Inhaler and return precautions",
                  documentName: "discharge_summary_maya_rao.pdf",
                  pageRef: "Page 3",
                  excerpt: "",
                  synthetic: true,
                  verificationStatus: "awaiting_review",
                  extractedByAi: true,
                  capturedAt: "",
                }}
              />
              <Badge tone="amber">Ambiguity flagged</Badge>
            </div>
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3">
              <p className="text-[0.65rem] font-bold uppercase tracking-[0.12em] text-amber-800">
                Clinician review required
              </p>
              <p className="mt-1 text-xs leading-relaxed text-slate-700">
                The twin surfaces this instruction with a review badge. It does not
                silently assert a spacer technique that the document never states.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="safety" className="mx-auto max-w-6xl px-4 py-20 md:px-6">
        <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr]">
          <div>
            <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-care-700">
              Safety architecture
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-navy-950 md:text-4xl">
              Clinical humility, encoded.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              CareTwin AI is explicitly not a diagnostic or prescribing system. Safety
              lives in deterministic checks, bounded inputs, consent enforcement and
              visible uncertainty — not in a reassuring tone.
            </p>
            <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
              <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                <Stethoscope className="h-4 w-4 text-care-700" /> Example boundary
              </p>
              <p className="mt-2 text-xs leading-relaxed text-slate-600">
                A patient reports chest pain at 8/10. The deterministic rule raises a
                critical alert and the check-in is accepted with alerts. The system
                never diagnoses the cause or suggests a treatment.
              </p>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-1">
            {principles.map((principle) => {
              const Icon = principle.icon;
              return (
                <div
                  key={principle.title}
                  className="flex gap-4 rounded-2xl border border-slate-200/80 bg-white p-5"
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-care-50 text-care-700 ring-1 ring-care-100">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <h3 className="text-sm font-semibold text-navy-950">
                      {principle.title}
                    </h3>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">
                      {principle.body}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-12 overflow-hidden rounded-2xl border border-care-500/20 bg-gradient-to-br from-care-600 to-care-700 text-white shadow-[0_24px_60px_-35px_rgba(37,99,235,0.55)]">
          <div className="flex flex-col gap-6 p-6 md:flex-row md:items-center md:justify-between md:p-8">
            <div className="max-w-2xl">
              <p className="flex items-center gap-2 text-[0.62rem] font-semibold uppercase tracking-[0.16em] text-care-100">
                <ClipboardCheck className="h-3.5 w-3.5" /> One check-in, four artifacts
              </p>
              <h3 className="mt-2 font-display text-xl font-semibold tracking-tight md:text-2xl">
                Report → rule evaluation → alert → twin snapshot.
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-care-100">
                A single daily check-in creates linked evidence, a timeline event,
                deterministic safety alerts and a new twin version. The whole chain is
                inspectable in the demo.
              </p>
            </div>
            <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-2">
              {["Evidence", "Event", "Alerts", "Snapshot"].map((step, index) => (
                <div
                  key={step}
                  className="rounded-lg border border-white/20 bg-white/10 px-3 py-2"
                >
                  <p className="font-mono text-[0.6rem] text-care-200">0{index + 1}</p>
                  <p className="text-xs font-semibold text-white">{step}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="roles" className="border-y border-slate-200/70 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-20 md:px-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-care-700">
                Role-aware by design
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-navy-950 md:text-4xl">
                One patient record. Three honest views.
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-slate-600">
                Switch between demo identities to see consent filtering, permission
                boundaries and role-specific workflows operate against the same twin.
              </p>
            </div>
            <LinkButton href="/demo" variant="secondary">
              Compare roles <KeyRound className="h-4 w-4" />
            </LinkButton>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {roles.map((item) => (
              <div
                key={item.role}
                className="rounded-2xl border border-slate-200/80 bg-mist-50/50 p-5"
              >
                <div className="flex items-center justify-between">
                  <RoleBadge role={item.role} />
                  <Users className="h-4 w-4 text-slate-300" />
                </div>
                <p className="mt-4 text-base font-semibold text-navy-950">{item.name}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{item.detail}</p>
                <p className="mt-4 border-t border-slate-200/70 pt-3 text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-care-700">
                  {item.note}
                </p>
              </div>
            ))}
          </div>

        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20 md:px-6">
        <div className="grid gap-8 lg:grid-cols-[1fr_0.8fr] lg:items-center">
          <div>
            <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-care-700">
              Architecture, briefly
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-navy-950 md:text-4xl">
              Next.js interface. FastAPI safety core. SQLite demo state.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600">
              A monorepo with shared TypeScript contracts and domain helpers. The backend
              owns authorization, consent, monitoring, twin projection and the optional
              AI provider boundary. The frontend never becomes the source of truth.
            </p>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {[
                "Shared camelCase contracts",
                "Server-side demo identity",
                "SQLite with versioned twin snapshots",
                "Deterministic clinical summary mode",
              ].map((line) => (
                <p key={line} className="flex items-center gap-2 text-xs text-slate-700">
                  <CheckCircle2 className="h-3.5 w-3.5 text-care-600" /> {line}
                </p>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 font-mono text-[0.7rem] leading-relaxed text-slate-600 shadow-sm">
            <p className="mb-2 flex items-center gap-1.5 font-sans text-[0.6rem] font-bold uppercase tracking-[0.14em] text-slate-400">
              <span className="h-2 w-2 rounded-full bg-rose-400" />
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              request path
            </p>
            <p>
              <span className="text-slate-400">UI</span> → role + consent check →{" "}
              <span className="text-care-700">twin projection</span>
            </p>
            <p className="mt-1.5">
              <span className="text-slate-400">check-in</span> → validate → evaluate rules
              → persistence
            </p>
            <p className="mt-1.5">
              <span className="text-slate-400">AI</span> → grounded context → strict output
              validation → <span className="text-amber-700">503 if unconfigured</span>
            </p>
            <div className="mt-3 rounded-lg bg-mist-50 px-3 py-2 font-sans text-[0.65rem] text-slate-500">
              No AI key is required to run or evaluate the working demo.
            </div>
          </div>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto max-w-6xl px-4 py-16 md:px-6 md:py-20">
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-care-600 to-care-700 px-6 py-12 text-white shadow-[0_30px_70px_-40px_rgba(37,99,235,0.6)] md:px-10 md:py-14">
            <div className="grid-lines absolute inset-0 opacity-20" aria-hidden="true" />
            <div className="relative flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
              <div className="max-w-2xl">
                <p className="flex items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-care-100">
                  <Orbit className="h-4 w-4" /> Synthetic demo · Phase 1
                </p>
                <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight md:text-4xl">
                  Open Maya&apos;s recovery twin.
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-care-100">
                  No account, no API key, no real patient data. Choose a role and inspect
                  the evidence, alerts, consent boundaries and audit trail.
                </p>
              </div>
              <LinkButton
                href="/demo"
                size="lg"
                className="bg-white text-care-700 hover:bg-care-50"
              >
                Enter the demo workspace <ArrowRight className="h-4 w-4" />
              </LinkButton>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200/70 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex items-center gap-3">
            <Brand compact />
            <span className="text-[0.65rem] text-slate-400">Phase 1 · Synthetic only</span>
          </div>
          <p className="max-w-xl text-[0.66rem] leading-relaxed text-slate-500">
            CareTwin AI organizes documented and reported information. It does not
            diagnose, prescribe, or replace clinical judgment. In an emergency, contact
            local emergency services. Demo identities use a header, not production
            authentication.
          </p>
          <Link
            href="/demo"
            className="text-xs font-semibold text-care-700 hover:text-care-800"
          >
            Demo access
          </Link>
        </div>
      </footer>
    </div>
  );
}
