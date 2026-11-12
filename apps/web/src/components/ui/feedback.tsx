"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@caretwin/shared";
import { ApiClientError, errorMessage } from "@/lib/api";
import { Button, LinkButton } from "@/components/ui/button";

export function LoadingBlock({
  label = "Loading recovery data",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-center gap-2.5 rounded-2xl border border-slate-200 bg-white px-5 py-12 text-sm text-slate-500",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-4 w-4 animate-spin text-care-600" />
      {label}…
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-5" aria-hidden="true">
      <div className="skeleton h-8 w-56 rounded-lg" />
      <div className="skeleton h-4 w-96 max-w-full rounded" />
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((item) => (
          <div
            key={item}
            className="skeleton h-36 rounded-2xl border border-slate-200"
          />
        ))}
      </div>
      <div className="skeleton h-72 rounded-2xl border border-slate-200" />
    </div>
  );
}

export function InlineMessage({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: "info" | "success" | "error" | "warning";
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  const config = {
    info: {
      icon: Info,
      classes: "border-sky-200 bg-sky-50 text-sky-900",
      iconClass: "text-sky-600",
    },
    success: {
      icon: CheckCircle2,
      classes: "border-emerald-200 bg-emerald-50 text-emerald-900",
      iconClass: "text-emerald-600",
    },
    error: {
      icon: AlertCircle,
      classes: "border-rose-200 bg-rose-50 text-rose-900",
      iconClass: "text-rose-600",
    },
    warning: {
      icon: AlertTriangle,
      classes: "border-amber-200 bg-amber-50 text-amber-900",
      iconClass: "text-amber-600",
    },
  }[tone];
  const Icon = config.icon;
  return (
    <div
      className={cn("rounded-xl border px-4 py-3 text-sm", config.classes, className)}
      role={tone === "error" ? "alert" : "status"}
    >
      <div className="flex gap-2.5">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", config.iconClass)} />
        <div className="min-w-0">
          {title && <p className="font-semibold">{title}</p>}
          <div className={cn("leading-relaxed", title && "mt-0.5")}>{children}</div>
        </div>
      </div>
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  title = "Unable to load recovery data",
  compact = false,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  compact?: boolean;
}) {
  const message = errorMessage(error);
  const isAccess = error instanceof ApiClientError && error.status === 403;
  const isNetwork = error instanceof ApiClientError && error.status === 0;
  return (
    <div
      className={cn(
        "rounded-2xl border border-rose-200 bg-rose-50 px-5 py-8 text-center",
        compact && "px-4 py-5 text-left",
      )}
      role="alert"
    >
      <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-rose-100 text-rose-600">
        <ShieldAlert className="h-5 w-5" />
      </span>
      <h2 className="mt-3 text-sm font-semibold text-navy-950">{title}</h2>
      <p className="mx-auto mt-1.5 max-w-lg text-sm leading-relaxed text-slate-600">
        {message}
      </p>
      {isNetwork && (
        <p className="mx-auto mt-3 max-w-lg rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-[0.7rem] text-slate-600">
          python -m uvicorn app.main:app --reload --port 8000 --app-dir apps/api
        </p>
      )}
      {isAccess && (
        <p className="mx-auto mt-2 max-w-lg text-xs text-slate-500">
          This is an expected permission boundary, not a data error. Switch to an
          authorized demo role or ask the patient to update consent.
        </p>
      )}
      {onRetry && !isAccess && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-mist-50 px-5 py-8 text-center",
        className,
      )}
    >
      {icon && (
        <span className="mb-2 flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-care-500">
          {icon}
        </span>
      )}
      <p className="text-sm font-semibold text-navy-900">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">
          {description}
        </p>
      )}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function AccessRestricted({
  title = "Sharing is not active",
  description,
  showConsentLink = false,
}: {
  title?: string;
  description?: string;
  showConsentLink?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-6 py-10 text-center">
      <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-amber-100 text-amber-600 ring-1 ring-amber-200">
        <LockKeyhole className="h-5 w-5" />
      </span>
      <h2 className="mt-3 font-display text-lg font-semibold text-navy-950">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-relaxed text-slate-600">
        {description ??
          "The patient has not granted an active consent scope for this information. CareTwin AI enforces consent at the API boundary, so no recovery data is returned to this role."}
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        {showConsentLink && (
          <LinkButton href="/workspace/consent" variant="secondary" size="sm">
            View consent state
          </LinkButton>
        )}
        <LinkButton href="/demo" variant="ghost" size="sm">
          Switch demo role
        </LinkButton>
      </div>
    </div>
  );
}

export function SafetyFooterNote({ compact = false }: { compact?: boolean }) {
  return (
    <p className={cn("text-[0.7rem] leading-relaxed text-slate-500", compact && "text-[0.65rem]")}>
      CareTwin AI organizes documented and reported information. It does not diagnose,
      prescribe, or replace clinical judgment. In an emergency, contact local emergency
      services.
    </p>
  );
}

export function DemoAccessNote() {
  return (
    <InlineMessage tone="info" title="Synthetic demo access">
      No real patient information. Demo identity is sent with an{" "}
      <code className="rounded bg-white px-1 py-0.5 font-mono text-[0.68rem] text-slate-700 ring-1 ring-slate-200">
        X-Demo-User-Id
      </code>{" "}
      header and is not production authentication.
    </InlineMessage>
  );
}

export function BackendOfflineLink() {
  return (
    <Link href="/demo" className="text-care-600 underline underline-offset-2">
      Open demo access
    </Link>
  );
}
