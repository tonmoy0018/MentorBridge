import { Briefcase, GraduationCap } from "lucide-react";
import type { MentorExperience } from "@/lib/api/types";
import { formatMonthYear } from "@/lib/format";

function period(experience: MentorExperience) {
  const start = formatMonthYear(experience.start_date);
  const end = experience.end_date ? formatMonthYear(experience.end_date) : "Present";
  return `${start} – ${end}`;
}

export function ExperienceTimeline({ experiences }: { experiences: MentorExperience[] }) {
  const sorted = [...experiences].sort((a, b) => b.start_date.localeCompare(a.start_date));
  return (
    <ol className="relative grid gap-6 border-l pl-6">
      {sorted.map((experience) => {
        const Icon = experience.kind === "education" ? GraduationCap : Briefcase;
        return (
          <li key={experience.id} className="relative">
            <span className="absolute top-0.5 -left-[2.3rem] flex size-7 items-center justify-center rounded-full border bg-card">
              <Icon className="size-3.5 text-primary" aria-hidden="true" />
            </span>
            <h3 className="font-medium">{experience.title}</h3>
            <p className="text-sm text-muted-foreground">
              {experience.organization} · <span className="whitespace-nowrap">{period(experience)}</span>
              <span className="sr-only">{experience.kind === "education" ? " (education)" : " (work)"}</span>
            </p>
            {experience.description ? <p className="mt-1 text-sm">{experience.description}</p> : null}
          </li>
        );
      })}
    </ol>
  );
}
