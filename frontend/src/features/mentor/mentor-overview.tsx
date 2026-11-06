"use client";

import { CalendarCheck, Inbox, Star, Wallet } from "lucide-react";
import Link from "next/link";
import type { Booking } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { BookingActions, bookingPermissions } from "@/components/bookings/booking-actions";
import { BookingCard } from "@/components/bookings/booking-card";
import { PageHeader, SectionHeading } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatCard } from "@/components/common/stat-card";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { EmptyState } from "@/components/feedback/empty-state";
import { useApiQuery } from "@/hooks/use-api-query";
import { VerificationNotice } from "./verification-status";

export function MentorOverview() {
  const { user } = useCurrentUser();
  const profile = useApiQuery("mentor:profile", () => api.mentor.profile());
  const bookings = useApiQuery("mentor:bookings", () => api.bookings.list({ scope: "upcoming" }));
  const earnings = useApiQuery("mentor:earnings", () => api.mentor.earningsSummary());

  const requests = bookings.data?.results.filter((b) => b.status === "requested") ?? [];
  const confirmed = bookings.data?.results.filter((b) => b.status === "confirmed") ?? [];

  const replace = (updated: Booking) =>
    bookings.mutate((page) => ({ ...page, results: page.results.map((b) => (b.id === updated.id ? updated : b)) }));

  const renderList = (items: Booking[]) => (
    <ul className="grid grid-cols-1 gap-4">
      {items.map((booking) => (
        <li key={booking.id}>
          <BookingCard
            booking={booking}
            perspective="mentor"
            timeZone={user.timezone}
            actions={
              bookingPermissions(booking, "mentor").any ? (
                <BookingActions booking={booking} perspective="mentor" onUpdated={replace} onStale={bookings.reload} />
              ) : undefined
            }
          />
        </li>
      ))}
    </ul>
  );

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={`Welcome back, ${user.first_name}`} description="Your requests, sessions and earnings at a glance." />

      {profile.data && profile.data.verification_status !== "approved" ? (
        <VerificationNotice
          status={profile.data.verification_status}
          reason={profile.data.verification_decision_reason}
          action={
            <Button asChild variant="outline">
              <Link href="/dashboard/mentor/profile">Go to profile</Link>
            </Button>
          }
        />
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Requests to review" value={bookings.data ? requests.length : "–"} icon={Inbox} />
        <StatCard label="Upcoming sessions" value={bookings.data ? confirmed.length : "–"} icon={CalendarCheck} />
        <StatCard
          label="Available balance"
          value={earnings.data ? formatMoney(earnings.data.available, { showFree: false }) : "–"}
          hint={earnings.data ? `${formatMoney(earnings.data.pending, { showFree: false })} pending` : undefined}
          icon={Wallet}
        />
        <StatCard
          label="Rating"
          value={profile.data?.rating_avg ? Number(profile.data.rating_avg).toFixed(1) : "–"}
          hint={profile.data ? (profile.data.rating_count ? `${profile.data.rating_count} reviews` : "No reviews yet") : undefined}
          icon={Star}
        />
      </div>

      <section aria-labelledby="requests-heading" className="grid grid-cols-1 gap-4">
        <SectionHeading
          id="requests-heading"
          title="Requests waiting for you"
          description="Respond within 48 hours. Unanswered requests expire and the student isn't charged."
        />
        <QueryView query={bookings} errorTitle="Couldn't load booking requests">
          {() =>
            requests.length === 0 ? (
              <EmptyState icon={Inbox} title="You're all caught up" description="New booking requests will appear here." />
            ) : (
              renderList(requests)
            )
          }
        </QueryView>
      </section>

      <section aria-labelledby="sessions-heading" className="grid grid-cols-1 gap-4">
        <SectionHeading
          id="sessions-heading"
          title="Upcoming sessions"
          action={
            <Link href="/dashboard/mentor/bookings" className="text-sm font-medium text-primary hover:underline">
              All bookings
            </Link>
          }
        />
        <QueryView query={bookings} errorTitle="Couldn't load sessions">
          {() =>
            confirmed.length === 0 ? (
              <EmptyState
                icon={CalendarCheck}
                title="No confirmed sessions yet"
                description="Keep your availability up to date so students can book you."
                action={
                  <Button asChild variant="outline">
                    <Link href="/dashboard/mentor/availability">Update availability</Link>
                  </Button>
                }
              />
            ) : (
              renderList(confirmed.slice(0, 3))
            )
          }
        </QueryView>
      </section>
    </div>
  );
}
