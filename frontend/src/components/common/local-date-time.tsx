"use client";

import { useSyncExternalStore } from "react";
import { formatDate, formatDateTime, timeZoneLabel } from "@/lib/format";

const subscribe = () => () => {};

/** True after hydration; false during server render and the hydration pass. */
export function useIsClient(): boolean {
  return useSyncExternalStore(subscribe, () => true, () => false);
}

/**
 * Formats an instant in the visitor's own timezone. The server doesn't know that timezone,
 * so the server render shows the UTC calendar date and the browser fills in the local time.
 */
export function LocalDateTime({ iso, dateOnly }: { iso: string; dateOnly?: boolean }) {
  const isClient = useIsClient();
  if (!isClient) {
    return <time dateTime={iso}>{formatDate(iso, "UTC")}</time>;
  }
  return (
    <time dateTime={iso}>
      {dateOnly ? formatDate(iso) : `${formatDateTime(iso)} ${timeZoneLabel(undefined, new Date(iso))}`}
    </time>
  );
}
