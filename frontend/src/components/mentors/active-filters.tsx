import { X } from "lucide-react";
import Link from "next/link";
import type { MentorSearchParams, Taxonomy } from "@/lib/api/types";
import { AVAILABILITY_OPTIONS, mentorsHref } from "@/lib/search-params";

/** Removable chips for each active filter. Each chip is a link to the URL without it. */
export function ActiveFilters({ params, taxonomy }: { params: MentorSearchParams; taxonomy: Taxonomy }) {
  const without = (patch: Partial<MentorSearchParams>) => mentorsHref({ ...params, ...patch, page: undefined });

  const chips: { label: string; href: string }[] = [];
  if (params.q) chips.push({ label: `“${params.q}”`, href: without({ q: undefined }) });
  if (params.industry) {
    const name = taxonomy.industries.find((i) => i.slug === params.industry)?.name ?? params.industry;
    chips.push({ label: name, href: without({ industry: undefined }) });
  }
  if (params.skill) {
    const name = taxonomy.skills.find((s) => s.slug === params.skill)?.name ?? params.skill;
    chips.push({ label: name, href: without({ skill: undefined }) });
  }
  if (params.country) {
    const name = taxonomy.countries.find((c) => c.code === params.country)?.name ?? params.country;
    chips.push({ label: name, href: without({ country: undefined }) });
  }
  if (params.language) {
    const name = taxonomy.languages.find((l) => l.code === params.language)?.name ?? params.language;
    chips.push({ label: name, href: without({ language: undefined }) });
  }
  if (params.price_min !== undefined || params.price_max !== undefined) {
    const label =
      params.price_min !== undefined && params.price_max !== undefined
        ? `$${params.price_min}–$${params.price_max}`
        : params.price_min !== undefined
          ? `$${params.price_min}+`
          : `Up to $${params.price_max}`;
    chips.push({ label, href: without({ price_min: undefined, price_max: undefined }) });
  }
  if (params.available_within) {
    const label =
      AVAILABILITY_OPTIONS.find((o) => o.value === params.available_within)?.label ??
      `Within ${params.available_within} days`;
    chips.push({ label: `Available ${label.toLowerCase()}`, href: without({ available_within: undefined }) });
  }

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">Active filters:</span>
      <ul className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <li key={chip.label}>
            <Link
              href={chip.href}
              className="inline-flex items-center gap-1 rounded-full border bg-card py-1 pr-2 pl-3 text-sm hover:border-primary/40"
            >
              {chip.label}
              <X className="size-3.5 text-muted-foreground" aria-hidden="true" />
              <span className="sr-only">(remove filter)</span>
            </Link>
          </li>
        ))}
      </ul>
      <Link href={mentorsHref({ sort: params.sort })} className="text-sm font-medium text-primary hover:underline">
        Clear all
      </Link>
    </div>
  );
}
