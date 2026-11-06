import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Booking, BookingStatus } from "@/lib/api/types";
import { bookingPermissions } from "@/components/bookings/booking-actions";
import { CheckoutReturnNotice } from "@/components/bookings/checkout-return-notice";
import { parseRefundAmount } from "@/features/admin/admin-payments";
import { goToCheckout } from "@/lib/checkout";

const getBooking = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useSearchParams: () => search }));
vi.mock("@/lib/data/client", () => ({ api: { bookings: { get: (id: string) => getBooking(id) } } }));

const HOUR = 3_600_000;
const NOW = Date.UTC(2026, 10, 2, 12);

function booking(status: BookingStatus, overrides: Partial<Booking> = {}): Booking {
  return {
    id: "b1",
    status,
    start_at: new Date(NOW + 48 * HOUR).toISOString(),
    end_at: new Date(NOW + 49 * HOUR).toISOString(),
    service_title: "Career chat",
    duration_minutes: 60,
    price: { amount_cents: 4000, currency: "USD" },
    student_note: "",
    meeting_url: null,
    mentor: { id: "m1", slug: "mia", display_name: "Mia Mentor", headline: "Engineer", avatar_url: null },
    student: { id: "s1", display_name: "Jordan Lee", avatar_url: null },
    hold_expires_at: new Date(NOW + HOUR / 2).toISOString(),
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

describe("Pay now", () => {
  it("is offered to the student while the slot is held", () => {
    expect(bookingPermissions(booking("pending_payment"), "student", NOW).canPay).toBe(true);
  });
  it("is not offered to the mentor, after the hold lapses, or once paid", () => {
    expect(bookingPermissions(booking("pending_payment"), "mentor", NOW).canPay).toBe(false);
    expect(bookingPermissions(booking("pending_payment"), "student", NOW + HOUR).canPay).toBe(false);
    expect(bookingPermissions(booking("requested"), "student", NOW).canPay).toBe(false);
  });
});

describe("parseRefundAmount", () => {
  it("converts major units to cents within the refundable amount", () => {
    expect(parseRefundAmount("", 4000)).toBeUndefined(); // full remaining amount
    expect(parseRefundAmount("12.5", 4000)).toBe(1250);
    expect(parseRefundAmount("40", 4000)).toBe(4000);
  });
  it.each(["40.01", "0", "-1", "1.234", "abc"])("rejects %s", (value) => {
    expect(parseRefundAmount(value, 4000)).toBeNull();
  });
});

describe("goToCheckout", () => {
  it("refuses anything that isn't https", () => {
    expect(() => goToCheckout("javascript:alert(1)")).toThrow();
    expect(() => goToCheckout("http://checkout.example.com")).toThrow();
    expect(() => goToCheckout("not a url")).toThrow();
  });
});

describe("CheckoutReturnNotice", () => {
  beforeEach(() => getBooking.mockReset());
  afterEach(() => {
    search = new URLSearchParams();
  });

  it("renders nothing without a checkout return", () => {
    const { container } = render(<CheckoutReturnNotice onSettled={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("reports success only from the booking status the backend returns", async () => {
    search = new URLSearchParams("checkout=b1");
    getBooking.mockResolvedValue(booking("requested"));
    const settled = vi.fn();
    render(<CheckoutReturnNotice onSettled={settled} timeZone="UTC" />);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Payment authorised"));
    expect(getBooking).toHaveBeenCalledWith("b1");
    expect(settled).toHaveBeenCalled();
  });

  it("a cancelled checkout says payment wasn't completed", async () => {
    search = new URLSearchParams("checkout=b1&cancelled=1");
    getBooking.mockResolvedValue(booking("pending_payment"));
    render(<CheckoutReturnNotice onSettled={() => {}} timeZone="UTC" />);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Payment wasn't completed"));
  });

  it("keeps checking while the provider hasn't confirmed, without claiming payment", async () => {
    search = new URLSearchParams("checkout=b1");
    getBooking.mockResolvedValue(booking("pending_payment"));
    render(<CheckoutReturnNotice onSettled={() => {}} timeZone="UTC" />);
    await waitFor(() => expect(getBooking).toHaveBeenCalled());
    expect(screen.getByRole("status")).toHaveTextContent("Checking your payment");
    expect(screen.getByRole("status")).not.toHaveTextContent(/authorised|received/);
  });
});
