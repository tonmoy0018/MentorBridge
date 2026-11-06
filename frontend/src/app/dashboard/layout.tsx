import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: { default: "Dashboard", template: "%s · Dashboard · MentorBridge" },
  robots: { index: false, follow: false },
};

export default function DashboardRootLayout({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
    </>
  );
}
