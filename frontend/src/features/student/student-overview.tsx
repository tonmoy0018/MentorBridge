"use client";

import { CalendarDays, Heart, Target } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/data/client";
import { formatCalendarDate, formatDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { BookingCard } from "@/components/bookings/booking-card";
import { BookingStatusBadge } from "@/components/bookings/booking-status-badge";
import { PageHeader, SectionHeading } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatCard } from "@/components/common/stat-card";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { EmptyState } from "@/components/feedback/empty-state";
import { MentorAvatar } from "@/components/mentors/mentor-avatar";
import { useApiQuery } from "@/hooks/use-api-query";
import { GoalStatusBadge } from "./goal-status";

export function StudentOverview() {
  const { user } = useCurrentUser();
  const upcoming = useApiQuery("student:upcoming", () => api.bookings.list({ scope: "upcoming" }));
  const past = useApiQuery("student:past", () => api.bookings.list({ scope: "past" }));
  const saved = useApiQuery("student:saved", () => api.student.savedMentors());
  const goals = useApiQuery("student:goals", () => api.student.goals());

  const activeGoals = goals.data?.filter((g) => g.status === "in_progress" || g.status === "not_started");
  const statValue = (n: number | undefined) => (n === undefined ? "–" : n);

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader
        title={`Welcome back, ${user.first_name}`}
        description="Here's what's coming up and what you're working towards."
        actions={
          <Button asChild>
            <Link href="/mentors">Find a mentor</Link>
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Upcoming sessions" value={statValue(upcoming.data?.count)} icon={CalendarDays} />
        <StatCard label="Saved mentors" value={statValue(saved.data?.count)} icon={Heart} />
        <StatCard label="Active goals" value={statValue(activeGoals?.length)} icon={Target} />
      </div>

      <section aria-labelledby="upcoming-heading" className="grid grid-cols-1 gap-4">
        <SectionHeading
          id="upcoming-heading"
          title="Upcoming sessions"
          action={
            <Link href="/dashboard/student/bookings" className="text-sm font-medium text-primary hover:underline">
              All bookings
            </Link>
          }
        />
        <QueryView query={upcoming} errorTitle="Couldn't load upcoming sessions">
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState
                icon={CalendarDays}
                title="No upcoming sessions"
                description="Find a mentor and book a time that suits you."
                action={
                  <Button asChild variant="outline">
                    <Link href="/mentors">Browse mentors</Link>
                  </Button>
                }
              />
            ) : (
              <ul className="grid grid-cols-1 gap-4">
                {page.results.slice(0, 3).map((booking) => (
                  <li key={booking.id}>
                    <BookingCard booking={booking} perspective="student" timeZone={user.timezone} />
                  </li>
                ))}
              </ul>
            )
          }
        </QueryView>
      </section>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
        <section aria-labelledby="recent-heading" className="grid content-start gap-4">
          <SectionHeading id="recent-heading" title="Recent bookings" />
          <QueryView query={past} errorTitle="Couldn't load recent bookings">
            {(page) =>
              page.results.length === 0 ? (
                <p className="text-sm text-muted-foreground">Past and cancelled bookings will appear here.</p>
              ) : (
                <ul className="divide-y rounded-xl border bg-card">
                  {page.results.slice(0, 4).map((booking) => (
                    <li key={booking.id} className="flex items-center justify-between gap-3 p-4">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{booking.service_title}</p>
                        <p className="truncate text-sm text-muted-foreground">
                          {booking.mentor.display_name} · {formatDateTime(booking.start_at, user.timezone)}
                        </p>
                      </div>
                      <BookingStatusBadge status={booking.status} perspective="student" />
                    </li>
                  ))}
                </ul>
              )
            }
          </QueryView>
        </section>

        <section aria-labelledby="saved-heading" className="grid content-start gap-4">
          <SectionHeading
            id="saved-heading"
            title="Saved mentors"
            action={
              <Link href="/dashboard/student/saved-mentors" className="text-sm font-medium text-primary hover:underline">
                View all
              </Link>
            }
          />
          <QueryView query={saved} errorTitle="Couldn't load saved mentors">
            {(page) =>
              page.results.length === 0 ? (
                <p className="text-sm text-muted-foreground">Save mentors from their profile to compare them later.</p>
              ) : (
                <ul className="divide-y rounded-xl border bg-card">
                  {page.results.slice(0, 4).map((mentor) => (
                    <li key={mentor.id}>
                      <Link href={`/mentors/${mentor.slug}`} className="flex items-center gap-3 p-4 hover:bg-muted/50">
                        <MentorAvatar name={mentor.display_name} src={mentor.avatar_url} size="sm" />
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{mentor.display_name}</span>
                          <span className="block truncate text-sm text-muted-foreground">{mentor.current_title}</span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )
            }
          </QueryView>
        </section>
      </div>

      <section aria-labelledby="goals-heading" className="grid grid-cols-1 gap-4">
        <SectionHeading
          id="goals-heading"
          title="Career goals"
          action={
            <Link href="/dashboard/student/goals" className="text-sm font-medium text-primary hover:underline">
              Manage goals
            </Link>
          }
        />
        <QueryView query={goals} errorTitle="Couldn't load goals">
          {(list) =>
            list.length === 0 ? (
              <EmptyState
                icon={Target}
                title="Set your first goal"
                description="Goals help you and your mentors focus sessions on what matters."
                action={
                  <Button asChild variant="outline">
                    <Link href="/dashboard/student/goals">Add a goal</Link>
                  </Button>
                }
              />
            ) : (
              <ul className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {list.slice(0, 3).map((goal) => (
                  <li key={goal.id} className="rounded-xl border bg-card p-4">
                    <GoalStatusBadge status={goal.status} />
                    <p className="mt-2 font-medium">{goal.title}</p>
                    {goal.target_date ? (
                      <p className="mt-1 text-sm text-muted-foreground">Target: {formatCalendarDate(goal.target_date)}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )
          }
        </QueryView>
      </section>
    </div>
  );
}
