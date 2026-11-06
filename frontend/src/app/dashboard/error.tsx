"use client";

import { ErrorState } from "@/components/feedback/error-state";

/** Shown when a dashboard page fails to render (e.g. the API is down or timed out). */
export default function DashboardError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="container-page py-16">
      <ErrorState title="We couldn't load your dashboard" onRetry={reset} />
    </div>
  );
}
