"use client";

import { CalendarX2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useId, useMemo, useState } from "react";
import { toast } from "sonner";
import type { MentorPackage, MentorService, Seminar, SessionFormat } from "@/lib/api/types";
import { getErrorMessage, isApiError } from "@/lib/api/errors";
import { goToCheckout } from "@/lib/checkout";
import { api } from "@/lib/data/client";
import { formatDate, formatDuration, formatMoney, formatTime, pluralize, timeZoneLabel } from "@/lib/format";
import { FORMAT_LABEL, serviceFormats, sessionPrice } from "@/lib/sessions";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { NativeSelect } from "@/components/forms/native-select";
import { loginRedirectPath } from "@/hooks/use-api-error-handler";
import { useApiQuery } from "@/hooks/use-api-query";
import { useReloadOnBack } from "@/hooks/use-reload-on-back";
import { BundleCheckout } from "./bundle-checkout";
import { SeminarPicker } from "./seminar-picker";

const LOOKAHEAD_DAYS = 21;

/** YYYY-MM-DD for an instant in the browser's timezone (en-CA formats as ISO dates). */
const localDayKey = (iso: string) =>
  new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));

function utcDate(offsetDays: number) {
  return new Date(Date.now() + offsetDays * 86_400_000).toISOString().slice(0, 10);
}

/**
 * Service → day → time picker for booking a session. Slots come from the API as UTC
 * instants and are shown in the visitor's timezone. The server re-validates the slot.
 */
export function BookingWidget({
  mentorId,
  mentorUuid,
  mentorFirstName,
  services,
  initialServiceId,
  initialPackageId,
  seminars = [],
  initialSeminarId,
  packages = [],
  paymentsEnabled,
  paymentsLivemode,
  freeCancellationHours,
}: {
  mentorId: string;
  /** The mentor's UUID, to find the student's packages with them. */
  mentorUuid: string;
  mentorFirstName: string;
  services: MentorService[];
  initialServiceId?: string;
  /** Preselect one of the student's packages (e.g. right after getting it). */
  initialPackageId?: string;
  /** The mentor's upcoming group seminars; a service with any offers "Group seminar". */
  seminars?: Seminar[];
  initialSeminarId?: string;
  /** Multi-session options; a service with any offers "1 session" or "N sessions". */
  packages?: MentorPackage[];
  /** From GET /config/. While false, the API refuses paid bookings, so the UI does too. */
  paymentsEnabled: boolean;
  /** False while the provider runs in sandbox mode (no real money moves). */
  paymentsLivemode: boolean;
  freeCancellationHours: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const selectId = useId();
  useReloadOnBack();
  const isBookable = (s: MentorService) =>
    paymentsEnabled || serviceFormats(s).some((f) => sessionPrice(s, f).amount_cents === 0);
  const initialSeminar = seminars.find((s) => s.id === initialSeminarId);
  const [serviceId, setServiceId] = useState(
    initialSeminar && services.some((s) => s.id === initialSeminar.service.id)
      ? initialSeminar.service.id
      : services.some((s) => s.id === initialServiceId)
        ? initialServiceId!
        : (services.find(isBookable)?.id ?? services[0]?.id ?? ""),
  );
  const [mode, setMode] = useState<"one" | "group">(initialSeminar ? "group" : "one");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  // Set when the chosen time was taken by someone else; cleared when the dialog closes.
  const [slotTaken, setSlotTaken] = useState(false);

  const [formatChoice, setFormatChoice] = useState<SessionFormat>("online");
  const [packageId, setPackageId] = useState(initialPackageId ?? "");

  // The student's packages with this mentor that still have sessions. Signed-out visitors and
  // non-students simply have none.
  const purchases = useApiQuery(`packages:${mentorUuid}`, () => api.student.packages(mentorUuid).catch(() => []));
  const usablePackages = (purchases.data ?? []).filter(
    (p) => p.status === "active" && !p.is_expired && p.sessions_remaining > 0,
  );
  const [bundleId, setBundleId] = useState("");
  const purchase = usablePackages.find((p) => p.id === packageId);

  const serviceSeminars = seminars.filter((s) => s.service.id === serviceId);
  // Group seminars don't use packages; a chosen package always means one-to-one.
  const groupMode = mode === "group" && !purchase && serviceSeminars.length > 0;

  const effectiveServiceId = purchase ? purchase.service_id : serviceId;
  const service = services.find((s) => s.id === effectiveServiceId);
  const formats = service ? serviceFormats(service) : [];
  const format: SessionFormat = purchase
    ? purchase.format
    : formats.includes(formatChoice)
      ? formatChoice
      : (formats[0] ?? "online");
  // null = covered by the package.
  const price = purchase || !service ? null : sessionPrice(service, format);
  const isFree = !price || price.amount_cents === 0;
  const serviceBundles = purchase || groupMode ? [] : packages.filter((p) => p.service.id === serviceId && p.prices[format]);
  const bundle = serviceBundles.find((p) => p.id === bundleId);
  const paymentBlocked = Boolean(price && price.amount_cents > 0 && !paymentsEnabled);
  const cheapestSeat = serviceSeminars.reduce<Seminar | undefined>(
    (low, s) => (!low || s.price.amount_cents < low.price.amount_cents ? s : low),
    undefined,
  );

  const availability = useApiQuery(`availability:${mentorId}:${effectiveServiceId}`, () =>
    api.mentors.availability(mentorId, {
      service: effectiveServiceId,
      from: utcDate(0),
      to: utcDate(LOOKAHEAD_DAYS),
    }),
  );
  // Note: slots for a paid service are still loaded so they appear as soon as payments launch;
  // the request button stays disabled while `paymentBlocked`.

  const days = useMemo(() => {
    const grouped = new Map<string, string[]>();
    for (const slot of availability.data?.slots ?? []) {
      const key = localDayKey(slot);
      grouped.set(key, [...(grouped.get(key) ?? []), slot]);
    }
    return [...grouped.entries()].map(([key, slots]) => ({ key, slots }));
  }, [availability.data]);

  const activeDay = days.find((d) => d.key === selectedDay) ?? days[0];

  if (services.length === 0) {
    return (
      <EmptyState
        icon={CalendarX2}
        title="No bookable services"
        description={`${mentorFirstName} hasn't published any services yet.`}
      />
    );
  }

  async function submit(note: string) {
    if (!service || !selectedSlot) return;
    let booking;
    try {
      booking = await api.bookings.create({
        service_id: service.id,
        start_at: selectedSlot,
        student_note: note,
        ...(purchase ? { package_purchase_id: purchase.id } : { format }),
      });
    } catch (error) {
      if (isApiError(error) && error.kind === "unauthenticated") {
        router.push(loginRedirectPath(pathname));
        return;
      }
      if (isApiError(error) && error.kind === "forbidden" && error.code === "permission_denied") {
        throw new Error("Only student accounts can book sessions.");
      }
      if (isApiError(error) && error.kind === "conflict") {
        // Keep the dialog (and its error message) open; refresh the times underneath it.
        setSlotTaken(true);
        availability.reload();
      }
      throw error;
    }
    if (booking.status === "pending_payment") {
      // The slot is now held; payment happens on the provider's page. The booking only moves on
      // once the backend has verified the provider's notification, never because of the redirect.
      try {
        const checkout = await api.bookings.checkout(booking.id);
        goToCheckout(checkout.checkout_url);
        await new Promise(() => {}); // keep the dialog busy while the browser leaves
      } catch (error) {
        toast.error("Your time is held, but the payment page didn't open", {
          description: `${getErrorMessage(error)} Use “Pay now” in your bookings to try again.`,
        });
        router.push("/dashboard/student/bookings");
      }
      return;
    }
    toast.success("Booking request sent", {
      description: `${mentorFirstName} will be notified. You can track it in your bookings.`,
    });
    router.push("/dashboard/student/bookings");
  }

  const zone = timeZoneLabel(undefined);

  return (
    <div className="grid min-w-0 gap-5">
      {usablePackages.length > 0 && !groupMode ? (
        <div className="grid min-w-0 gap-2">
          <label htmlFor={`${selectId}-pay`} className="text-sm font-medium">
            Pay with
          </label>
          <NativeSelect
            id={`${selectId}-pay`}
            value={purchase?.id ?? ""}
            onChange={(e) => {
              setPackageId(e.target.value);
              setSelectedDay(null);
              setSelectedSlot(null);
            }}
          >
            <option value="">Pay per session</option>
            {usablePackages.map((p) => (
              <option key={p.id} value={p.id}>
                Package: {p.title} ({pluralize(p.sessions_remaining, "session")} left)
              </option>
            ))}
          </NativeSelect>
        </div>
      ) : null}

      {purchase ? (
        service ? (
          <p className="rounded-lg bg-muted/60 p-3 text-sm">
            {service.title} · {formatDuration(purchase.duration_minutes)} · {FORMAT_LABEL[purchase.format]}
            {purchase.format === "in_person" && service.in_person_area ? ` in ${service.in_person_area}` : ""}. Book
            before {purchase.expires_at ? formatDate(purchase.expires_at) : "it expires"}.
          </p>
        ) : (
          <p role="note" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
            {mentorFirstName} isn&apos;t offering this package&apos;s session right now. Contact support if you need
            help using your package.
          </p>
        )
      ) : (
        <div className="grid min-w-0 gap-2">
          <label htmlFor={selectId} className="text-sm font-medium">
            Service
          </label>
          <NativeSelect
            id={selectId}
            value={serviceId}
            onChange={(e) => {
              setServiceId(e.target.value);
              setSelectedDay(null);
              setSelectedSlot(null);
            }}
          >
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} · {formatDuration(s.duration_minutes)} · {formatMoney(sessionPrice(s, serviceFormats(s)[0] ?? "online"))}
                {isBookable(s) ? "" : " (online payment coming soon)"}
              </option>
            ))}
          </NativeSelect>
        </div>
      )}

      {!purchase && cheapestSeat ? (
        <fieldset className="grid min-w-0 gap-2">
          <legend className="mb-2 text-sm font-medium">Session type</legend>
          {(
            [
              ["one", "One-to-one", "Any open time · just you", price ? formatMoney(price) : ""],
              [
                "group",
                "Group seminar",
                `Fixed dates · up to ${Math.max(...serviceSeminars.map((s) => s.capacity))} people`,
                `${formatMoney(cheapestSeat.price)}${cheapestSeat.price.amount_cents > 0 ? " per seat" : ""}`,
              ],
            ] as const
          ).map(([value, label, hint, cost]) => (
            <label
              key={value}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm",
                (value === "group") === groupMode ? "border-primary bg-primary/5" : "bg-card hover:border-primary/50",
              )}
            >
              <input
                type="radio"
                name={`${selectId}-mode`}
                value={value}
                checked={(value === "group") === groupMode}
                onChange={() => setMode(value)}
                className="size-4 accent-primary"
              />
              <span className="min-w-0 flex-1">
                <span className="font-medium">{label}</span>
                <span className="block text-muted-foreground">{hint}</span>
              </span>
              <span className="font-medium">{cost}</span>
            </label>
          ))}
        </fieldset>
      ) : null}

      {groupMode ? (
        <SeminarPicker
          key={serviceId}
          seminars={serviceSeminars}
          mentorFirstName={mentorFirstName}
          initialSeminarId={initialSeminarId}
          paymentsEnabled={paymentsEnabled}
          paymentsLivemode={paymentsLivemode}
          freeCancellationHours={freeCancellationHours}
        />
      ) : (
      <>
      {!purchase && service && formats.length > 1 ? (
        <fieldset className="grid min-w-0 gap-2">
          <legend className="mb-2 text-sm font-medium">Format</legend>
          {formats.map((f) => (
            <label
              key={f}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm",
                f === format ? "border-primary bg-primary/5" : "bg-card hover:border-primary/50",
              )}
            >
              <input
                type="radio"
                name={`${selectId}-format`}
                value={f}
                checked={f === format}
                onChange={() => setFormatChoice(f)}
                className="size-4 accent-primary"
              />
              <span className="min-w-0 flex-1">
                <span className="font-medium">{FORMAT_LABEL[f]}</span>
                {f === "in_person" ? (
                  <span className="block text-muted-foreground">Meet in {service.in_person_area}</span>
                ) : (
                  <span className="block text-muted-foreground">Video call</span>
                )}
              </span>
              <span className="font-medium">{formatMoney(sessionPrice(service, f))}</span>
            </label>
          ))}
        </fieldset>
      ) : !purchase && service && format === "in_person" ? (
        <p className="text-sm text-muted-foreground">In person only: meet in {service.in_person_area}.</p>
      ) : null}

      {serviceBundles.length > 0 && price ? (
        <fieldset className="grid min-w-0 gap-2">
          <legend className="mb-2 text-sm font-medium">How many sessions</legend>
          {[undefined, ...serviceBundles].map((option) => {
            const id = option?.id ?? "";
            const cost = option ? option.prices[format]! : price;
            return (
              <label
                key={id || "one"}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm",
                  id === (bundle?.id ?? "") ? "border-primary bg-primary/5" : "bg-card hover:border-primary/50",
                )}
              >
                <input
                  type="radio"
                  name={`${selectId}-count`}
                  value={id}
                  checked={id === (bundle?.id ?? "")}
                  onChange={() => setBundleId(id)}
                  className="size-4 accent-primary"
                />
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{option ? `${option.session_count} sessions` : "1 session"}</span>
                  <span className="block text-muted-foreground">
                    {option
                      ? `Book each when it suits you · within ${option.validity_days} days`
                      : "Pick a time now"}
                  </span>
                </span>
                <span className="text-right font-medium">
                  {formatMoney(cost)}
                  {option && option.discount_percent > 0 ? (
                    <span className="block text-xs font-normal text-muted-foreground">save {option.discount_percent}%</span>
                  ) : null}
                </span>
              </label>
            );
          })}
        </fieldset>
      ) : null}

      {bundle ? (
        <BundleCheckout
          key={`${bundle.id}:${format}`}
          bundle={bundle}
          format={format}
          mentorSlug={mentorId}
          mentorFirstName={mentorFirstName}
          paymentsEnabled={paymentsEnabled}
          paymentsLivemode={paymentsLivemode}
        />
      ) : (
      <>
      {paymentBlocked ? (
        <p role="note" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
          Online payment isn&apos;t available yet, so paid sessions can&apos;t be booked.
          {services.some(isBookable) ? " Choose a free session, or check back soon." : " Please check back soon."}
        </p>
      ) : availability.status === "loading" ? (
        <div role="status" className="grid gap-3">
          <span className="sr-only">Loading available times…</span>
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : availability.status === "error" ? (
        <ErrorState error={availability.error} title="Couldn't load availability" onRetry={availability.reload} />
      ) : days.length === 0 ? (
        <EmptyState
          icon={CalendarX2}
          title="No open times"
          description={`${mentorFirstName} has no open times in the next ${LOOKAHEAD_DAYS} days for this service.`}
        />
      ) : (
        <>
          <fieldset className="min-w-0">
            <legend className="mb-2 text-sm font-medium">Date</legend>
            <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
              {days.map((day) => {
                const active = day.key === activeDay?.key;
                const first = day.slots[0]!;
                return (
                  <button
                    key={day.key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setSelectedDay(day.key);
                      setSelectedSlot(null);
                    }}
                    className={cn(
                      "flex min-w-16 shrink-0 flex-col items-center rounded-lg border px-3 py-2 text-sm transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                      active ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:border-primary/50",
                    )}
                  >
                    <span className="text-xs">
                      {new Intl.DateTimeFormat("en-US", { weekday: "short" }).format(new Date(first))}
                    </span>
                    <span className="text-base font-semibold">
                      {new Intl.DateTimeFormat("en-US", { day: "numeric" }).format(new Date(first))}
                    </span>
                    <span className="text-xs">
                      {new Intl.DateTimeFormat("en-US", { month: "short" }).format(new Date(first))}
                    </span>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {activeDay ? (
            <fieldset>
              <legend className="mb-2 text-sm font-medium">
                Time <span className="font-normal text-muted-foreground">({zone}, your time zone)</span>
              </legend>
              <div className="grid grid-cols-3 gap-2">
                {activeDay.slots.map((slot) => {
                  const active = slot === selectedSlot;
                  return (
                    <button
                      key={slot}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setSelectedSlot(slot)}
                      className={cn(
                        "h-10 rounded-lg border text-sm font-medium tabular-nums transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                        active ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:border-primary/50",
                      )}
                    >
                      {formatTime(slot)}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          ) : null}
        </>
      )}

      <div className="rounded-lg bg-muted/60 p-4 text-sm" aria-live="polite">
        {service && selectedSlot ? (
          <p>
            <span className="font-medium">{service.title}</span> on {formatDate(selectedSlot)} at{" "}
            {formatTime(selectedSlot)} {zone} · {FORMAT_LABEL[format]} ·{" "}
            {price ? formatMoney(price) : "from your package"}
          </p>
        ) : (
          <p className="text-muted-foreground">Choose a date and time to continue.</p>
        )}
      </div>

      <Button
        size="lg"
        disabled={!service || !selectedSlot || paymentBlocked}
        onClick={() => setConfirmOpen(true)}
      >
        {!isFree && !paymentBlocked ? "Book and pay" : "Request booking"}
      </Button>

      {service && selectedSlot ? (
        <ConfirmationDialog
          open={confirmOpen}
          onOpenChange={(open) => {
            setConfirmOpen(open);
            if (!open && slotTaken) {
              setSelectedSlot(null);
              setSlotTaken(false);
            }
          }}
          title={isFree ? "Request this session?" : "Continue to payment?"}
          description={
            isFree
              ? `${mentorFirstName} will be asked to accept your request. You can cancel any time before the session starts.${
                  purchase
                    ? ` The session comes from your package; cancelling at least ${freeCancellationHours} hours before it starts returns it to the package.`
                    : ""
                }`
              : `You'll pay on our payment provider's secure page. Your card is authorised now but only charged if ${mentorFirstName} accepts; if they decline or don't respond, the authorisation is released. After they accept, you can cancel for a full refund up to ${freeCancellationHours} hours before the session.`
          }
          confirmLabel={isFree ? "Send request" : "Continue to payment"}
          reason={{
            label: `Note for ${mentorFirstName}`,
            placeholder: "What would you like help with? Share any context that will make the session useful.",
          }}
          onConfirm={submit}
        >
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg bg-muted/60 p-4 text-sm">
            <dt className="text-muted-foreground">Service</dt>
            <dd>{service.title}</dd>
            <dt className="text-muted-foreground">When</dt>
            <dd>
              {formatDate(selectedSlot)}, {formatTime(selectedSlot)} {zone}
            </dd>
            <dt className="text-muted-foreground">Length</dt>
            <dd>{formatDuration(purchase?.duration_minutes ?? service.duration_minutes)}</dd>
            <dt className="text-muted-foreground">Format</dt>
            <dd>
              {FORMAT_LABEL[format]}
              {format === "in_person" && service.in_person_area ? ` · ${service.in_person_area}` : ""}
            </dd>
            <dt className="text-muted-foreground">Price</dt>
            <dd className="font-medium">{price ? formatMoney(price) : `Included in ${purchase?.title}`}</dd>
          </dl>
          {format === "in_person" ? (
            <p className="text-sm text-muted-foreground">
              {mentorFirstName} will share the exact meeting place once the session is confirmed. Meet somewhere
              public.
            </p>
          ) : null}
          {!isFree && !paymentsLivemode ? (
            <p role="note" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
              Test mode: payments run in the provider&apos;s sandbox. Use a test card; no real money is taken.
            </p>
          ) : null}
        </ConfirmationDialog>
      ) : null}
      </>
      )}
      </>
      )}
    </div>
  );
}
