import type { Metadata } from "next";
import { MentorOverview } from "@/features/mentor/mentor-overview";

export const metadata: Metadata = { title: "Overview" };

export default function Page() {
  return <MentorOverview />;
}
