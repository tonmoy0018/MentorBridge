import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

/** Page numbers to display, with null standing for an ellipsis gap. */
export function pageWindow(current: number, total: number): (number | null)[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const result: (number | null)[] = [];
  sorted.forEach((page, i) => {
    if (i > 0 && page - sorted[i - 1]! > 1) result.push(null);
    result.push(page);
  });
  return result;
}

/** Link-based pagination: every page has a real, shareable URL. */
export function Pagination({
  page,
  totalPages,
  hrefForPage,
  className,
}: {
  page: number;
  totalPages: number;
  hrefForPage: (page: number) => string;
  className?: string;
}) {
  if (totalPages <= 1) return null;
  const linkClass = buttonVariants({ variant: "outline", size: "default" });

  return (
    <nav aria-label="Pagination" className={cn("flex items-center justify-center gap-1", className)}>
      {page > 1 ? (
        <Link href={hrefForPage(page - 1)} className={linkClass} rel="prev">
          <ChevronLeft aria-hidden="true" />
          <span className="max-sm:sr-only">Previous</span>
        </Link>
      ) : null}
      <ul className="flex items-center gap-1">
        {pageWindow(page, totalPages).map((p, i) =>
          p === null ? (
            <li key={`gap-${i}`} aria-hidden="true" className="px-2 text-muted-foreground">
              …
            </li>
          ) : (
            <li key={p} className={cn(p !== page && Math.abs(p - page) > 1 && "max-sm:hidden")}>
              <Link
                href={hrefForPage(p)}
                aria-current={p === page ? "page" : undefined}
                aria-label={`Page ${p}`}
                className={cn(
                  buttonVariants({ variant: p === page ? "default" : "ghost", size: "icon" }),
                  "tabular-nums",
                )}
              >
                {p}
              </Link>
            </li>
          ),
        )}
      </ul>
      {page < totalPages ? (
        <Link href={hrefForPage(page + 1)} className={linkClass} rel="next">
          <span className="max-sm:sr-only">Next</span>
          <ChevronRight aria-hidden="true" />
        </Link>
      ) : null}
    </nav>
  );
}
