import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import Link from "next/link";
import { getErrorMessage, isApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function ErrorState({
  error,
  title,
  onRetry,
  retryHref,
  className,
}: {
  error?: unknown;
  title?: string;
  /** Client Components: retry in place. */
  onRetry?: () => void;
  /** Server Components: reload the current URL. */
  retryHref?: string;
  className?: string;
}) {
  const isNetwork = isApiError(error) && error.kind === "network";
  const Icon = isNetwork ? WifiOff : AlertTriangle;
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center rounded-xl border border-destructive/20 bg-destructive/5 px-6 py-10 text-center",
        className,
      )}
    >
      <Icon className="mb-3 size-8 text-destructive" aria-hidden="true" />
      <h3 className="text-base font-semibold">
        {title ?? (isNetwork ? "Connection problem" : "We couldn't load this")}
      </h3>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{getErrorMessage(error)}</p>
      {onRetry ? (
        <Button variant="outline" className="mt-5" onClick={onRetry}>
          <RefreshCw aria-hidden="true" />
          Try again
        </Button>
      ) : retryHref ? (
        <Button asChild variant="outline" className="mt-5">
          <Link href={retryHref}>
            <RefreshCw aria-hidden="true" />
            Try again
          </Link>
        </Button>
      ) : null}
    </div>
  );
}
