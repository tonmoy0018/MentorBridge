import type { Metadata } from "next";
import { AdminVerification } from "@/features/admin/admin-verification";

export const metadata: Metadata = { title: "Mentor verification" };

export default function Page() {
  return <AdminVerification />;
}
