import type { Metadata } from "next";
import { MentorProfileEditor } from "@/features/mentor/mentor-profile-editor";

export const metadata: Metadata = { title: "Profile" };

export default function Page() {
  return <MentorProfileEditor />;
}
