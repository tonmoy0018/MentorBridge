"use client";

import { CalendarX2, MapPin, Users, Video } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useId, useState } from "react";
import { toast } from "sonner";
import type { Seminar } from "@/lib/api/types";
import { getErrorMessage, isApiError } from "@/lib/api/errors";
import { goToCheckout } from "@/lib/checkout";
import { api } from "@/lib/data/client";
import { formatDate, formatDuration, formatMoney, formatTime, pluralize, timeZoneLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { loginRedirectPath } from "@/hooks/use-api-error-handler";

/**
 * Pick one of a service's upcoming group seminars and register for a seat. Free seats are
 * confirmed at once; paid seats go to the provider's checkout and are confirmed only when the
 * backend has verified the payment.
 */
export function SeminarPicker({
  seminars,
  mentorFirstName,
  initialSeminarId,
  paymentsEnabled,
  paymentsLivemode,
  freeCancellationHours,
}: {
  seminars: Seminar[];
  mentorFirstName: string;
  initialSeminarId?: string;
  paymentsEnabled: boolean;
  paymentsLivemode: boolean;
  freeCancellationHours: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const name = useId();
  const open = seminars.filter((s) => s.seats_left > 0);
  const [selectedId, setSelectedId] = useState(
    open.some((s) => s.id === initialSeminarId) ? initialSeminarId! : (open[0]?.id ?? ""),
  );
  const [confirmOpen, setConfirmOpen] = useState(false);
  const seminar = seminars.find((s) => s.id === selectedId);
  const paid = Boolean(seminar && seminar.price.amount_cents > 0);
  const paymentBlocked = paid && !paymentsEnabled;
  const zone = timeZoneLabel(undefined);

  if (seminars.length === 0) {
    return <EmptyState icon={CalendarX2} title="No upcoming seminars" description="Check back soon." />;
  }

  async function submit() {
    if (!seminar) return;
    let booking;
    try {
      booking = await api.student.registerSeminar(seminar.id);
    } catch (error) {
      if (isApiError(error) && error.kind === "unauthenticated") {
        router.push(loginRedirectPath(pathname));
        return;
      }
      if (isApiError(error) && error.kind === "forbidden" && error.code === "permission_denied") {
        throw new Error("Only student accounts can register for seminars.");
      }
      if (isApiError(error) && error.kind === "conflict") router.refresh(); // update seats left
      throw error;
    }
    if (booking.status === "pending_payment") {
      try {
        const checkout = await api.bookings.checkout(booking.id);
        goToCheckout(checkout.checkout_url);
        await new Promise(() => {}); // keep the dialog busy while the browser leaves
      } catch (error) {
        toast.error("Your seat is held, but the payment page didn't open", {
          description: `${getErrorMessage(error)} Use “Pay now” in your bookings to try again.`,
        });
        router.push("/dashboard/student/bookings");
      }
      return;
    }
    toast.success("You're registered", { description: "Your seat is confirmed. It's in your bookings." });
    router.push("/dashboard/student/bookings");
  }

  return (
    <div className="grid min-w-0 gap-5">
      <fieldset className="grid min-w-0 gap-2">
        <legend className="mb-2 text-sm font-medium">
          Upcoming seminars <span className="font-normal text-muted-foreground">({zone}, your time zone)</span>
        </legend>
        {seminars.map((s) => {
          const full = s.seats_left === 0;
          return (
            <label
              key={s.id}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3 text-sm",
                full ? "opacity-60" : "cursor-pointer hover:border-primary/50",
                s.id === selectedId ? "border-primary bg-primary/5" : "bg-card",
              )}
            >
              <input
                type="radio"
                name={name}
                value={s.id}
                checked={s.id === selectedId}
                disabled={full}
                onChange={() => setSelectedId(s.id)}
                className="mt-0.5 size-4 accent-primary"
              />
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{s.title}</span>
                <span className="block">
                  {formatDate(s.start_at)}, {formatTime(s.start_at)} · {formatDuration(s.duration_minutes)}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
                  <span className="flex items-center gap-1">
                    {s.format === "in_person" ? (
                      <MapPin className="size-3.5" aria-hidden="true" />
                    ) : (
                      <Video className="size-3.5" aria-hidden="true" />
                    )}
                    {s.format === "in_person" ? s.in_person_area : "Online"}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="size-3.5" aria-hidden="true" />
                    {full ? "Full" : `${pluralize(s.seats_left, "seat")} left`}
                  </span>
                </span>
              </span>
              <span className="font-medium whitespace-nowrap">
                {formatMoney(s.price)}
                {s.price.amount_cents > 0 ? <span className="block text-xs font-normal text-muted-foreground">per seat</span> : null}
              </span>
            </label>
          );
        })}
      </fieldset>

      {seminar?.description ? <p className="text-sm text-muted-foreground">{seminar.description}</p> : null}

      {paymentBlocked ? (
        <p role="note" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
          Online payment isn&apos;t available yet, so paid seminars can&apos;t be booked. Please check back soon.
        </p>
      ) : null}

      <Button size="lg" disabled={!seminar || seminar.seats_left === 0 || paymentBlocked} onClick={() => setConfirmOpen(true)}>
        {paid && !paymentBlocked ? "Register and pay" : "Register"}
      </Button>

      {seminar ? (
        <ConfirmationDialog
          open={confirmOpen}
          onOpenChange={setConfirmOpen}
          title={paid ? "Continue to payment?" : "Register for this seminar?"}
          description={
            paid
              ? `You'll pay on our payment provider's secure page; your seat is confirmed once payment goes through. Cancel at least ${freeCancellationHours} hours before for a full refund. If ${mentorFirstName} cancels the seminar, you're refunded in full.`
              : `Your seat is confirmed straight away. You can cancel any time before the seminar starts.`
          }
          confirmLabel={paid ? "Continue to payment" : "Register"}
          onConfirm={submit}
        >
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg bg-muted/60 p-4 text-sm">
            <dt className="text-muted-foreground">Seminar</dt>
            <dd>{seminar.title}</dd>
            <dt className="text-muted-foreground">When</dt>
            <dd>
              {formatDate(seminar.start_at)}, {formatTime(seminar.start_at)} {zone}
            </dd>
            <dt className="text-muted-foreground">Length</dt>
            <dd>{formatDuration(seminar.duration_minutes)}</dd>
            <dt className="text-muted-foreground">Where</dt>
            <dd>{seminar.format === "in_person" ? `In person · ${seminar.in_person_area}` : "Online"}</dd>
            <dt className="text-muted-foreground">Price</dt>
            <dd className="font-medium">{formatMoney(seminar.price)}</dd>
          </dl>
          {seminar.format === "in_person" ? (
            <p className="text-sm text-muted-foreground">
              The exact meeting place appears in your bookings once your seat is confirmed.
            </p>
          ) : null}
          {paid && !paymentsLivemode ? (
            <p role="note" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
              Test mode: payments run in the provider&apos;s sandbox. Use a test card; no real money is taken.
            </p>
          ) : null}
        </ConfirmationDialog>
      ) : null}
    </div>
  );
}
