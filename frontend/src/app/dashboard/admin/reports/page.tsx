import type { Metadata } from "next";
import { AdminReports } from "@/features/admin/admin-reports";

export const metadata: Metadata = { title: "Reports" };

export default function Page() {
  return <AdminReports />;
}
