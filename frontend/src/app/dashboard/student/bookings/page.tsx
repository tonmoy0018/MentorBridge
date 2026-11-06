import type { Metadata } from "next";
import { BookingsBoard } from "@/components/bookings/bookings-board";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Bookings" };

export default function StudentBookingsPage() {
  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader title="Bookings" description="Your upcoming, past and cancelled sessions." />
      <BookingsBoard perspective="student" />
    </div>
  );
}
