import type { ReactNode } from "react";
import { cn } from "@caretwin/shared";

export function Card({
  children,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag
      className={cn(
        "relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04),0_14px_36px_-28px_rgba(15,23,42,0.22)] transition-colors duration-300",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

export function SectionCard({
  title,
  description,
  action,
  icon,
  children,
  className,
  bodyClassName,
  tone = "default",
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  tone?: "default" | "glow";
}) {
  return (
    <Card className={cn("group flex flex-col", tone === "glow" && "border-care-200", className)}>
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div className="flex min-w-0 items-start gap-3">
          {icon && (
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-care-100 bg-care-50 text-care-600">
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <h2 className="text-[0.9rem] font-semibold tracking-tight text-navy-950">{title}</h2>
            {description && (
              <p className="mt-0.5 text-[0.7rem] leading-relaxed text-slate-500">
                {description}
              </p>
            )}
          </div>
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <div className={cn("flex-1 px-5 py-4", bodyClassName)}>{children}</div>
    </Card>
  );
}

export function Metric({
  label,
  value,
  hint,
  icon,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl border border-slate-200 bg-white p-4 transition-all duration-300 hover:border-care-200 hover:bg-care-50/40",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-slate-500">
          {label}
        </p>
        {icon && <span className="text-care-500">{icon}</span>}
      </div>
      <p className="mt-2 font-display text-xl font-semibold tracking-tight text-navy-950">
        {value}
      </p>
      {hint && <p className="mt-1 text-[0.68rem] leading-relaxed text-slate-500">{hint}</p>}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="max-w-3xl">
        {eyebrow && (
          <p className="mb-1.5 flex items-center gap-2 text-[0.62rem] font-semibold uppercase tracking-[0.2em] text-care-600">
            <span className="h-px w-6 bg-care-300" aria-hidden="true" />
            {eyebrow}
          </p>
        )}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-navy-950 md:text-[1.9rem]">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
