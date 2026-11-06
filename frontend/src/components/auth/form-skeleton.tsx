import { Skeleton } from "@/components/ui/skeleton";

export function FormSkeleton({ fields = 2 }: { fields?: number }) {
  return (
    <div role="status" className="grid gap-5">
      <span className="sr-only">Loading form…</span>
      {Array.from({ length: fields }, (_, i) => (
        <div key={i} className="grid gap-2" aria-hidden="true">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
      <Skeleton className="h-11 w-full" aria-hidden="true" />
    </div>
  );
}
