import type { Metadata } from "next";
import { ServicesManager } from "@/features/mentor/services-manager";

export const metadata: Metadata = { title: "Services" };

export default function Page() {
  return <ServicesManager />;
}
