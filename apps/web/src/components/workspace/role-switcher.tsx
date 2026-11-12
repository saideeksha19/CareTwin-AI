"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  Loader2,
  ShieldCheck,
  Stethoscope,
  Users,
  X,
} from "lucide-react";
import type { DemoUser, UserRole } from "@caretwin/contracts";
import { cn } from "@caretwin/shared";
import { useSession } from "@/lib/session";
import { workspaceHome } from "@/lib/nav";
import { Badge, RoleBadge } from "@/components/ui/badges";
import { InlineMessage } from "@/components/ui/feedback";

const roleCopy: Record<
  UserRole,
  { label: string; detail: string; icon: typeof ShieldCheck }
> = {
  patient: {
    label: "Patient",
    detail: "Full recovery record, check-ins, medications and consent control.",
    icon: ShieldCheck,
  },
  caregiver: {
    label: "Caregiver",
    detail: "Consent-scoped twin, schedule, alerts and observation workflow.",
    icon: Users,
  },
  clinician: {
    label: "Clinician",
    detail: "Clinical review, alert acknowledgement, instructions and audit.",
    icon: Stethoscope,
  },
};

function consentState(user: DemoUser) {
  if (user.role === "patient") {
    return { label: "Patient record", tone: "teal" as const, icon: ShieldCheck };
  }
  if (user.role === "clinician") {
    return { label: "Clinical access", tone: "blue" as const, icon: Stethoscope };
  }
  return { label: "Consent active", tone: "violet" as const, icon: Users };
}

export function RoleSwitcher({
  open,
  onClose,
  onSwitched,
}: {
  open: boolean;
  onClose: () => void;
  onSwitched: (user: DemoUser) => void;
}) {
  const { users, selectedUser, switchUser, switching, switchError, clearSwitchError } =
    useSession();
  const router = useRouter();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const visibleUsers = users.filter((user) => user.id !== "usr_priya");

  useEffect(() => {
    if (!open) return;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    clearSwitchError();
    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open, onClose, clearSwitchError]);

  async function choose(user: DemoUser) {
    if (switching) return;
    if (user.id === selectedUser?.id) {
      onClose();
      return;
    }
    setPendingId(user.id);
    const next = await switchUser(user).catch(() => null);
    setPendingId(null);
    if (!next) return;
    onSwitched(next);
    onClose();
    router.push(workspaceHome(next.role));
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-end justify-center bg-navy-950/40 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="demo-role-dialog-title"
        aria-describedby="demo-role-dialog-description"
        aria-busy={switching}
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-slate-200 bg-white shadow-[0_30px_90px_-30px_rgba(4,19,32,0.55)] sm:max-w-3xl sm:rounded-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4 sm:px-6">
          <div>
            <p className="text-[0.6rem] font-semibold uppercase tracking-[0.18em] text-care-700">
              Demo identity
            </p>
            <h2
              id="demo-role-dialog-title"
              className="mt-1 font-display text-xl font-semibold tracking-tight text-navy-950"
            >
              Switch demo access
            </h2>
            <p
              id="demo-role-dialog-description"
              className="mt-1 max-w-xl text-xs leading-relaxed text-slate-500"
            >
              Choose who is viewing Maya&apos;s synthetic recovery record. The backend
              confirms the identity and every workspace request stays role-scoped.
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close demo role switcher"
            className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 transition-colors hover:bg-mist-100 hover:text-navy-900 focus:outline-none focus:ring-2 focus:ring-care-500/40"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-5 sm:px-6">
          {switchError && (
            <InlineMessage tone="error" title="Could not switch demo role">
              {switchError}
            </InlineMessage>
          )}

          <p className="sr-only" role="status" aria-live="polite">
            {switching ? "Switching demo identity" : ""}
          </p>

          <ul className="grid gap-2.5 sm:grid-cols-2 md:grid-cols-3">
            {visibleUsers.map((user) => {
              const copy = roleCopy[user.role];
              const consent = consentState(user);
              const active = selectedUser?.id === user.id;
              const pending = switching && pendingId === user.id;
              const ConsentIcon = consent.icon;
              const RoleIcon = copy.icon;
              return (
                <li key={user.id}>
                  <button
                    type="button"
                    onClick={() => choose(user)}
                    disabled={switching}
                    aria-current={active ? "true" : undefined}
                    aria-label={
                      active
                        ? `${user.name}, current demo identity`
                        : `Switch to ${user.name}, ${copy.label}`
                    }
                    className={cn(
                      "flex w-full items-start gap-3 rounded-xl border p-3.5 text-left transition-all focus:outline-none focus:ring-2 focus:ring-care-500/40 disabled:cursor-wait disabled:opacity-70",
                      active
                        ? "border-care-300 bg-care-50/70 ring-1 ring-care-200"
                        : "border-slate-200 bg-white hover:border-care-200 hover:bg-mist-50",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white",
                        user.role === "caregiver"
                          ? "bg-violet-600"
                          : user.role === "clinician"
                            ? "bg-navy-800"
                            : "bg-care-600",
                      )}
                    >
                      {user.initials}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-1.5">
                        <span className="truncate text-sm font-semibold text-navy-950">
                          {user.name}
                        </span>
                        <RoleBadge role={user.role} />
                        {active && (
                          <Badge tone="teal">
                            <CheckCircle2 className="h-3 w-3" /> Current
                          </Badge>
                        )}
                      </span>
                      <span className="mt-0.5 block truncate text-[0.68rem] text-slate-500">
                        {user.title}
                      </span>
                      <span className="mt-2 flex flex-wrap items-center gap-1.5">
                        <Badge tone={consent.tone}>
                          <ConsentIcon className="h-3 w-3" />
                          {consent.label}
                        </Badge>
                        <span className="inline-flex items-center gap-1 text-[0.6rem] font-medium text-slate-400">
                          <RoleIcon className="h-3 w-3" />
                          {copy.label} scope
                        </span>
                      </span>
                      <span className="mt-2 block text-[0.66rem] leading-relaxed text-slate-500">
                        {copy.detail}
                      </span>
                    </span>
                    {pending && (
                      <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-care-600" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="rounded-xl border border-slate-200 bg-mist-50 px-4 py-3 text-[0.68rem] leading-relaxed text-slate-500">
            This switcher changes a synthetic demo identity only. It never changes a
            production sign-in, role assignment or consent record.
          </div>
        </div>
      </div>
    </div>
  );
}
