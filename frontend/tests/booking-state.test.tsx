import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Booking, BookingStatus, CurrentUser } from "@/lib/api/types";
import { canUseDashboard } from "@/lib/routes";
import { bookingPermissions } from "@/components/bookings/booking-actions";
import { BookingCard } from "@/components/bookings/booking-card";

const HOUR = 3_600_000;
const NOW = Date.UTC(2026, 10, 2, 12);

function booking(status: BookingStatus, overrides: Partial<Booking> = {}): Booking {
  const start = new Date(NOW + 48 * HOUR).toISOString();
  return {
    id: "b1",
    status,
    start_at: start,
    end_at: new Date(NOW + 49 * HOUR).toISOString(),
    service_title: "Career chat",
    duration_minutes: 60,
    price: { amount_cents: 4500, currency: "USD" },
    student_note: "",
    meeting_url: status === "confirmed" ? "https://meet.example.com/x" : null,
    mentor: { id: "m1", slug: "mia", display_name: "Mia Mentor", headline: "Engineer", avatar_url: null },
    student: { id: "s1", display_name: "Jordan Lee", avatar_url: null },
    hold_expires_at: null,
    respond_by: null,
    confirmed_at: null,
    completed_at: null,
    cancelled_at: null,
    cancellation_reason: "",
    refund_outcome: "",
    has_review: false,
    created_at: new Date(NOW).toISOString(),
    ...overrides,
  };
}

describe("bookingPermissions", () => {
  it.each<BookingStatus>(["cancelled", "declined", "expired"])(
    "a %s booking never offers session actions",
    (status) => {
      expect(bookingPermissions(booking(status), "student", NOW).any).toBe(false);
      expect(bookingPermissions(booking(status), "mentor", NOW).any).toBe(false);
    },
  );

  it("lets the mentor accept or decline only open requests", () => {
    expect(bookingPermissions(booking("requested"), "mentor", NOW)).toMatchObject({ canAccept: true, canCancel: false });
    expect(bookingPermissions(booking("requested"), "student", NOW)).toMatchObject({ canAccept: false, canCancel: true });
    const startedRequest = booking("requested", { start_at: new Date(NOW - HOUR).toISOString() });
    expect(bookingPermissions(startedRequest, "mentor", NOW).canAccept).toBe(false);
  });

  it("only completes confirmed sessions that have started", () => {
    expect(bookingPermissions(booking("confirmed"), "mentor", NOW).canComplete).toBe(false);
    const started = booking("confirmed", { start_at: new Date(NOW - HOUR).toISOString() });
    expect(bookingPermissions(started, "mentor", NOW)).toMatchObject({ canComplete: true, canCancel: false });
  });

  it("offers a review once, to the student, after completion", () => {
    expect(bookingPermissions(booking("completed"), "student", NOW).canReview).toBe(true);
    expect(bookingPermissions(booking("completed", { has_review: true }), "student", NOW).canReview).toBe(false);
    expect(bookingPermissions(booking("completed"), "mentor", NOW).canReview).toBe(false);
    expect(bookingPermissions(booking("confirmed"), "student", NOW).canReview).toBe(false);
  });
});

describe("BookingCard", () => {
  it("only shows the meeting link for confirmed bookings", () => {
    const { rerender } = render(<BookingCard booking={booking("confirmed")} perspective="student" timeZone="UTC" />);
    expect(screen.getByRole("link", { name: /join meeting/i })).toHaveAttribute("href", "https://meet.example.com/x");
    rerender(
      <BookingCard
        booking={booking("cancelled", { meeting_url: "https://meet.example.com/x" })}
        perspective="student"
        timeZone="UTC"
      />,
    );
    expect(screen.queryByRole("link", { name: /join meeting/i })).not.toBeInTheDocument();
  });

  it("explains the refund outcome from the backend", () => {
    render(
      <BookingCard
        booking={booking("cancelled", { refund_outcome: "no_refund", cancellation_reason: "Clash" })}
        perspective="student"
        timeZone="UTC"
      />,
    );
    expect(screen.getByText(/no refund under the policy/i)).toBeInTheDocument();
    expect(screen.getByText("Reason: Clash")).toBeInTheDocument();
  });
});

describe("canUseDashboard", () => {
  const user = (role: CurrentUser["role"], is_admin = false): CurrentUser => ({
    id: "u",
    email: "u@example.com",
    first_name: "U",
    last_name: "S",
    role,
    timezone: "UTC",
    email_verified: true,
    is_admin,
  });

  it("matches roles, and requires backend admin permission for the admin area", () => {
    expect(canUseDashboard(user("student"), "student")).toBe(true);
    expect(canUseDashboard(user("student"), "mentor")).toBe(false);
    expect(canUseDashboard(user("admin", false), "admin")).toBe(false);
    expect(canUseDashboard(user("admin", true), "admin")).toBe(true);
  });
});
