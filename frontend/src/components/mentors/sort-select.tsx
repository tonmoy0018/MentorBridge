"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { MentorSearchParams, MentorSort } from "@/lib/api/types";
import { SORT_OPTIONS, mentorsHref } from "@/lib/search-params";
import { NativeSelect } from "@/components/forms/native-select";

export function SortSelect({ params }: { params: MentorSearchParams }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  return (
    <form action="/mentors" method="get" className="flex items-center gap-2">
      <label htmlFor="sort" className="text-sm whitespace-nowrap text-muted-foreground">
        Sort by
      </label>
      <NativeSelect
        id="sort"
        name="sort"
        defaultValue={params.sort ?? "relevance"}
        aria-busy={pending}
        className="w-48"
        onChange={(event) => {
          const sort = event.target.value as MentorSort;
          startTransition(() => router.push(mentorsHref({ ...params, sort, page: undefined })));
        }}
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </NativeSelect>
      <noscript>
        <button type="submit" className="text-sm underline">
          Apply
        </button>
      </noscript>
    </form>
  );
}
