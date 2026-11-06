import {
  Briefcase,
  Code2,
  Cog,
  HeartPulse,
  Landmark,
  Megaphone,
  Palette,
  Scale,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import type { IndustryWithCount } from "@/lib/api/types";
import { pluralize } from "@/lib/format";
import { mentorsHref } from "@/lib/search-params";

const ICONS: Record<string, LucideIcon> = {
  technology: Code2,
  finance: Landmark,
  healthcare: HeartPulse,
  design: Palette,
  consulting: Briefcase,
  marketing: Megaphone,
  engineering: Cog,
  law: Scale,
  "human-resources": Users,
};

export function CategoryCard({ industry }: { industry: IndustryWithCount }) {
  const Icon = ICONS[industry.slug] ?? Briefcase;
  return (
    <Link
      href={mentorsHref({ industry: industry.slug })}
      className="group flex items-center gap-4 rounded-xl border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-accent/50"
    >
      <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className="block font-medium">{industry.name}</span>
        <span className="block text-sm text-muted-foreground">
          {industry.mentor_count > 0 ? pluralize(industry.mentor_count, "mentor") : "Be the first mentor"}
        </span>
      </span>
    </Link>
  );
}
