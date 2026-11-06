import { CalendarDays, Clock, ExternalLink, MessageSquareText } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import type { Booking, RefundOutcome } from "@/lib/api/types";
import { formatDate, formatDuration, formatMoney, formatTime, timeZoneLabel } from "@/lib/format";
import { ROUTES } from "@/lib/routes";
import { cn } from "@/lib/utils";
import { MentorAvatar } from "@/components/mentors/mentor-avatar";
import { BookingStatusBadge } from "./booking-status-badge";

const REFUND_TEXT: Record<Exclude<RefundOutcome, "">, string> = {
  not_charged: "Cancelled before payment was taken: no charge.",
  full_refund: "A full refund is due under the cancellation policy.",
  no_refund: "Cancelled less than 24 hours before the session: no refund under the policy.",
};

/**
 * One booking, from the student's or mentor's point of view. Times are shown in
 * `timeZone` (the viewer's profile timezone). Render only in Client Components after
 * data has loaded, so server and browser never format the same time differently.
 */
export function BookingCard({
  booking,
  perspective,
  timeZone,
  actions,
  className,
}: {
  booking: Booking;
  perspective: "student" | "mentor";
  timeZone?: string;
  actions?: ReactNode;
  className?: string;
}) {
  const counterpart = perspective === "student" ? booking.mentor : booking.student;
  const zone = timeZoneLabel(timeZone, new Date(booking.start_at));

  return (
    <article className={cn("rounded-xl border bg-card p-5", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <MentorAvatar name={counterpart.display_name} src={counterpart.avatar_url} size="md" />
          <div className="min-w-0">
            <h3 className="font-semibold">{booking.service_title}</h3>
            <p className="truncate text-sm text-muted-foreground">
              {perspective === "student" ? (
                <>
                  with{" "}
                  <Link href={ROUTES.mentor(booking.mentor.slug)} className="underline-offset-4 hover:underline">
                    {booking.mentor.display_name}
                  </Link>
                </>
              ) : (
                <>with {booking.student.display_name}</>
              )}
            </p>
          </div>
        </div>
        <BookingStatusBadge status={booking.status} perspective={perspective} />
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
        <div className="flex items-center gap-2">
          <dt>
            <CalendarDays className="size-4 text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">Date</span>
          </dt>
          <dd>{formatDate(booking.start_at, timeZone)}</dd>
        </div>
        <div className="flex items-center gap-2">
          <dt>
            <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">Time</span>
          </dt>
          <dd>
            {formatTime(booking.start_at, timeZone)} {zone} · {formatDuration(booking.duration_minutes)}
          </dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="sr-only">Price</dt>
          <dd className="font-medium">{formatMoney(booking.price)}</dd>
        </div>
      </dl>

      {booking.student_note ? (
        <p className="mt-4 flex gap-2 rounded-lg bg-muted/60 p-3 text-sm">
          <MessageSquareText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span>
            <span className="sr-only">Note from student: </span>
            {booking.student_note}
          </span>
        </p>
      ) : null}

      {booking.status === "pending_payment" && booking.hold_expires_at ? (
        <p className="mt-3 text-sm text-warning">
          This time is held until {formatTime(booking.hold_expires_at, timeZone)} while payment is completed. If
          payment isn&apos;t confirmed by then, the hold expires.
        </p>
      ) : null}
      {booking.status === "confirmed" && !booking.meeting_url ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {perspective === "mentor"
            ? "Add a default meeting link in your profile so the student can join."
            : "Your mentor hasn't added a meeting link yet. It will appear here."}
        </p>
      ) : null}
      {booking.status === "expired" ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {booking.respond_by || !booking.hold_expires_at
            ? "This request expired before the mentor responded. You weren't charged."
            : "The payment hold expired, so this time was released."}
        </p>
      ) : null}
      {booking.status === "cancelled" && booking.refund_outcome ? (
        <p className="mt-3 text-sm text-muted-foreground">{REFUND_TEXT[booking.refund_outcome]}</p>
      ) : null}
      {booking.status === "completed" && booking.has_review && perspective === "student" ? (
        <p className="mt-3 text-sm text-muted-foreground">You reviewed this session. Thank you!</p>
      ) : null}
      {booking.status === "requested" && booking.respond_by ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {perspective === "mentor" ? "Please respond by " : "The mentor will respond by "}
          {formatDate(booking.respond_by, timeZone)}, {formatTime(booking.respond_by, timeZone)}.
        </p>
      ) : null}
      {booking.cancellation_reason && (booking.status === "cancelled" || booking.status === "declined") ? (
        <p className="mt-3 text-sm text-muted-foreground">Reason: {booking.cancellation_reason}</p>
      ) : null}

      {(booking.status === "confirmed" && booking.meeting_url) || actions ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t pt-4">
          {booking.status === "confirmed" && booking.meeting_url ? (
            <a
              href={booking.meeting_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/85"
            >
              Join meeting
              <ExternalLink className="size-3.5" aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          ) : null}
          {actions}
        </div>
      ) : null}
    </article>
  );
}
