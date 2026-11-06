import type { Metadata } from "next";
import { AdminNotifications } from "@/features/admin/admin-notifications";

export const metadata: Metadata = { title: "Email delivery" };

export default function Page() {
  return <AdminNotifications />;
}
