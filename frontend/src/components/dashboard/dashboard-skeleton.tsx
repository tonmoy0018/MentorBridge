import { Skeleton } from "@/components/ui/skeleton";

export function DashboardSkeleton() {
  return (
    <div role="status" className="flex min-h-svh flex-col bg-muted/30">
      <span className="sr-only">Loading your dashboard…</span>
      <div className="h-16 border-b bg-background" aria-hidden="true" />
      <div className="mx-auto flex w-full max-w-7xl flex-1" aria-hidden="true">
        <div className="hidden w-60 shrink-0 space-y-2 border-r p-4 lg:block">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
        <div className="flex-1 space-y-4 p-8">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    </div>
  );
}
