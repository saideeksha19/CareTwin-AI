import { cn } from "@caretwin/shared";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

const base =
  "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-navy-950 shadow-sm placeholder:text-slate-400 transition-colors focus:border-care-500 focus:outline-none focus:ring-2 focus:ring-care-500/20 disabled:bg-mist-100 disabled:text-slate-400";

export function Field({
  label,
  htmlFor,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label
        htmlFor={htmlFor}
        className="flex items-center gap-1 text-xs font-semibold text-navy-800"
      >
        {label}
        {required && <span className="text-rose-500">*</span>}
      </label>
      {children}
      {hint && !error && <p className="text-[0.68rem] text-slate-500">{hint}</p>}
      {error && (
        <p className="text-[0.68rem] font-medium text-rose-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(base, className)} {...props} />;
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(base, "min-h-24 resize-y", className)} {...props} />;
}

export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(base, "appearance-none pr-8", className)} {...props}>
      {children}
    </select>
  );
}

export function RangeField({
  label,
  value,
  onChange,
  min = 0,
  max = 10,
  step = 1,
  leftLabel,
  rightLabel,
  hint,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  leftLabel?: string;
  rightLabel?: string;
  hint?: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label className="text-xs font-semibold text-navy-800">{label}</label>
        <span className="rounded-md bg-care-50 px-2 py-0.5 font-mono text-xs font-semibold text-care-700">
          {value}
          <span className="text-slate-400">/{max}</span>
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-2.5 w-full cursor-pointer"
        aria-label={label}
      />
      <div className="mt-1 flex justify-between text-[0.62rem] font-medium uppercase tracking-wide text-slate-500">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
      {hint && <p className="mt-1 text-[0.68rem] text-slate-500">{hint}</p>}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <label className={cn("flex items-start gap-3", disabled && "opacity-60")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors",
          checked ? "bg-care-600" : "bg-slate-300",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
            checked ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </button>
      <span>
        <span className="block text-xs font-semibold text-navy-800">{label}</span>
        {description && (
          <span className="mt-0.5 block text-[0.68rem] leading-relaxed text-slate-500">
            {description}
          </span>
        )}
      </span>
    </label>
  );
}
