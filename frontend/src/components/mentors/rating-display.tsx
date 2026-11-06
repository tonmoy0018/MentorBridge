import { Star } from "lucide-react";
import { pluralize } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Average rating with review count. Shows "No reviews yet" rather than a made-up score. */
export function RatingDisplay({
  rating,
  count,
  className,
  size = "sm",
}: {
  /** Decimal string from the API, e.g. "4.80"; null when there are no reviews. */
  rating: string | null;
  count: number;
  className?: string;
  size?: "sm" | "md";
}) {
  if (rating === null || count === 0) {
    return <span className={cn("text-sm text-muted-foreground", className)}>No reviews yet</span>;
  }
  const value = Number(rating).toFixed(1);
  return (
    <span
      className={cn("inline-flex items-center gap-1", size === "md" ? "text-base" : "text-sm", className)}
    >
      <Star className={cn("fill-rating text-rating", size === "md" ? "size-5" : "size-4")} aria-hidden="true" />
      <span className="sr-only">
        Rated {value} out of 5 from {pluralize(count, "review")}
      </span>
      <span aria-hidden="true" className="font-semibold">
        {value}
      </span>
      <span aria-hidden="true" className="text-muted-foreground">
        ({pluralize(count, "review")})
      </span>
    </span>
  );
}

/** Five-star row for an individual review. */
export function RatingStars({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-0.5", className)} role="img" aria-label={`${value} out of 5 stars`}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className={cn("size-4", i < value ? "fill-rating text-rating" : "text-border")}
          aria-hidden="true"
        />
      ))}
    </span>
  );
}
