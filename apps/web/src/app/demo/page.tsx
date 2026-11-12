"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BellRing,
  ClipboardCheck,
  Eye,
  FileSearch,
  FlaskConical,
  ShieldCheck,
  Stethoscope,
  Users,
} from "lucide-react";
import type { DemoUser, UserRole } from "@caretwin/contracts";
import { cn } from "@caretwin/shared";
import { useSession } from "@/lib/session";
import { workspaceHome } from "@/lib/nav";
import { Brand } from "@/components/brand";
import { Button, LinkButton } from "@/components/ui/button";
import { Badge, RoleBadge } from "@/components/ui/badges";
import { ErrorState, InlineMessage, LoadingBlock } from "@/components/ui/feedback";

const roleMeta: Record<
  UserRole,
  {
    icon: typeof ShieldCheck;
    accent: string;
    permissions: string[];
    lookFor: string;
    cta: string;
  }
> = {
  patient: {
    icon: ShieldCheck,
    accent: "from-care-600 to-care-400",
    permissions: ["Full twin", "Check-in", "Medications", "Alerts", "Consent control"],
    lookFor:
      "Submit a check-in and watch the evidence, timeline event, deterministic alerts and new twin version appear together.",
    cta: "Enter patient workspace",
  },
  caregiver: {
    icon: Users,
    accent: "from-violet-600 to-violet-400",
    permissions: ["Shared twin", "Shared schedule", "Shared alerts", "Observations"],
    lookFor:
      "Record a caregiver observation. Note that the write path is separate from the patient check-in and still produces provenance.",
    cta: "Enter caregiver workspace",
  },
  clinician: {
    icon: Stethoscope,
    accent: "from-navy-800 to-navy-600",
    permissions: [
      "Twin review",
      "Alert acknowledgement",
      "Instruction verification",
      "Monitoring rules",
      "Audit",
    ],
    lookFor:
      "Verify the ambiguous inhaler instruction, acknowledge an alert, run a monitoring sweep and inspect the safety decisions.",
    cta: "Enter clinical workspace",
  },
};

export default function DemoPage() {
  const {
    session,
    users,
    selectedUser,
    loading,
    error,
    reload,
    switchUser,
    switching,
    switchError,
  } = useSession();
  const router = useRouter();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const visibleUsers = users.filter((user) => user.id !== "usr_priya");

  async function enter(user: DemoUser) {
    if (switching) return;
    setPendingId(user.id);
    const next = await switchUser(user).catch(() => null);
    setPendingId(null);
    if (!next) return;
    router.push(workspaceHome(next.role));
  }

  return (
    <div className="ct-app min-h-screen bg-mist-50">
      <header className="border-b border-slate-200/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 md:px-6">
          <div className="flex items-center gap-4">
            <Brand href="/" />
            <span className="hidden h-6 w-px bg-slate-200 sm:block" />
            <Link
              href="/"
              className="hidden items-center gap-1 text-xs font-semibold text-slate-500 hover:text-navy-900 sm:inline-flex"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Overview
            </Link>
          </div>
          <span className="flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[0.65rem] font-semibold text-amber-800">
            <FlaskConical className="h-3 w-3" /> Synthetic demo access
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-10 md:px-6 md:py-14">
        <div className="max-w-2xl">
          <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-care-700">
            Demo identity
          </p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-navy-950 md:text-4xl">
            Choose who is viewing Maya&apos;s recovery.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-slate-600">
            The same synthetic twin is projected through patient, caregiver and clinician
            scopes. The backend confirms the selected demo identity, then requests carry it
            as an{" "}
            <code className="rounded bg-white px-1.5 py-0.5 font-mono text-[0.7rem] text-slate-700 ring-1 ring-slate-200">
              X-Demo-User-Id
            </code>{" "}
            header.
          </p>
        </div>

        {loading && <LoadingBlock className="mt-8" label="Loading demo identities" />}

        {error && (
          <div className="mt-8 max-w-xl space-y-3">
            <ErrorState
              error={new Error(error)}
              onRetry={reload}
              title="Backend unavailable"
            />
            <p className="text-xs leading-relaxed text-slate-500">
              Start the API from the project root:{" "}
              <code className="rounded bg-white px-1.5 py-0.5 font-mono text-[0.68rem] ring-1 ring-slate-200">
                npm run dev:api
              </code>{" "}
              — then retry. The interface is intentionally honest when the safety core is
              not running.
            </p>
          </div>
        )}

        {switchError && (
          <InlineMessage
            tone="error"
            title="Could not switch demo identity"
            className="mt-6 max-w-xl"
          >
            {switchError}
          </InlineMessage>
        )}

        {!loading && !error && session && (
          <>
            <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {visibleUsers.map((user) => {
                const meta = roleMeta[user.role];
                const Icon = meta.icon;
                const active = selectedUser?.id === user.id;
                return (
                  <div
                    key={user.id}
                    className={cn(
                      "relative flex flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-white transition-all duration-300 hover:-translate-y-0.5 hover:border-care-300 hover:shadow-[0_20px_50px_-35px_rgba(4,19,32,0.5)]",
                      active && "ring-2 ring-care-500/40",
                    )}
                  >
                    <div className={cn("h-1 w-full bg-gradient-to-r", meta.accent)} />
                    <div className="flex flex-1 flex-col p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-care-600 text-sm font-bold text-white">
                            {user.initials}
                          </span>
                          <div>
                            <p className="text-sm font-semibold text-navy-950">{user.name}</p>
                            <p className="text-[0.68rem] text-slate-500">{user.title}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          <RoleBadge role={user.role} />
                          <Badge tone="teal">Consent active</Badge>
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-1.5">
                        {meta.permissions.map((permission) => (
                          <span
                            key={permission}
                            className="rounded-md bg-mist-50 px-2 py-1 text-[0.62rem] font-medium text-slate-600 ring-1 ring-slate-200/70"
                          >
                            {permission}
                          </span>
                        ))}
                      </div>

                      <p className="mt-4 flex-1 text-xs leading-relaxed text-slate-600">
                        {meta.lookFor}
                      </p>

                      <div className="mt-5 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
                        <span className="flex items-center gap-1.5 text-[0.62rem] font-medium text-slate-400">
                          <Icon className="h-3.5 w-3.5" />
                          {user.organization}
                        </span>
                        <Button
                          size="sm"
                          onClick={() => enter(user)}
                          disabled={switching}
                        >
                          {pendingId === user.id ? "Switching…" : "Enter"}
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                  <ClipboardCheck className="h-4 w-4 text-care-700" /> Working workflow
                </p>
                <p className="mt-1.5 text-[0.7rem] leading-relaxed text-slate-600">
                  Patient check-in creates evidence, a timeline event, rule alerts, a
                  safety decision and a new twin version.
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                  <BellRing className="h-4 w-4 text-care-700" /> Deterministic alerts
                </p>
                <p className="mt-1.5 text-[0.7rem] leading-relaxed text-slate-600">
                  Alerts are produced by clinician-configured thresholds. No generative
                  model participates in the safety path.
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="flex items-center gap-2 text-xs font-semibold text-navy-950">
                  <Eye className="h-4 w-4 text-care-700" /> Inspectable state
                </p>
                <p className="mt-1.5 text-[0.7rem] leading-relaxed text-slate-600">
                  Evidence, snapshots, audit entries and safety decisions are available in
                  the workspace rather than hidden behind claims.
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-3 rounded-xl border border-slate-200 bg-mist-100/60 px-4 py-3 text-[0.7rem] text-slate-600 sm:flex-row sm:items-center sm:justify-between">
              <p className="flex items-start gap-2">
                <FileSearch className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                {session.disclaimer}
              </p>
              <LinkButton href="/" variant="ghost" size="sm">
                Back to overview
              </LinkButton>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
