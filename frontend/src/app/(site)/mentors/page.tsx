import { SearchX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { getServerApi } from "@/lib/data/server";
import { pluralize } from "@/lib/format";
import {
  countActiveFilters,
  mentorsHref,
  parseMentorSearchParams,
  type RawSearchParams,
} from "@/lib/search-params";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Pagination } from "@/components/common/pagination";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/loading-state";
import { ActiveFilters } from "@/components/mentors/active-filters";
import { MentorCard } from "@/components/mentors/mentor-card";
import { MentorFilters } from "@/components/mentors/mentor-filters";
import { MobileFilters } from "@/components/mentors/mobile-filters";
import { SearchBar } from "@/components/mentors/search-bar";
import { SortSelect } from "@/components/mentors/sort-select";

export const metadata: Metadata = {
  title: "Find a mentor",
  description: "Search verified mentors by industry, skill, country, language, price and availability.",
};

const PAGE_SIZE = 9;

export default function MentorsPage({ searchParams }: PageProps<"/mentors">) {
  return (
    <div className="container-page py-8 sm:py-12">
      <h1 className="text-3xl font-semibold sm:text-4xl">Find a mentor</h1>
      <p className="mt-2 text-muted-foreground">
        Browse verified professionals and book one-to-one guidance.
      </p>
      <Suspense fallback={<DirectorySkeleton />}>
        <Directory searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Directory({ searchParams }: { searchParams: Promise<RawSearchParams> }) {
  const params = parseMentorSearchParams(await searchParams);
  const page = params.page ?? 1;
  const api = await getServerApi();
  const [taxonomyResult, resultsResult] = await Promise.allSettled([
    api.taxonomy.get(),
    api.mentors.search({ ...params, page, page_size: PAGE_SIZE }),
  ]);

  if (taxonomyResult.status === "rejected" || resultsResult.status === "rejected") {
    const error =
      taxonomyResult.status === "rejected"
        ? taxonomyResult.reason
        : (resultsResult as PromiseRejectedResult).reason;
    return (
      <ErrorState className="mt-8" error={error} title="We couldn't load mentors" retryHref={mentorsHref(params)} />
    );
  }

  const taxonomy = taxonomyResult.value;
  const results = resultsResult.value;
  const totalPages = Math.max(1, Math.ceil(results.count / PAGE_SIZE));
  const activeCount = countActiveFilters(params);

  return (
    <>
      <SearchBar defaultValue={params.q} hiddenParams={{ ...params, q: undefined, page: undefined }} className="mt-6 max-w-2xl" />

      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[17rem_1fr]">
        <aside aria-label="Filters" className="hidden lg:block">
          <div className="sticky top-24 rounded-xl border bg-card p-5">
            <h2 className="mb-4 font-semibold">Filters</h2>
            <MentorFilters taxonomy={taxonomy} params={params} idPrefix="desktop" />
          </div>
        </aside>

        <section aria-labelledby="results-heading" className="min-w-0">
          <h2 id="results-heading" className="sr-only">
            Results
          </h2>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p aria-live="polite" className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">{pluralize(results.count, "mentor")}</span> found
              {totalPages > 1 ? ` · page ${page} of ${totalPages}` : ""}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <MobileFilters taxonomy={taxonomy} params={params} activeCount={activeCount} />
              <SortSelect params={params} />
            </div>
          </div>

          <div className="mt-4">
            <ActiveFilters params={params} taxonomy={taxonomy} />
          </div>

          {results.results.length === 0 ? (
            <EmptyState
              className="mt-6"
              icon={SearchX}
              title={page > 1 ? "No more mentors on this page" : "No mentors match your search"}
              description="Try removing a filter, widening the price range or searching for a broader term."
              action={
                <Button asChild variant="outline">
                  <Link href="/mentors">Clear search and filters</Link>
                </Button>
              }
            />
          ) : (
            <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {results.results.map((mentor) => (
                <li key={mentor.id}>
                  <MentorCard mentor={mentor} />
                </li>
              ))}
            </ul>
          )}

          <Pagination
            className="mt-10"
            page={page}
            totalPages={totalPages}
            hrefForPage={(p) => mentorsHref({ ...params, page: p })}
          />
        </section>
      </div>
    </>
  );
}

function DirectorySkeleton() {
  return (
    <div className="mt-6">
      <Skeleton className="h-10 max-w-2xl rounded-lg" />
      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[17rem_1fr]">
        <Skeleton className="hidden h-[32rem] rounded-xl lg:block" />
        <div>
          <Skeleton className="h-6 w-40" />
          <CardListSkeleton count={6} className="mt-6 sm:grid-cols-2 xl:grid-cols-3" label="Loading mentors…" />
        </div>
      </div>
    </div>
  );
}
