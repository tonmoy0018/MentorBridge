"use client";

import { CalendarDays } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";
import type { Booking } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QueryView } from "@/components/common/query-view";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { EmptyState } from "@/components/feedback/empty-state";
import { useApiQuery } from "@/hooks/use-api-query";
import { BookingActions, bookingPermissions } from "./booking-actions";
import { BookingCard } from "./booking-card";
import { CheckoutReturnNotice } from "./checkout-return-notice";

type Perspective = "student" | "mentor";

const ACTIVE = new Set<Booking["status"]>(["pending_payment", "requested", "confirmed"]);
const isFuture = (b: Booking) => new Date(b.end_at).getTime() >= Date.now();

interface TabDef {
  value: string;
  label: string;
  filter: (b: Booking) => boolean;
  empty: string;
  sortDesc?: boolean;
}

const TABS: Record<Perspective, TabDef[]> = {
  student: [
    { value: "upcoming", label: "Upcoming", filter: (b) => ACTIVE.has(b.status) && isFuture(b), empty: "You have no upcoming sessions." },
    { value: "past", label: "Past", filter: (b) => b.status === "completed" || (ACTIVE.has(b.status) && !isFuture(b)), empty: "Your completed sessions will appear here.", sortDesc: true },
    { value: "cancelled", label: "Cancelled", filter: (b) => ["cancelled", "declined", "expired"].includes(b.status), empty: "No cancelled or declined bookings.", sortDesc: true },
  ],
  mentor: [
    { value: "requests", label: "Requests", filter: (b) => b.status === "requested" && isFuture(b), empty: "No requests waiting for your response." },
    { value: "upcoming", label: "Upcoming", filter: (b) => (b.status === "confirmed" || b.status === "pending_payment") && isFuture(b), empty: "No upcoming confirmed sessions." },
    { value: "past", label: "Past", filter: (b) => b.status === "completed" || (b.status === "confirmed" && !isFuture(b)), empty: "Completed sessions will appear here.", sortDesc: true },
    { value: "cancelled", label: "Cancelled", filter: (b) => ["cancelled", "declined", "expired"].includes(b.status), empty: "No cancelled or declined bookings.", sortDesc: true },
  ],
};

export function BookingsBoard({ perspective }: { perspective: Perspective }) {
  const { user } = useCurrentUser();
  // All of the user's bookings: the tabs filter them client-side, so a single page would drop
  // the newest ones once someone has more than a page of history.
  const query = useApiQuery(`bookings:${perspective}`, async () => {
    const results = await api.bookings.listAll({ scope: "all" });
    return { count: results.length, next: null, previous: null, results };
  });
  const tabs = TABS[perspective];

  const replace = (updated: Booking) =>
    query.mutate((page) => ({ ...page, results: page.results.map((b) => (b.id === updated.id ? updated : b)) }));

  return (
    <>
      {perspective === "student" ? (
        <Suspense fallback={null}>
          <CheckoutReturnNotice onSettled={query.reload} timeZone={user.timezone} />
        </Suspense>
      ) : null}
      <QueryView query={query} errorTitle="We couldn't load your bookings">
      {(page) => (
        <Tabs defaultValue={tabs[0]!.value}>
          <TabsList className="h-auto flex-wrap">
            {tabs.map((tab) => {
              const count = page.results.filter(tab.filter).length;
              return (
                <TabsTrigger key={tab.value} value={tab.value} className="px-3 py-1.5">
                  {tab.label}
                  <span className="rounded-full bg-muted px-1.5 text-xs tabular-nums">{count}</span>
                </TabsTrigger>
              );
            })}
          </TabsList>
          {tabs.map((tab) => {
            const items = page.results
              .filter(tab.filter)
              .sort((a, b) => (tab.sortDesc ? b.start_at.localeCompare(a.start_at) : a.start_at.localeCompare(b.start_at)));
            return (
              <TabsContent key={tab.value} value={tab.value} className="mt-4">
                {items.length === 0 ? (
                  <EmptyState
                    icon={CalendarDays}
                    title={tab.empty}
                    action={
                      perspective === "student" && tab.value === "upcoming" ? (
                        <Button asChild>
                          <Link href="/mentors">Find a mentor</Link>
                        </Button>
                      ) : undefined
                    }
                  />
                ) : (
                  <ul className="grid grid-cols-1 gap-4">
                    {items.map((booking) => (
                      <li key={booking.id}>
                        <BookingCard
                          booking={booking}
                          perspective={perspective}
                          timeZone={user.timezone}
                          actions={
                            bookingPermissions(booking, perspective).any ? (
                              <BookingActions
                                booking={booking}
                                perspective={perspective}
                                onUpdated={replace}
                                onStale={query.reload}
                              />
                            ) : undefined
                          }
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}
    </QueryView>
    </>
  );
}
