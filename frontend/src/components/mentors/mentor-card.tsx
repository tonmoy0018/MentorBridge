import { CalendarClock, Globe2, MapPin } from "lucide-react";
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
 * Mentor summary card. The whole card is clickable via a stretched link on the name,
 * so there is a single, well-labelled link per card for keyboard and screen-reader users.
 * `action` renders above the stretched link (e.g. a remove button) and stays clickable.
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

  return (
    <article
      className={cn(
        "group relative flex h-full flex-col rounded-xl border bg-card p-5 transition-shadow focus-within:ring-3 focus-within:ring-ring/40 hover:shadow-md",
        className,
      )}
    >
      <div className="flex items-start gap-4">
        <MentorAvatar name={mentor.display_name} src={mentor.avatar_url} size="lg" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Heading className="text-base font-semibold">
              <Link
                href={ROUTES.mentor(mentor.slug)}
                className="outline-none after:absolute after:inset-0 after:rounded-xl group-hover:text-primary"
              >
                {mentor.display_name}
              </Link>
            </Heading>
            <VerifiedBadge verified={mentor.is_verified} compact />
          </div>
          <p className="truncate text-sm text-muted-foreground">
            {mentor.current_title}
            {mentor.current_company ? ` · ${mentor.current_company}` : ""}
          </p>
          <RatingDisplay rating={mentor.rating_avg} count={mentor.rating_count} className="mt-1" />
        </div>
      </div>

      <p className="mt-4 line-clamp-2 text-sm">{mentor.headline}</p>

      {mentor.skills.length > 0 ? (
        <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Skills">
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

      <dl className="mt-4 grid gap-1.5 text-sm text-muted-foreground">
        {mentor.country ? (
          <div className="flex items-center gap-2">
            <dt>
              <MapPin className="size-4" aria-hidden="true" />
              <span className="sr-only">Location</span>
            </dt>
            <dd>{countryName(mentor.country)}</dd>
          </div>
        ) : null}
        {mentor.languages.length > 0 ? (
          <div className="flex items-center gap-2">
            <dt>
              <Globe2 className="size-4" aria-hidden="true" />
              <span className="sr-only">Languages</span>
            </dt>
            <dd className="truncate">{mentor.languages.map(languageName).join(", ")}</dd>
          </div>
        ) : null}
        <div className="flex items-center gap-2">
          <dt>
            <CalendarClock className="size-4" aria-hidden="true" />
            <span className="sr-only">Next available</span>
          </dt>
          <dd>
            {mentor.next_available_at ? (
              <>
                Next available <LocalDateTime iso={mentor.next_available_at} />
              </>
            ) : (
              "No open times right now"
            )}
          </dd>
        </div>
      </dl>

      <div className="mt-auto pt-4">
        <div className="flex items-center justify-between gap-3 border-t pt-4">
          <PriceDisplay price={mentor.starting_price} from />
          {action ? <div className="relative z-10">{action}</div> : null}
        </div>
      </div>
    </article>
  );
}
