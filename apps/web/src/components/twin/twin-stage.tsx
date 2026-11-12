"use client";

import dynamic from "next/dynamic";
import { cn } from "@caretwin/shared";

const DigitalTwin3D = dynamic(() => import("@/components/twin/digital-twin-3d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3">
      <span className="h-11 w-11 animate-spin rounded-full border-2 border-care-300/25 border-t-care-300" />
      <p className="text-[0.6rem] uppercase tracking-[0.22em] text-slate-500">
        Loading twin projection
      </p>
    </div>
  ),
});

export function TwinStage({
  status = "on_track",
  className,
  compact = false,
  showSystems = true,
}: {
  status?: "on_track" | "needs_attention" | "urgent_review";
  className?: string;
  compact?: boolean;
  showSystems?: boolean;
}) {
  return (
    <div className={cn("relative h-full w-full", className)}>
      <DigitalTwin3D
        status={status}
        compact={compact}
        showSystems={showSystems}
        className="h-full w-full"
      />
    </div>
  );
}

export default TwinStage;
