import type { BookingStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Perspective = "student" | "mentor" | "admin";

const STYLES: Record<BookingStatus, string> = {
  pending_payment: "bg-warning-soft text-warning",
  requested: "bg-info-soft text-info",
  confirmed: "bg-success-soft text-success",
  completed: "bg-muted text-foreground",
  declined: "bg-destructive/10 text-destructive",
  cancelled: "bg-muted text-muted-foreground",
  expired: "bg-muted text-muted-foreground",
};

export function bookingStatusLabel(status: BookingStatus, perspective: Perspective): string {
  switch (status) {
    case "pending_payment":
      return "Awaiting payment";
    case "requested":
      return perspective === "mentor" ? "Needs your response" : "Awaiting mentor";
    case "confirmed":
      return "Confirmed";
    case "completed":
      return "Completed";
    case "declined":
      return "Declined";
    case "cancelled":
      return "Cancelled";
    case "expired":
      return "Expired";
  }
}

export function BookingStatusBadge({
  status,
  perspective = "student",
  className,
}: {
  status: BookingStatus;
  perspective?: Perspective;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        STYLES[status],
        className,
      )}
    >
      {bookingStatusLabel(status, perspective)}
    </span>
  );
}
