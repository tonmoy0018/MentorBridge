import type { Metadata } from "next";
import { Goals } from "@/features/student/goals";

export const metadata: Metadata = { title: "Career goals" };

export default function GoalsPage() {
  return <Goals />;
}
