import type { Money } from "@/lib/api/types";
import { formatDuration, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

export function PriceDisplay({
  price,
  durationMinutes,
  from,
  className,
}: {
  price: Money | null;
  durationMinutes?: number;
  /** Prefix with "From" (for a mentor's lowest-priced service). */
  from?: boolean;
  className?: string;
}) {
  if (!price) {
    return <span className={cn("text-sm text-muted-foreground", className)}>No services yet</span>;
  }
  if (from && price.amount_cents === 0) {
    // The cheapest option is free (e.g. an intro call); other services may be paid.
    return <span className={cn("font-semibold", className)}>Free intro available</span>;
  }
  return (
    <span className={cn("inline-flex items-baseline gap-1", className)}>
      {from ? <span className="text-sm text-muted-foreground">From</span> : null}
      <span className="font-semibold">{formatMoney(price)}</span>
      {durationMinutes ? (
        <span className="text-sm text-muted-foreground">/ {formatDuration(durationMinutes)}</span>
      ) : null}
    </span>
  );
}
