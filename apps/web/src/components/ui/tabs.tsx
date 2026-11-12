"use client";

import { cn } from "@caretwin/shared";

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: Array<{ value: T; label: string; count?: number }>;
  value: T;
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "scrollbar-thin flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-mist-100 p-1",
        className,
      )}
      role="tablist"
    >
      {items.map((item) => (
        <button
          key={item.value}
          role="tab"
          aria-selected={item.value === value}
          onClick={() => onChange(item.value)}
          className={cn(
            "whitespace-nowrap rounded-lg px-3.5 py-2 text-xs font-semibold transition-all",
            item.value === value
              ? "bg-white text-care-700 shadow-sm ring-1 ring-slate-200"
              : "text-slate-500 hover:bg-white/70 hover:text-navy-900",
          )}
        >
          {item.label}
          {typeof item.count === "number" && (
            <span className="ml-1.5 rounded bg-slate-200 px-1.5 py-0.5 font-mono text-[0.6rem] text-slate-600">
              {item.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
