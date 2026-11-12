import type { Metadata, Viewport } from "next";
import "./globals.css";
import { SessionProvider } from "@/lib/session";

export const metadata: Metadata = {
  title: {
    default: "CareTwin AI — Recovery intelligence, evidence-linked",
    template: "%s · CareTwin AI",
  },
  description:
    "An evidence-linked Recovery Digital Twin with deterministic safety controls, role-scoped care coordination, and a provider-independent AI boundary.",
  applicationName: "CareTwin AI",
};

export const viewport: Viewport = {
  themeColor: "#F8FAFC",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
