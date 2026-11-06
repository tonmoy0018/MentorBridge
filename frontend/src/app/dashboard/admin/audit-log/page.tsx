import type { Metadata } from "next";
import { AdminAuditLog } from "@/features/admin/admin-audit-log";

export const metadata: Metadata = { title: "Audit log" };

export default function Page() {
  return <AdminAuditLog />;
}
