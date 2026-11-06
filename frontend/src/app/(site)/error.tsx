"use client";

import { ErrorState } from "@/components/feedback/error-state";

export default function SiteError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="container-page py-16">
      <ErrorState title="Something went wrong" onRetry={reset} />
    </div>
  );
}
