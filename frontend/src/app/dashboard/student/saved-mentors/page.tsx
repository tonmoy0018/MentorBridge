import type { Metadata } from "next";
import { SavedMentors } from "@/features/student/saved-mentors";

export const metadata: Metadata = { title: "Saved mentors" };

export default function SavedMentorsPage() {
  return <SavedMentors />;
}
