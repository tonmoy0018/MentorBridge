import type { Metadata } from "next";
import { AccountSettings } from "@/features/account/account-settings";

export const metadata: Metadata = { title: "Settings" };

export default function StudentSettingsPage() {
  return <AccountSettings />;
}
