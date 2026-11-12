import type { UserRole } from "@caretwin/contracts";

export type NavIcon =
  | "overview"
  | "twin"
  | "documents"
  | "labs"
  | "history"
  | "timeline"
  | "alerts"
  | "assistant"
  | "guidance"
  | "careteam"
  | "consent"
  | "settings"
  | "checkin"
  | "schedule"
  | "intelligence";

export type NavItem = {
  href: string;
  label: string;
  icon: NavIcon;
  description?: string;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

const patientGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/workspace", label: "Dashboard", icon: "overview" },
      { href: "/workspace/twin", label: "My Digital Twin", icon: "twin" },
    ],
  },
  {
    label: "Health record",
    items: [
      { href: "/workspace/documents", label: "Medical Documents", icon: "documents" },
      { href: "/workspace/labs", label: "Lab Reports", icon: "labs" },
      { href: "/workspace/history", label: "Medical History", icon: "history" },
      { href: "/workspace/timeline", label: "Health Timeline", icon: "timeline" },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { href: "/workspace/alerts", label: "Monitoring & Alerts", icon: "alerts" },
      { href: "/workspace/assistant", label: "AI Health Assistant", icon: "assistant" },
    ],
  },
  {
    label: "Care network",
    items: [
      { href: "/workspace/care-team", label: "Care Team", icon: "careteam" },
      { href: "/workspace/settings", label: "Settings", icon: "settings" },
    ],
  },
  {
    label: "Daily care",
    items: [
      { href: "/workspace/check-in", label: "Daily Check-in", icon: "checkin" },
      { href: "/workspace/schedule", label: "Medications & Follow-ups", icon: "schedule" },
    ],
  },
  {
    label: "More",
    items: [
      { href: "/workspace/guidance", label: "Recovery Guidance", icon: "guidance" },
      { href: "/workspace/consent", label: "Privacy & Consent", icon: "consent" },
      { href: "/workspace/intelligence", label: "Intelligence & Trust", icon: "intelligence" },
    ],
  },
];

const caregiverGroups: NavGroup[] = [
  {
    label: "Shared care",
    items: [
      { href: "/workspace/caregiver", label: "Dashboard", icon: "overview" },
      { href: "/workspace/twin", label: "My Digital Twin", icon: "twin" },
    ],
  },
  {
    label: "Health record",
    items: [
      { href: "/workspace/documents", label: "Medical Documents", icon: "documents" },
      { href: "/workspace/labs", label: "Lab Reports", icon: "labs" },
      { href: "/workspace/history", label: "Medical History", icon: "history" },
      { href: "/workspace/timeline", label: "Health Timeline", icon: "timeline" },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { href: "/workspace/alerts", label: "Monitoring & Alerts", icon: "alerts" },
      { href: "/workspace/guidance", label: "Recovery Guidance", icon: "guidance" },
    ],
  },
  {
    label: "Care network",
    items: [
      { href: "/workspace/care-team", label: "Care Team", icon: "careteam" },
      { href: "/workspace/consent", label: "Privacy & Consent", icon: "consent" },
      { href: "/workspace/settings", label: "Settings", icon: "settings" },
    ],
  },
  {
    label: "Daily care",
    items: [
      { href: "/workspace/check-in", label: "Daily Check-in", icon: "checkin" },
      { href: "/workspace/schedule", label: "Medications & Follow-ups", icon: "schedule" },
    ],
  },
];

const clinicianGroups: NavGroup[] = [
  {
    label: "Clinical workspace",
    items: [
      { href: "/workspace/clinician", label: "Dashboard", icon: "overview" },
      { href: "/workspace/twin", label: "My Digital Twin", icon: "twin" },
    ],
  },
  {
    label: "Health record",
    items: [
      { href: "/workspace/documents", label: "Medical Documents", icon: "documents" },
      { href: "/workspace/labs", label: "Lab Reports", icon: "labs" },
      { href: "/workspace/history", label: "Medical History", icon: "history" },
      { href: "/workspace/timeline", label: "Health Timeline", icon: "timeline" },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { href: "/workspace/alerts", label: "Monitoring & Alerts", icon: "alerts" },
      { href: "/workspace/assistant", label: "AI Health Assistant", icon: "assistant" },
      { href: "/workspace/guidance", label: "Recovery Guidance", icon: "guidance" },
    ],
  },
  {
    label: "Care network",
    items: [
      { href: "/workspace/care-team", label: "Care Team", icon: "careteam" },
      { href: "/workspace/consent", label: "Privacy & Consent", icon: "consent" },
      { href: "/workspace/settings", label: "Settings", icon: "settings" },
    ],
  },
  {
    label: "More",
    items: [
      { href: "/workspace/intelligence", label: "Intelligence & Trust", icon: "intelligence" },
    ],
  },
];

export function navGroupsForRole(role: UserRole): NavGroup[] {
  if (role === "caregiver") return caregiverGroups;
  if (role === "clinician") return clinicianGroups;
  return patientGroups;
}

export function navForRole(role: UserRole): NavItem[] {
  return navGroupsForRole(role).flatMap((group) => group.items);
}

export function workspaceHome(role: UserRole): string {
  if (role === "caregiver") return "/workspace/caregiver";
  if (role === "clinician") return "/workspace/clinician";
  return "/workspace";
}
