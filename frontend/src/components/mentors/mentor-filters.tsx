"use client";

import { useRouter } from "next/navigation";
import { useTransition, type FormEvent } from "react";
import Link from "next/link";
import type { MentorSearchParams, Taxonomy } from "@/lib/api/types";
import { AVAILABILITY_OPTIONS, mentorsHref, parseMentorSearchParams } from "@/lib/search-params";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormField, FormFieldset } from "@/components/forms/form-field";
import { NativeSelect } from "@/components/forms/native-select";

/**
 * Directory filters. A plain GET form (works without JavaScript); with JavaScript it
 * navigates client-side and drops empty values so URLs stay clean and shareable.
 */
export function MentorFilters({
  taxonomy,
  params,
  idPrefix,
  onApplied,
}: {
  taxonomy: Taxonomy;
  params: MentorSearchParams;
  /** Unique per instance (desktop sidebar vs mobile sheet) to keep ids unique. */
  idPrefix: string;
  onApplied?: () => void;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const raw: Record<string, string> = {};
    data.forEach((value, key) => {
      if (typeof value === "string") raw[key] = value;
    });
    // Re-validate through the same parser the page uses; page resets to 1.
    const next = { ...parseMentorSearchParams(raw), page: undefined };
    startTransition(() => {
      router.push(mentorsHref(next));
      onApplied?.();
    });
  }

  const id = (name: string) => `${idPrefix}-${name}`;

  return (
    <form action="/mentors" method="get" onSubmit={handleSubmit} aria-label="Filter mentors" className="grid gap-5">
      {params.q ? <input type="hidden" name="q" value={params.q} /> : null}
      {params.sort ? <input type="hidden" name="sort" value={params.sort} /> : null}

      <FormField label="Industry" id={id("industry")}>
        {(props) => (
          <NativeSelect {...props} name="industry" defaultValue={params.industry ?? ""}>
            <option value="">All industries</option>
            {taxonomy.industries.map((i) => (
              <option key={i.id} value={i.slug}>
                {i.name}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>

      <FormField label="Skill" id={id("skill")}>
        {(props) => (
          <NativeSelect {...props} name="skill" defaultValue={params.skill ?? ""}>
            <option value="">Any skill</option>
            {taxonomy.skills.map((s) => (
              <option key={s.id} value={s.slug}>
                {s.name}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>

      <FormField label="Country" id={id("country")}>
        {(props) => (
          <NativeSelect {...props} name="country" defaultValue={params.country ?? ""}>
            <option value="">Any country</option>
            {taxonomy.countries.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>

      <FormField label="Language" id={id("language")}>
        {(props) => (
          <NativeSelect {...props} name="language" defaultValue={params.language ?? ""}>
            <option value="">Any language</option>
            {taxonomy.languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>

      <FormFieldset legend="Price per session (USD)">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Minimum" id={id("price-min")}>
            {(props) => (
              <Input
                {...props}
                name="price_min"
                type="number"
                inputMode="numeric"
                min={0}
                step={5}
                placeholder="0"
                defaultValue={params.price_min ?? ""}
              />
            )}
          </FormField>
          <FormField label="Maximum" id={id("price-max")}>
            {(props) => (
              <Input
                {...props}
                name="price_max"
                type="number"
                inputMode="numeric"
                min={0}
                step={5}
                placeholder="Any"
                defaultValue={params.price_max ?? ""}
              />
            )}
          </FormField>
        </div>
      </FormFieldset>

      <FormFieldset legend="Availability">
        <div className="grid gap-2">
          {[{ value: "", label: "Any time" }, ...AVAILABILITY_OPTIONS.map((o) => ({ ...o, value: String(o.value) }))].map(
            (option) => (
              <label key={option.value || "any"} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="available_within"
                  value={option.value}
                  defaultChecked={String(params.available_within ?? "") === option.value}
                  className="size-4 accent-primary"
                />
                {option.label}
              </label>
            ),
          )}
        </div>
      </FormFieldset>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={pending} className="flex-1">
          {pending ? "Applying…" : "Apply filters"}
        </Button>
        <Button asChild variant="ghost">
          <Link href={mentorsHref({ q: params.q, sort: params.sort })}>Clear</Link>
        </Button>
      </div>
    </form>
  );
}
