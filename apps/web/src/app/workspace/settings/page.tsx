"use client";

import {
  Activity,
  BrainCircuit,
  Database,
  Fingerprint,
  Globe2,
  Server,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { AiStatus } from "@caretwin/contracts";
import { API_BASE_URL } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";
import { PageHeader, SectionCard } from "@/components/ui/cards";
import { Badge } from "@/components/ui/badges";
import { LinkButton } from "@/components/ui/button";
import { DemoAccessNote, InlineMessage, PageSkeleton } from "@/components/ui/feedback";

type HealthResponse = {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
  aiState: string;
  demoMode: boolean;
};

type MetaResponse = {
  name: string;
  apiPrefix: string;
  docs: string;
  syntheticOnly: boolean;
  generatedAt: string;
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-2 last:border-0">
      <span className="text-[0.68rem] text-slate-400">{label}</span>
      <span className="min-w-0 truncate text-right text-[0.7rem] font-medium text-navy-900">
        {value}
      </span>
    </div>
  );
}

export default function SettingsPage() {
  const { selectedUser } = useSession();
  const health = useApi<HealthResponse>("/health");
  const meta = useApi<MetaResponse>("/meta");
  const ai = useApi<AiStatus>("/ai/status");

  if (!selectedUser) return <PageSkeleton />;

  return (
    <div>
      <PageHeader
        eyebrow="Settings"
        title="Workspace &amp; system status"
        description="Read-only environment information for this demonstration workspace. CareTwin AI does not offer account, billing or security configuration in demo mode; those are intentionally absent rather than simulated."
        actions={<Badge tone="amber">Synthetic demo</Badge>}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard
          title="Current session"
          description="Demo identity sent as a request header"
          icon={<UserRound className="h-4 w-4" />}
        >
          <Row label="Name" value={selectedUser.name} />
          <Row label="Role" value={<span className="capitalize">{selectedUser.role}</span>} />
          <Row label="Title" value={selectedUser.title} />
          <Row label="Organization" value={selectedUser.organization} />
          <Row label="Linked patient" value={selectedUser.linkedPatientName} />
          <Row label="Patient ID" value={selectedUser.patientId} />
          <div className="mt-3">
            <LinkButton href="/demo" variant="secondary" size="sm">
              Switch demo identity
            </LinkButton>
          </div>
        </SectionCard>

        <SectionCard
          title="Backend connection"
          description="Live values read from the FastAPI service"
          icon={<Server className="h-4 w-4" />}
        >
          {health.loading ? (
            <div className="skeleton h-28 rounded-lg" />
          ) : health.error ? (
            <InlineMessage tone="error" title="Backend unreachable">
              Start the API on 127.0.0.1:8000 to populate live system status.
            </InlineMessage>
          ) : (
            <>
              <Row
                label="Health"
                value={
                  <Badge tone={health.data?.status === "ok" ? "teal" : "amber"}>
                    {health.data?.status ?? "unknown"}
                  </Badge>
                }
              />
              <Row label="Service" value={health.data?.service ?? "—"} />
              <Row label="Version" value={health.data?.version ?? "—"} />
              <Row label="Environment" value={health.data?.environment ?? "—"} />
              <Row label="Database" value={health.data?.database ?? "—"} />
              <Row label="Demo mode" value={health.data?.demoMode ? "Enabled" : "Disabled"} />
            </>
          )}
          <Row label="API base URL" value={<span className="font-mono text-[0.62rem]">{API_BASE_URL}</span>} />
          <Row label="API prefix" value={meta.data?.apiPrefix ?? "—"} />
        </SectionCard>

        <SectionCard
          title="AI boundary"
          description="Server-side only · configuration never reaches the browser"
          icon={<BrainCircuit className="h-4 w-4" />}
        >
          {ai.loading ? (
            <div className="skeleton h-24 rounded-lg" />
          ) : ai.error ? (
            <InlineMessage tone="warning" title="AI status unavailable">
              The status endpoint could not be reached. AI explanations remain disabled.
            </InlineMessage>
          ) : (
            <>
              <Row
                label="State"
                value={
                  <Badge
                    tone={
                      ai.data?.state === "ready"
                        ? "teal"
                        : ai.data?.state === "error"
                          ? "rose"
                          : "amber"
                    }
                  >
                    {(ai.data?.state ?? "unknown").replaceAll("_", " ")}
                  </Badge>
                }
              />
              <Row label="Provider" value={ai.data?.provider ?? "—"} />
              <Row label="Model" value={ai.data?.model ?? "—"} />
              <Row
                label="Grounded context"
                value={ai.data?.groundedContextReady ? "Ready" : "Not prepared"}
              />
              <Row label="Server-side only" value={ai.data?.serverSideOnly ? "Yes" : "No"} />
            </>
          )}
          <p className="mt-2 rounded-lg bg-mist-50 px-3 py-2 text-[0.64rem] leading-relaxed text-slate-400">
            {ai.data?.message ??
              "When no model is configured, guidance falls back to deterministic, source-quoted summaries."}
          </p>
        </SectionCard>

        <SectionCard
          title="Data, privacy & safety"
          description="What this deployment does and does not claim"
          icon={<ShieldCheck className="h-4 w-4" />}
        >
          <div className="flex items-start gap-2.5 rounded-lg border border-slate-100 bg-mist-50 p-3">
            <Database className="mt-0.5 h-4 w-4 shrink-0 text-care-600" />
            <p className="text-[0.66rem] leading-relaxed text-slate-300">
              SQLite demo database with versioned twin snapshots and an immutable event
              timeline. Uploaded original documents are retained in protected local
              storage.
            </p>
          </div>
          <div className="mt-2 flex items-start gap-2.5 rounded-lg border border-slate-100 bg-mist-50 p-3">
            <Fingerprint className="mt-0.5 h-4 w-4 shrink-0 text-care-600" />
            <p className="text-[0.66rem] leading-relaxed text-slate-300">
              Provenance is part of the data model: every item carries source, author,
              verification and review state.
            </p>
          </div>
          <div className="mt-2 flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3">
            <Globe2 className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
            <p className="text-[0.66rem] leading-relaxed text-amber-700">
              No HIPAA, GDPR or other certification claim is made. This is a synthetic
              demonstration build, not production clinical software.
            </p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <LinkButton href="/workspace/consent" variant="secondary" size="sm">
              <ShieldCheck className="h-3.5 w-3.5" /> Privacy &amp; consent
            </LinkButton>
            <LinkButton href="/workspace/intelligence" variant="ghost" size="sm">
              <Activity className="h-3.5 w-3.5" /> AI, evidence &amp; audit
            </LinkButton>
          </div>
        </SectionCard>
      </div>

      <div className="mt-4">
        <DemoAccessNote />
      </div>
    </div>
  );
}
