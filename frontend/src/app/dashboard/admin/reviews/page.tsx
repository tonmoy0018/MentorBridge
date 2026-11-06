import type { Metadata } from "next";
import { AdminReviews } from "@/features/admin/admin-reviews";

export const metadata: Metadata = { title: "Reviews" };

export default function Page() {
  return <AdminReviews />;
}
