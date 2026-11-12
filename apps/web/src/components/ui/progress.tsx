import { cn, percent } from "@caretwin/shared";
import type { TwinStatus } from "@caretwin/contracts";

export function ProgressRing({
  completed,
  total,
  size = 92,
  stroke = 8,
  status = "on_track",
  label,
  ariaLabel,
  className,
}: {
  completed: number;
  total: number;
  size?: number;
  stroke?: number;
  status?: TwinStatus;
  label?: string;
  ariaLabel?: string;
  className?: string;
}) {
  const value = percent(completed, total);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const color =
    status === "on_track" ? "#2563eb" : status === "needs_attention" ? "#d97706" : "#e11d48";

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={
        ariaLabel ?? `Recovery milestones: ${completed} of ${total} complete (${value}%)`
      }
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="font-display text-xl font-semibold tracking-tight text-navy-950">
          {value}%
        </span>
        <span className="text-[0.55rem] font-semibold uppercase tracking-[0.12em] text-slate-500">
          {label ?? `${completed}/${total} done`}
        </span>
      </div>
    </div>
  );
}

export function ProgressBar({
  value,
  tone = "teal",
  className,
}: {
  value: number;
  tone?: "teal" | "amber" | "rose";
  className?: string;
}) {
  const color =
    tone === "teal"
      ? "bg-care-600"
      : tone === "amber"
        ? "bg-amber-500"
        : "bg-rose-500";
  return (
    <div
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-slate-200", className)}
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn("h-full rounded-full transition-all duration-700", color)}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}
