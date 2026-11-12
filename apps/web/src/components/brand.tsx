import Link from "next/link";
import { cn } from "@caretwin/shared";

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      aria-hidden="true"
      className={cn("h-9 w-9", className)}
      fill="none"
    >
      <rect width="40" height="40" rx="11" fill="currentColor" />
      <circle cx="20" cy="20" r="10.5" stroke="white" strokeOpacity="0.35" />
      <circle cx="20" cy="20" r="5.4" stroke="white" strokeOpacity="0.6" />
      <path
        d="M20 12.2v15.6M12.2 20h15.6"
        stroke="white"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeOpacity="0.9"
      />
      <circle cx="20" cy="20" r="2.2" fill="#bfdbfe" />
      <circle cx="29.2" cy="13.6" r="1.7" fill="#dbeafe" />
      <circle cx="10.8" cy="27.2" r="1.4" fill="#bfdbfe" />
      <circle cx="28.6" cy="27.6" r="1.2" fill="white" fillOpacity="0.8" />
    </svg>
  );
}

export function Brand({
  href = "/",
  tone = "dark",
  compact = false,
}: {
  href?: string;
  tone?: "dark" | "light";
  compact?: boolean;
}) {
  return (
    <Link
      href={href}
      className="group inline-flex items-center gap-2.5"
      aria-label="CareTwin AI home"
    >
      <BrandMark
        className={cn(
          tone === "light" ? "text-white/15" : "text-care-600",
          "transition-transform duration-300 group-hover:scale-[1.03]",
        )}
      />
      <span className="flex flex-col leading-none">
        <span
          className={cn(
            "font-display text-[1.05rem] font-semibold tracking-tight",
            tone === "light" ? "text-white" : "text-navy-950",
          )}
        >
          CareTwin <span className={tone === "light" ? "text-care-300" : "text-care-600"}>AI</span>
        </span>
        {!compact && (
          <span
            className={cn(
              "mt-1 text-[0.59rem] font-medium uppercase tracking-[0.19em]",
              tone === "light" ? "text-white/60" : "text-slate-500",
            )}
          >
            Recovery intelligence
          </span>
        )}
      </span>
    </Link>
  );
}
