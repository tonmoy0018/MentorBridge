"use client";

import type { ReactNode } from "react";
import type { QueryState } from "@/hooks/use-api-query";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/loading-state";

/** Renders loading / error / success for a useApiQuery result. */
export function QueryView<T>({
  query,
  loading,
  errorTitle,
  children,
}: {
  query: QueryState<T> & { reload: () => void };
  loading?: ReactNode;
  errorTitle?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.status === "error") {
    return <ErrorState error={query.error} title={errorTitle} onRetry={query.reload} />;
  }
  if (query.status === "loading" && query.data === undefined) {
    return <>{loading ?? <CardListSkeleton count={2} />}</>;
  }
  return <>{children(query.data as T)}</>;
}
