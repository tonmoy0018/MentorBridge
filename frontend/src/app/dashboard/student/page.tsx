import type { Metadata } from "next";
import { StudentOverview } from "@/features/student/student-overview";

export const metadata: Metadata = { title: "Overview" };

export default function StudentDashboardPage() {
  return <StudentOverview />;
}
