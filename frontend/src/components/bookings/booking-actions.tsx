"use client";

import { CreditCard, Link2, MapPin, Star } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";
import { getErrorMessage, isApiError } from "@/lib/api/errors";
import type { Booking, BookingStatus } from "@/lib/api/types";
import { goToCheckout } from "@/lib/checkout";
import { api } from "@/lib/data/client";
import { useReloadOnBack } from "@/hooks/use-reload-on-back";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog as DialogRoot, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";

type Dialog = "cancel" | "accept" | "decline" | "complete" | "review" | "place" | "link" | null;

/** Statuses that hold a time slot. Anything else is closed and offers no session actions. */
export const ACTIVE_STATUSES: ReadonlySet<BookingStatus> = new Set(["pending_payment", "requested", "confirmed"]);

/**
 * Which actions apply to this booking for this viewer. Derived only from the backend status
 * (and start time), mirroring the API's rules, so a cancelled, declined or expired booking can
 * never offer confirmed-session actions. The API enforces the same rules.
 */
export function bookingPermissions(booking: Booking, perspective: "student" | "mentor", now = Date.now()) {
  const started = new Date(booking.start_at).getTime() <= now;
  const isMentor = perspective === "mentor";
  const canAccept = isMentor && booking.status === "requested" && !started;
  const canComplete = isMentor && booking.status === "confirmed" && started;
  const canCancel =
    ACTIVE_STATUSES.has(booking.status) && !started && !(isMentor && booking.status === "requested");
  const canReview = !isMentor && booking.status === "completed" && !booking.has_review;
  const holdLive = !booking.hold_expires_at || new Date(booking.hold_expires_at).getTime() > now;
  const canPay = !isMentor && booking.status === "pending_payment" && holdLive && !started;
  const canSetPlace =
    isMentor && booking.format === "in_person" && booking.status === "confirmed" && !started;
  const canSetLink =
    isMentor && booking.format === "online" && !booking.seminar && booking.status === "confirmed" && !started;
  return {
    canAccept,
    canComplete,
    canCancel,
    canReview,
    canPay,
    canSetPlace,
    canSetLink,
    any: canAccept || canComplete || canCancel || canReview || canPay || canSetPlace || canSetLink,
  };
}

/**
 * The actions a student or mentor may take on a booking. Each action runs in a dialog that
 * disables itself while the request is in flight (no double submissions). If the booking changed
 * elsewhere (409/404), `onStale` refreshes the list so outdated buttons disappear.
 */
export function BookingActions({
  booking,
  perspective,
  onUpdated,
  onStale,
}: {
  booking: Booking;
  perspective: "student" | "mentor";
  onUpdated: (booking: Booking) => void;
  onStale?: () => void;
}) {
  const [dialog, setDialog] = useState<Dialog>(null);
  const [opening, setOpening] = useState(false);
  useReloadOnBack();
  const isMentor = perspective === "mentor";
  const { canAccept, canComplete, canCancel, canReview, canPay, canSetPlace, canSetLink, any } = bookingPermissions(
    booking,
    perspective,
  );
  const inPerson = booking.format === "in_person";

  if (!any) return null;

  async function pay() {
    setOpening(true);
    try {
      const checkout = await api.bookings.checkout(booking.id);
      goToCheckout(checkout.checkout_url); // the page navigates away; keep the button disabled
    } catch (error) {
      setOpening(false);
      if (isApiError(error) && (error.kind === "conflict" || error.kind === "not_found")) onStale?.();
      toast.error("Couldn't open the payment page", { description: getErrorMessage(error) });
    }
  }

  const run = (action: () => Promise<Booking>, message: string) => async () => {
    try {
      const updated = await action();
      onUpdated(updated);
      toast.success(message);
    } catch (error) {
      if (isApiError(error) && (error.kind === "conflict" || error.kind === "not_found")) onStale?.();
      throw error; // shown inside the dialog
    }
  };

  const close = (open: boolean) => !open && setDialog(null);

  return (
    <>
      {canPay ? (
        <Button size="sm" onClick={pay} disabled={opening} aria-busy={opening}>
          <CreditCard aria-hidden="true" />
          {opening ? "Opening payment page…" : "Pay now"}
        </Button>
      ) : null}
      {canAccept ? (
        <>
          <Button size="sm" onClick={() => setDialog("accept")}>
            Accept
          </Button>
          <Button size="sm" variant="outline" onClick={() => setDialog("decline")}>
            Decline
          </Button>
        </>
      ) : null}
      {canComplete ? (
        <Button size="sm" variant="outline" onClick={() => setDialog("complete")}>
          Mark as completed
        </Button>
      ) : null}
      {canSetLink ? (
        <Button size="sm" variant="outline" onClick={() => setDialog("link")}>
          <Link2 aria-hidden="true" />
          Change meeting link
        </Button>
      ) : null}
      {canSetPlace ? (
        <Button size="sm" variant={booking.meeting_place ? "outline" : "default"} onClick={() => setDialog("place")}>
          <MapPin aria-hidden="true" />
          {booking.meeting_place ? "Change meeting place" : "Add meeting place"}
        </Button>
      ) : null}
      {canReview ? (
        <Button size="sm" onClick={() => setDialog("review")}>
          <Star aria-hidden="true" />
          Leave a review
        </Button>
      ) : null}
      {canCancel ? (
        <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDialog("cancel")}>
          Cancel booking
        </Button>
      ) : null}

      <ConfirmationDialog
        open={dialog === "accept"}
        onOpenChange={close}
        title="Accept this request?"
        description={
          inPerson
            ? `${booking.student.display_name} will be notified and the session will be confirmed. Tell them where to meet in ${booking.in_person_area}: somewhere public, never your home.`
            : `${booking.student.display_name} will be notified and the session will be confirmed.`
        }
        confirmLabel="Accept request"
        reason={
          inPerson
            ? { label: "Meeting place", placeholder: "e.g. Café name, street, and how to find you" }
            : {
                label: "Meeting link for this session (optional)",
                placeholder: "https://… (leave empty to use your default link)",
              }
        }
        onConfirm={(detail) =>
          run(
            () =>
              api.bookings.accept(booking.id, inPerson ? { meetingPlace: detail } : { meetingUrl: detail }),
            "Booking confirmed",
          )()
        }
      />
      <ConfirmationDialog
        open={dialog === "link"}
        onOpenChange={close}
        title="Change the meeting link?"
        description={`Use any video tool you and ${booking.student.display_name} agree on (Zoom, Google Meet, Teams…). They'll see the new link on their booking.`}
        confirmLabel="Save link"
        reason={{ label: "Meeting link", placeholder: "https://…", required: true }}
        onConfirm={(url) => run(() => api.bookings.setMeetingLink(booking.id, url), "Meeting link saved")()}
      />
      <ConfirmationDialog
        open={dialog === "place"}
        onOpenChange={close}
        title="Where will you meet?"
        description={`Only ${booking.student.display_name} sees this, once the session is confirmed. Choose somewhere public in ${booking.in_person_area}.`}
        confirmLabel="Save meeting place"
        reason={{
          label: "Meeting place",
          placeholder: "e.g. Café name, street, and how to find you",
          required: true,
        }}
        onConfirm={(place) => run(() => api.bookings.setMeetingPlace(booking.id, place), "Meeting place saved")()}
      />
      <ConfirmationDialog
        open={dialog === "decline"}
        onOpenChange={close}
        title="Decline this request?"
        description="The student will be notified and won't be charged."
        confirmLabel="Decline request"
        destructive
        reason={{ label: "Message to the student", placeholder: "Let them know why, and suggest an alternative if you can.", required: true }}
        onConfirm={(reason) => run(() => api.bookings.decline(booking.id, reason), "Request declined")()}
      />
      <ConfirmationDialog
        open={dialog === "complete"}
        onOpenChange={close}
        title="Mark this session as completed?"
        description="The student will be able to leave a review."
        confirmLabel="Mark completed"
        onConfirm={run(() => api.bookings.complete(booking.id), "Session marked as completed")}
      />
      <ConfirmationDialog
        open={dialog === "cancel"}
        onOpenChange={close}
        title="Cancel this booking?"
        description={cancelDescription(booking, isMentor)}
        confirmLabel="Cancel booking"
        cancelLabel="Keep booking"
        destructive
        reason={{ label: "Reason", required: isMentor }}
        onConfirm={(reason) => run(() => api.bookings.cancel(booking.id, reason), "Booking cancelled")()}
      />
      <ReviewDialog
        open={dialog === "review"}
        onOpenChange={close}
        booking={booking}
        onReviewed={() => onUpdated({ ...booking, has_review: true })}
        onStale={onStale}
      />
    </>
  );
}

function cancelDescription(booking: Booking, isMentor: boolean): string {
  if (isMentor) {
    return booking.package
      ? "The student will be notified and the session goes back to their package."
      : "The student will be notified. Any payment is refunded in full.";
  }
  if (booking.package) {
    return booking.status === "confirmed"
      ? "Cancel at least 24 hours before the session and it goes back to your package. Later than that, it counts as used."
      : "The mentor will be notified and the session goes back to your package.";
  }
  if (booking.price.amount_cents === 0) return "The mentor will be notified.";
  if (booking.status === "pending_payment") return "The held time is released. You won't be charged.";
  if (booking.status !== "confirmed")
    return "The mentor will be notified. Your card authorisation is released, so you won't be charged.";
  return "Refunds follow the cancellation policy: a full refund up to 24 hours before the session, none after.";
}

function ReviewDialog({
  open,
  onOpenChange,
  booking,
  onReviewed,
  onStale,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  booking: Booking;
  onReviewed: () => void;
  onStale?: () => void;
}) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const commentId = useId();

  function handleOpenChange(next: boolean) {
    if (pending) return;
    if (!next) {
      setRating(0);
      setComment("");
      setError(null);
    }
    onOpenChange(next);
  }

  async function submit() {
    if (rating < 1) {
      setError("Choose a rating from 1 to 5 stars.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await api.bookings.review(booking.id, { rating, comment: comment.trim() });
      toast.success("Thanks for your review");
      onReviewed();
      handleOpenChange(false);
    } catch (err) {
      if (isApiError(err) && err.code === "already_exists") {
        onReviewed();
        onStale?.();
      }
      setError(getErrorMessage(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <DialogRoot open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Review your session</DialogTitle>
          <DialogDescription>
            {booking.service_title} with {booking.mentor.display_name}. Your review is shown on their profile with
            your first name and last initial.
          </DialogDescription>
        </DialogHeader>
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Rating</legend>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((value) => (
              <label key={value} className="cursor-pointer">
                <input
                  type="radio"
                  name={`rating-${booking.id}`}
                  value={value}
                  checked={rating === value}
                  onChange={() => setRating(value)}
                  className="peer sr-only"
                />
                <Star
                  aria-hidden="true"
                  className={cn(
                    "size-8 rounded-sm peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50",
                    value <= rating ? "fill-rating text-rating" : "text-border",
                  )}
                />
                <span className="sr-only">
                  {value} star{value === 1 ? "" : "s"}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-2">
          <Label htmlFor={commentId}>
            Comment <span className="font-normal text-muted-foreground">(optional)</span>
          </Label>
          <Textarea
            id={commentId}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
            placeholder="What was most useful? Would you recommend this mentor?"
          />
        </div>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={pending} aria-busy={pending}>
            {pending ? "Submitting…" : "Submit review"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  );
}
