import type { MentorSearchParams, MentorSort } from "@/lib/api/types";

export type RawSearchParams = Record<string, string | string[] | undefined>;

export const SORT_OPTIONS: { value: MentorSort; label: string }[] = [
  { value: "relevance", label: "Most relevant" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "rating", label: "Highest rated" },
];

export const AVAILABILITY_OPTIONS: { value: number; label: string }[] = [
  { value: 3, label: "Within 3 days" },
  { value: 7, label: "Within a week" },
  { value: 14, label: "Within 2 weeks" },
];

const SORTS = new Set<MentorSort>(SORT_OPTIONS.map((o) => o.value));

function first(value: string | string[] | undefined): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  const trimmed = v?.trim();
  return trimmed ? trimmed : undefined;
}

function slug(value: string | undefined): string | undefined {
  return value && /^[a-z0-9-]{1,80}$/.test(value) ? value : undefined;
}

function nonNegativeInt(value: string | undefined, max: number): number | undefined {
  if (value === undefined || !/^\d+$/.test(value)) return undefined;
  const n = Number.parseInt(value, 10);
  return n <= max ? n : undefined;
}

/** Parse untrusted URL search params into validated mentor search params. */
export function parseMentorSearchParams(raw: RawSearchParams): MentorSearchParams {
  const country = first(raw.country)?.toUpperCase();
  const language = first(raw.language)?.toLowerCase();
  const sort = first(raw.sort) as MentorSort | undefined;
  const page = nonNegativeInt(first(raw.page), 1000);
  const availableWithin = nonNegativeInt(first(raw.available_within), 60);

  let priceMin = nonNegativeInt(first(raw.price_min), 100_000);
  let priceMax = nonNegativeInt(first(raw.price_max), 100_000);
  if (priceMin !== undefined && priceMax !== undefined && priceMin > priceMax) {
    [priceMin, priceMax] = [priceMax, priceMin];
  }

  return {
    q: first(raw.q)?.slice(0, 100),
    industry: slug(first(raw.industry)),
    skill: slug(first(raw.skill)),
    country: country && /^[A-Z]{2}$/.test(country) ? country : undefined,
    language: language && /^[a-z]{2,3}$/.test(language) ? language : undefined,
    price_min: priceMin,
    price_max: priceMax,
    available_within: availableWithin && availableWithin > 0 ? availableWithin : undefined,
    sort: sort && SORTS.has(sort) && sort !== "relevance" ? sort : undefined,
    page: page && page > 1 ? page : undefined,
  };
}

/** Serialize params to a query string, omitting empty values and defaults. */
export function toSearchQuery(params: MentorSearchParams): string {
  const qs = new URLSearchParams();
  const entries: [string, string | number | undefined][] = [
    ["q", params.q],
    ["industry", params.industry],
    ["skill", params.skill],
    ["country", params.country],
    ["language", params.language],
    ["price_min", params.price_min],
    ["price_max", params.price_max],
    ["available_within", params.available_within],
    ["sort", params.sort === "relevance" ? undefined : params.sort],
    ["page", params.page && params.page > 1 ? params.page : undefined],
  ];
  for (const [key, value] of entries) {
    if (value !== undefined && value !== "") qs.set(key, String(value));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export function mentorsHref(params: MentorSearchParams): string {
  return `/mentors${toSearchQuery(params)}`;
}

/** Number of active filters (excluding text search, sort and page). */
export function countActiveFilters(params: MentorSearchParams): number {
  return [
    params.industry,
    params.skill,
    params.country,
    params.language,
    params.price_min,
    params.price_max,
    params.available_within,
  ].filter((v) => v !== undefined).length;
}
