"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Bell,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  FileText,
  FlaskConical,
  History,
  LayoutDashboard,
  Menu,
  Orbit,
  ScrollText,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { cn } from "@caretwin/shared";
import type { DemoUser } from "@caretwin/contracts";
import { useSession } from "@/lib/session";
import { navForRole, navGroupsForRole, type NavIcon, type NavItem } from "@/lib/nav";
import { Brand } from "@/components/brand";
import { LoadingBlock, ErrorState } from "@/components/ui/feedback";
import { RoleSwitcher } from "@/components/workspace/role-switcher";

const icons = {
  overview: LayoutDashboard,
  twin: Orbit,
  documents: FileText,
  labs: FlaskConical,
  history: ScrollText,
  timeline: History,
  alerts: Bell,
  assistant: Sparkles,
  guidance: Sparkles,
  careteam: Users,
  consent: ShieldCheck,
  settings: Settings,
  checkin: ClipboardCheck,
  schedule: CalendarClock,
  intelligence: BrainCircuit,
} as const satisfies Record<NavIcon, unknown>;

function isActive(pathname: string, href: string) {
  if (href === "/workspace") return pathname === "/workspace";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { selectedUser } = useSession();
  if (!selectedUser) return null;
  const groups = navGroupsForRole(selectedUser.role);

  return (
    <nav
      className="scrollbar-thin flex-1 space-y-5 overflow-y-auto px-3 pb-4 pt-2"
      aria-label="Workspace navigation"
    >
      {groups.map((group) => (
        <div key={group.label}>
          <p className="px-3 pb-1.5 text-[0.55rem] font-semibold uppercase tracking-[0.18em] text-slate-400">
            {group.label}
          </p>
          <div className="space-y-0.5">
            {group.items.map((item: NavItem) => {
              const Icon = icons[item.icon];
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[0.79rem] font-medium transition-colors",
                    active
                      ? "bg-care-50 text-care-700"
                      : "text-slate-600 hover:bg-mist-100 hover:text-navy-900",
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-care-600" />
                  )}
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0 transition-colors",
                      active ? "text-care-600" : "text-slate-400 group-hover:text-slate-600",
                    )}
                  />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function PatientCard() {
  const { selectedUser, session } = useSession();
  if (!selectedUser) return null;
  return (
    <div className="mx-3 mt-3 rounded-xl border border-care-100 bg-care-50 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[0.55rem] font-semibold uppercase tracking-[0.16em] text-care-700">
          Active patient
        </p>
        <span className="rounded-full bg-white px-1.5 py-0.5 text-[0.52rem] font-semibold uppercase tracking-wide text-care-700 ring-1 ring-care-200">
          Synthetic
        </span>
      </div>
      <p className="mt-1.5 truncate text-[0.86rem] font-semibold text-navy-950">
        {session?.patient.fullName ?? selectedUser.linkedPatientName}
      </p>
      <p className="mt-0.5 truncate text-[0.64rem] text-slate-500">
        Linked record · {selectedUser.linkedPatientName}
      </p>
    </div>
  );
}

function RoleSelector({
  onOpen,
  expanded,
}: {
  onOpen: () => void;
  expanded: boolean;
}) {
  const { selectedUser } = useSession();
  if (!selectedUser) return null;
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label="Switch demo role"
      aria-haspopup="dialog"
      aria-expanded={expanded}
      className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white py-1.5 pl-2 pr-2 shadow-sm transition-colors hover:border-care-200 hover:bg-mist-50 focus:outline-none focus:ring-2 focus:ring-care-500/40"
    >
      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-care-600 text-[0.6rem] font-bold text-white">
        {selectedUser.initials}
      </span>
      <span className="hidden min-w-0 sm:block">
        <span className="block max-w-[9.5rem] truncate text-[0.7rem] font-semibold leading-tight text-navy-950">
          {selectedUser.name}
        </span>
        <span className="block max-w-[9.5rem] truncate text-[0.58rem] capitalize leading-tight text-slate-500">
          {selectedUser.role} · {selectedUser.organization}
        </span>
      </span>
      <ChevronDown className="h-3 w-3 shrink-0 text-slate-400" aria-hidden="true" />
    </button>
  );
}

function SidebarBody({
  onNavigate,
  onOpenSwitcher,
}: {
  onNavigate?: () => void;
  onOpenSwitcher: () => void;
}) {
  const { selectedUser } = useSession();
  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex h-[4.5rem] items-center justify-between border-b border-slate-100 px-4">
        <Brand href={selectedUser ? "/workspace" : "/"} />
      </div>
      <PatientCard />
      <SidebarNav onNavigate={onNavigate} />
      <div className="mt-auto border-t border-slate-100 p-3">
        <div className="rounded-xl border border-slate-200 bg-mist-50 p-3">
          <div className="flex items-center gap-1.5 text-[0.55rem] font-semibold uppercase tracking-[0.16em] text-care-700">
            <ShieldCheck className="h-3 w-3" /> Safety boundary
          </div>
          <p className="mt-1.5 text-[0.64rem] leading-relaxed text-slate-500">
            Organizes documented and reported information. No diagnosis, prescribing,
            or clinical replacement.
          </p>
          <button
            type="button"
            onClick={onOpenSwitcher}
            aria-haspopup="dialog"
            className="mt-2.5 inline-flex items-center gap-1 text-[0.64rem] font-semibold text-care-600 hover:text-care-700 focus:outline-none focus:ring-2 focus:ring-care-500/40"
          >
            Switch demo access
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { selectedUser, loading, error, reload } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [switchNotice, setSwitchNotice] = useState<string | null>(null);

  const openSwitcher = useCallback(() => {
    setMobileOpen(false);
    setSwitcherOpen(true);
  }, []);

  const closeSwitcher = useCallback(() => setSwitcherOpen(false), []);

  const handleSwitched = useCallback((user: DemoUser) => {
    setSwitchNotice(`Now viewing as ${user.name} · ${user.role}`);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!switchNotice) return;
    const timer = window.setTimeout(() => setSwitchNotice(null), 6000);
    return () => window.clearTimeout(timer);
  }, [switchNotice]);

  useEffect(() => {
    if (!loading && !error && !selectedUser) {
      router.replace("/demo");
    }
  }, [loading, error, selectedUser, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md">
          <LoadingBlock label="Preparing the recovery twin" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-lg">
          <ErrorState error={new Error(error)} onRetry={reload} />
          <Link
            href="/"
            className="mt-4 block text-center text-xs font-semibold text-slate-500 hover:text-navy-900"
          >
            Return to overview
          </Link>
        </div>
      </div>
    );
  }

  if (!selectedUser) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <LoadingBlock label="Opening demo access" />
      </div>
    );
  }

  const current =
    pathname === "/workspace"
      ? { label: "Dashboard" }
      : navForRole(selectedUser.role).find(
          (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
        );

  return (
    <div className="ct-app relative min-h-screen bg-mist-50">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[16.5rem] border-r border-slate-200 bg-white lg:block">
        <SidebarBody onOpenSwitcher={openSwitcher} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-navy-950/30 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[17rem] max-w-[85vw] border-r border-slate-200 bg-white shadow-xl">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-4 z-10 rounded-lg p-1.5 text-slate-500 hover:bg-mist-100"
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
            <SidebarBody
              onNavigate={() => setMobileOpen(false)}
              onOpenSwitcher={openSwitcher}
            />
          </div>
        </div>
      )}

      <div className="lg:pl-[16.5rem]">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur-xl">
          <div className="flex h-[4.5rem] items-center justify-between gap-3 px-4 md:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                onClick={() => setMobileOpen(true)}
                className="rounded-lg border border-slate-200 bg-white p-2 text-slate-600 lg:hidden"
                aria-label="Open navigation"
              >
                <Menu className="h-4 w-4" />
              </button>
              <div className="min-w-0">
                <p className="flex items-center gap-1 text-[0.6rem] font-medium text-slate-400">
                  <span>Workspace</span>
                  <ChevronRight className="h-3 w-3" aria-hidden="true" />
                  <span className="text-slate-600">{current?.label ?? "Overview"}</span>
                </p>
                <p className="truncate text-[0.95rem] font-semibold text-navy-950">
                  {selectedUser.linkedPatientName}
                  <span className="ml-2 hidden text-[0.72rem] font-normal text-slate-500 sm:inline">
                    {selectedUser.organization}
                  </span>
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[0.58rem] font-semibold uppercase tracking-[0.1em] text-emerald-700 md:inline-flex">
                <Activity className="h-3 w-3" /> Connected
              </span>
              <span className="hidden items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[0.58rem] font-semibold uppercase tracking-[0.1em] text-amber-700 lg:inline-flex">
                Demo data only
              </span>
              <Link
                href="/workspace/alerts"
                className="relative rounded-lg border border-slate-200 bg-white p-2 text-slate-500 transition-colors hover:bg-mist-100 hover:text-navy-900"
                aria-label="Open monitoring alerts"
              >
                <Bell className="h-4 w-4" />
                <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-care-600" />
              </Link>
              <RoleSelector onOpen={openSwitcher} expanded={switcherOpen} />
            </div>
          </div>
        </header>

        <main key={pathname} className="animate-fade-in mx-auto w-full max-w-[1600px] px-4 py-6 md:px-6 md:py-8 lg:px-8">
          {children}
        </main>

        <footer className="mx-auto flex w-full max-w-[1600px] flex-col gap-2 px-4 pb-8 text-[0.62rem] text-slate-500 md:flex-row md:items-center md:justify-between md:px-6 lg:px-8">
          <span>
            CareTwin AI · Your Health. Your Digital Twin. Always With You. ·
            synthetic demonstration
          </span>
          <span className="flex items-center gap-3">
            <button
              type="button"
              onClick={openSwitcher}
              aria-haspopup="dialog"
              className="font-semibold text-slate-600 hover:text-navy-900 focus:outline-none focus:ring-2 focus:ring-care-500/40"
            >
              Change demo role
            </button>
          </span>
        </footer>
      </div>

      <RoleSwitcher
        open={switcherOpen}
        onClose={closeSwitcher}
        onSwitched={handleSwitched}
      />

      {switchNotice && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-4 left-4 right-4 z-[60] flex items-center gap-2 rounded-xl border border-emerald-200 bg-white px-4 py-3 text-xs font-semibold text-emerald-800 shadow-lg sm:left-auto sm:right-6 sm:w-auto"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          {switchNotice}
        </div>
      )}
    </div>
  );
}
