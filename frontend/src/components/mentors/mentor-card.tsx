import { ArrowRight, CalendarClock } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import type { MentorSummary } from "@/lib/api/types";
import { countryName, languageName } from "@/lib/format";
import { ROUTES } from "@/lib/routes";
import { cn } from "@/lib/utils";
import { LocalDateTime } from "@/components/common/local-date-time";
import { MentorAvatar } from "./mentor-avatar";
import { PriceDisplay } from "./price-display";
import { RatingDisplay } from "./rating-display";
import { VerifiedBadge } from "./verified-badge";

const MAX_SKILLS = 3;

/**
 * Mentor summary card, laid out for comparison: who (name, role), what they help with
 * (headline, skills), when (next opening) and how much (starting price).
 *
 * The whole card is clickable via a stretched link on the name, so there is a single,
 * well-labelled link per card for keyboard and screen-reader users. `action` renders above
 * the stretched link (e.g. a remove button) and stays clickable.
 */
export function MentorCard({
  mentor,
  action,
  headingLevel = "h3",
  className,
}: {
  mentor: MentorSummary;
  action?: ReactNode;
  headingLevel?: "h2" | "h3";
  className?: string;
}) {
  const Heading = headingLevel;
  const extraSkills = mentor.skills.length - MAX_SKILLS;
  const role = [mentor.current_title, mentor.current_company].filter(Boolean).join(" · ");
  const place = [
    mentor.country ? countryName(mentor.country) : "",
    mentor.languages.map(languageName).join(", "),
    mentor.offers_in_person ? "Meets in person" : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <article
      className={cn(
        "group relative flex h-full flex-col rounded-xl border bg-card p-5 transition-[box-shadow,border-color] focus-within:ring-3 focus-within:ring-ring/40 hover:border-primary/30 hover:shadow-md",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <MentorAvatar name={mentor.display_name} src={mentor.avatar_url} size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-1.5">
            <Heading className="min-w-0 truncate font-semibold" title={mentor.display_name}>
              <Link
                href={ROUTES.mentor(mentor.slug)}
                className="outline-none after:absolute after:inset-0 after:rounded-xl group-hover:text-primary"
              >
                {mentor.display_name}
              </Link>
            </Heading>
            <VerifiedBadge verified={mentor.is_verified} compact />
          </div>
          {role ? (
            <p className="truncate text-sm text-muted-foreground" title={role}>
              {role}
            </p>
          ) : null}
        </div>
      </div>

      {mentor.rating_count > 0 ? (
        <RatingDisplay rating={mentor.rating_avg} count={mentor.rating_count} className="mt-3" />
      ) : null}

      <p className="mt-3 line-clamp-2 text-sm leading-relaxed">{mentor.headline}</p>

      {mentor.skills.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Skills">
          {mentor.skills.slice(0, MAX_SKILLS).map((skill) => (
            <li key={skill.id} className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              {skill.name}
            </li>
          ))}
          {extraSkills > 0 ? (
            <li className="rounded-full px-1 py-0.5 text-xs text-muted-foreground">+{extraSkills} more</li>
          ) : null}
        </ul>
      ) : null}

      {place ? <p className="mt-3 truncate text-sm text-muted-foreground">{place}</p> : null}

      <div className="mt-auto pt-4">
        <p
          className={cn(
            "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
            mentor.next_available_at ? "bg-secondary text-secondary-foreground" : "bg-muted text-muted-foreground",
          )}
        >
          <CalendarClock className="size-4 shrink-0" aria-hidden="true" />
          <span className="min-w-0">
            {mentor.next_available_at ? (
              <>
                Next opening <LocalDateTime iso={mentor.next_available_at} />
              </>
            ) : (
              "No open times right now"
            )}
          </span>
        </p>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <PriceDisplay price={mentor.starting_price} from />
          {action ? (
            <div className="relative z-10">{action}</div>
          ) : (
            // Visual cue only; the card's single link is the name above.
            <span
              aria-hidden="true"
              className="inline-flex items-center gap-1 text-sm font-medium whitespace-nowrap text-primary group-hover:underline"
            >
              View profile <ArrowRight className="size-4" />
            </span>
          )}
        </div>
      </div>
    </article>
  );
}
