import type { Metadata } from "next";
import { MyPackages } from "@/features/student/my-packages";

export const metadata: Metadata = { title: "Packages" };

export default function PackagesPage() {
  return <MyPackages />;
}
