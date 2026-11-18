import { CalendarDays, MapPin, Users, Video } from "lucide-react";
import Link from "next/link";
import type { Seminar } from "@/lib/api/types";
import { formatDuration, formatMoney, pluralize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { LocalDateTime } from "@/components/common/local-date-time";

/** Public list of a mentor's upcoming group seminars. "Choose" opens it in the booking panel. */
export function SeminarList({ seminars, mentorSlug }: { seminars: Seminar[]; mentorSlug: string }) {
  return (
    <ul className="grid gap-3">
      {seminars.map((seminar) => {
        const full = seminar.seats_left === 0;
        return (
          <li key={seminar.id} className="flex flex-col gap-4 rounded-xl border bg-card p-5 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <h3 className="font-semibold">{seminar.title}</h3>
              {seminar.description ? (
                <p className="mt-1 text-sm text-muted-foreground">{seminar.description}</p>
              ) : null}
              <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <CalendarDays className="size-4" aria-hidden="true" />
                  <LocalDateTime iso={seminar.start_at} /> · {formatDuration(seminar.duration_minutes)}
                </span>
                <span className="flex items-center gap-1.5">
                  {seminar.format === "in_person" ? (
                    <MapPin className="size-4" aria-hidden="true" />
                  ) : (
                    <Video className="size-4" aria-hidden="true" />
                  )}
                  {seminar.format === "in_person" ? `In person in ${seminar.in_person_area}` : "Online"}
                </span>
                <span className="flex items-center gap-1.5">
                  <Users className="size-4" aria-hidden="true" />
                  {full ? "Full" : `${pluralize(seminar.seats_left, "seat")} left of ${seminar.capacity}`}
                </span>
              </p>
            </div>
            <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
              <div className="text-right">
                <p className="text-lg font-semibold">{formatMoney(seminar.price)}</p>
                {seminar.price.amount_cents > 0 ? <p className="text-xs text-muted-foreground">per seat</p> : null}
              </div>
              {full ? null : (
                <Link
                  href={`/mentors/${encodeURIComponent(mentorSlug)}?seminar=${encodeURIComponent(seminar.id)}#book`}
                  scroll={false}
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                  aria-label={`Choose ${seminar.title}`}
                >
                  Choose
                </Link>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
