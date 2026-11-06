import { Button } from "@/components/ui/button";

const PAGE_SIZE = 20; // the API's default page size

/** Previous/next paging for client-side admin lists. */
export function Pager({ page, count, onPageChange }: { page: number; count: number; onPageChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  if (pages === 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-end gap-3 text-sm">
      <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        Previous
      </Button>
      <span className="tabular-nums text-muted-foreground">
        Page {page} of {pages}
      </span>
      <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
        Next
      </Button>
    </nav>
  );
}
