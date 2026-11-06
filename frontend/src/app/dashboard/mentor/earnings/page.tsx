import type { Metadata } from "next";
import { Earnings } from "@/features/mentor/earnings";

export const metadata: Metadata = { title: "Earnings" };

export default function Page() {
  return <Earnings />;
}
