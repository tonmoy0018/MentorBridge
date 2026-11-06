import type { Metadata } from "next";
import { AdminBookings } from "@/features/admin/admin-bookings";

export const metadata: Metadata = { title: "Bookings" };

export default function Page() {
  return <AdminBookings />;
}
