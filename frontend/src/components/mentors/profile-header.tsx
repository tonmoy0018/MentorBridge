import { Briefcase, Globe2, MapPin } from "lucide-react";
import type { ReactNode } from "react";
import type { MentorProfile } from "@/lib/api/types";
import { countryName, languageName, pluralize } from "@/lib/format";
import { MentorAvatar } from "./mentor-avatar";
import { RatingDisplay } from "./rating-display";
import { VerifiedBadge } from "./verified-badge";

export function ProfileHeader({ mentor, actions }: { mentor: MentorProfile; actions?: ReactNode }) {
  return (
    <header className="flex flex-col gap-6 sm:flex-row sm:items-start">
      <MentorAvatar name={mentor.display_name} src={mentor.avatar_url} size="xl" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold sm:text-4xl">{mentor.display_name}</h1>
          <VerifiedBadge verified={mentor.is_verified} />
        </div>
        <p className="mt-1 text-lg text-muted-foreground">
          {mentor.current_title}
          {mentor.current_company ? ` at ${mentor.current_company}` : ""}
        </p>
        <p className="mt-3 max-w-2xl">{mentor.headline}</p>
        <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
          {mentor.country ? (
            <li className="flex items-center gap-1.5">
              <MapPin className="size-4" aria-hidden="true" />
              <span className="sr-only">Location: </span>
              {countryName(mentor.country)}
            </li>
          ) : null}
          {mentor.languages.length ? (
            <li className="flex items-center gap-1.5">
              <Globe2 className="size-4" aria-hidden="true" />
              <span className="sr-only">Languages: </span>
              {mentor.languages.map(languageName).join(", ")}
            </li>
          ) : null}
          <li className="flex items-center gap-1.5">
            <Briefcase className="size-4" aria-hidden="true" />
            {pluralize(mentor.years_experience, "year")} of experience
          </li>
          <li>
            <RatingDisplay rating={mentor.rating_avg} count={mentor.rating_count} />
          </li>
        </ul>
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2 sm:flex-col">{actions}</div> : null}
    </header>
  );
}
