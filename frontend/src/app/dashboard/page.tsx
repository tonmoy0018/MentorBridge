import { redirect } from "next/navigation";
import { Suspense } from "react";
import { getCurrentUser } from "@/lib/data/server";
import { dashboardPathFor } from "@/lib/routes";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";

/** Sends each user to their own dashboard, based on the role Django reports. */
export default function DashboardIndexPage() {
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <DashboardRedirect />
    </Suspense>
  );
}

async function DashboardRedirect(): Promise<never> {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=%2Fdashboard");
  if (user.role === "admin" && !user.is_admin) redirect("/");
  redirect(dashboardPathFor(user.role));
}
