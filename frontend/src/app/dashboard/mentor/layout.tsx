import type { ReactNode } from "react";
import { Suspense } from "react";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";
import { RoleGate } from "@/components/dashboard/role-gate";

export default function MentorDashboardLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <RoleGate role="mentor">{children}</RoleGate>
    </Suspense>
  );
}
