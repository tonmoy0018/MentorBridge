"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { isApiError } from "@/lib/api/errors";
import type { Booking } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { loginRedirectPath } from "@/hooks/use-api-error-handler";

const POLL_MS = 2_000;
const MAX_POLLS = 15;

type State = { phase: "checking" } | { phase: "done"; booking: Booking } | { phase: "waiting"; booking?: Booking };

/**
 * Shown when the student comes back from the provider's checkout (`?checkout=<booking id>`).
 * The return itself proves nothing: this only re-reads the booking, whose status changes solely
 * when the backend has verified the provider's signed notification.
 */
export function CheckoutReturnNotice({ onSettled, timeZone }: { onSettled: () => void; timeZone?: string }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const bookingId = params.get("checkout");
  const cancelled = params.get("cancelled") === "1";
  const [state, setState] = useState<State>({ phase: "checking" });

  useEffect(() => {
    if (!bookingId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let polls = 0;

    const check = async () => {
      polls += 1;
      let booking: Booking | undefined;
      try {
        booking = await api.bookings.get(bookingId);
      } catch (error) {
        if (isApiError(error) && error.kind === "unauthenticated") {
          router.replace(loginRedirectPath(`${pathname}?${params.toString()}`, "expired"));
          return;
        }
        booking = undefined;
      }
      if (stopped) return;
      if (booking && (cancelled || booking.status !== "pending_payment")) {
        setState({ phase: "done", booking });
        if (booking.status !== "pending_payment") onSettled();
        return;
      }
      if (polls >= MAX_POLLS) {
        setState({ phase: "waiting", booking });
        return;
      }
      timer = setTimeout(check, POLL_MS);
    };
    void check();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
    // `onSettled` is a stable reload callback; re-polling only depends on the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId, cancelled]);

  if (!bookingId) return null;

  const { tone, text } = describe(state, cancelled, timeZone);
  return (
    <p
      role="status"
      className={cn(
        "rounded-lg p-4 text-sm",
        tone === "success" && "bg-success-soft text-success",
        tone === "info" && "bg-info-soft text-info",
        tone === "warning" && "bg-warning-soft text-warning",
      )}
    >
      {text}
    </p>
  );
}

function describe(state: State, cancelled: boolean, timeZone?: string): { tone: "success" | "info" | "warning"; text: string } {
  if (state.phase === "checking") {
    return { tone: "info", text: "Checking your payment with the payment provider…" };
  }
  const booking = state.booking;
  if (booking?.status === "requested") {
    return {
      tone: "success",
      text: `Payment authorised. Your request was sent to ${booking.mentor.display_name}. Your card is only charged if they accept.`,
    };
  }
  if (booking?.status === "confirmed") {
    return { tone: "success", text: "Payment received. Your session is confirmed." };
  }
  if (booking && booking.status !== "pending_payment") {
    return {
      tone: "warning",
      text: "This booking is no longer active. If your card was authorised, the authorisation is released automatically.",
    };
  }
  const heldUntil = booking?.hold_expires_at ? ` Your time is held until ${formatTime(booking.hold_expires_at, timeZone)}.` : "";
  if (cancelled) {
    return { tone: "info", text: `Payment wasn't completed.${heldUntil} You can pay from the booking below.` };
  }
  return {
    tone: "warning",
    text: `We haven't received confirmation from the payment provider yet.${heldUntil} Nothing is marked as paid until the provider confirms. Refresh this page in a minute to check again.`,
  };
}
