import type { ReactNode } from "react";
import type { Role } from "@/lib/api/types";
import { requireRole } from "@/lib/data/server";
import { DashboardShell } from "./dashboard-shell";

/**
 * Resolves the signed-in user for a dashboard section (redirecting if needed) and renders
 * the shell. Reads the session, so it must be rendered inside <Suspense>.
 */
export async function RoleGate({ role, children }: { role: Role; children: ReactNode }) {
  const user = await requireRole(role, `/dashboard/${role}`);
  return (
    <DashboardShell user={user} role={role}>
      {children}
    </DashboardShell>
  );
}
