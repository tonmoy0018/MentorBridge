"use client";

import { MessageSquareText, Star } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import type { AdminReview, ReviewStatus } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge } from "@/components/common/status-badge";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";

export function AdminReviews() {
  const { user } = useCurrentUser();
  const [tab, setTab] = useState<ReviewStatus>("published");
  const [acting, setActing] = useState<AdminReview | null>(null);
  const query = useApiQuery(`admin:reviews:${tab}`, () => api.admin.reviews({ status: tab }));

  const removeFromList = (id: string) =>
    query.mutate((p) => ({ ...p, count: p.count - 1, results: p.results.filter((r) => r.id !== id) }));

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Reviews"
        description="Hide reviews that break the content rules. Hidden reviews leave the mentor's profile and rating; publishing restores them."
      />
      <Tabs value={tab} onValueChange={(v) => setTab(v as ReviewStatus)}>
        <TabsList>
          <TabsTrigger value="published" className="px-3">
            Published
          </TabsTrigger>
          <TabsTrigger value="hidden" className="px-3">
            Hidden
          </TabsTrigger>
        </TabsList>
      </Tabs>
      <QueryView query={query} errorTitle="Couldn't load reviews">
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState icon={MessageSquareText} title={tab === "published" ? "No published reviews" : "No hidden reviews"} />
          ) : (
            <ul className="grid grid-cols-1 gap-4">
              {page.results.map((review) => (
                <li key={review.id} className="rounded-xl border bg-card p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex items-center gap-1 font-semibold" aria-label={`${review.rating} out of 5 stars`}>
                      <Star className="size-4 fill-rating text-rating" aria-hidden="true" />
                      {review.rating}
                    </span>
                    <span className="text-sm">
                      {review.reviewer_name} on{" "}
                      <Link href={`/mentors/${review.mentor_slug}`} className="text-primary hover:underline">
                        {review.mentor_name}
                      </Link>
                    </span>
                    {review.status === "hidden" ? <StatusBadge tone="neutral">Hidden</StatusBadge> : null}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(review.created_at, user.timezone)}</p>
                  {review.comment ? <p className="mt-3 text-sm">{review.comment}</p> : null}
                  {review.hidden_reason ? (
                    <p className="mt-3 rounded-lg bg-muted/60 p-3 text-sm">
                      <span className="font-medium">Hidden because:</span> {review.hidden_reason}
                    </p>
                  ) : null}
                  <div className="mt-4 border-t pt-4">
                    {review.status === "published" ? (
                      <Button size="sm" variant="outline" onClick={() => setActing(review)}>
                        Hide review
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => setActing(review)}>
                        Publish again
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
      <ConfirmationDialog
        open={acting !== null}
        onOpenChange={(open) => !open && setActing(null)}
        title={acting?.status === "published" ? "Hide this review?" : "Publish this review again?"}
        description={
          acting?.status === "published"
            ? "It's removed from the mentor's profile and their rating is recalculated."
            : "It reappears on the mentor's profile and counts towards their rating again."
        }
        confirmLabel={acting?.status === "published" ? "Hide review" : "Publish review"}
        destructive={acting?.status === "published"}
        reason={acting?.status === "published" ? { label: "Reason (recorded in the audit log)", required: true } : undefined}
        onConfirm={async (reason) => {
          if (!acting) return;
          if (acting.status === "published") await api.admin.hideReview(acting.id, reason);
          else await api.admin.publishReview(acting.id);
          removeFromList(acting.id);
          toast.success(acting.status === "published" ? "Review hidden" : "Review published");
        }}
      />
      <AdminSecurityNote />
    </div>
  );
}
