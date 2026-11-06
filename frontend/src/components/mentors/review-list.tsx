"use client";

import { CheckCircle2, MessageSquare } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { Paginated, Review } from "@/lib/api/types";
import { getErrorMessage } from "@/lib/api/errors";
import { api } from "@/lib/data/client";
import { formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { RatingStars } from "./rating-display";

export function ReviewList({ mentorId, initial }: { mentorId: string; initial: Paginated<Review> }) {
  const [reviews, setReviews] = useState(initial.results);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(initial.next !== null);
  const [loading, setLoading] = useState(false);

  async function loadMore() {
    setLoading(true);
    try {
      const next = await api.mentors.reviews(mentorId, page + 1);
      setReviews((current) => [...current, ...next.results]);
      setPage((p) => p + 1);
      setHasMore(next.next !== null);
    } catch (error) {
      toast.error("Couldn't load more reviews", { description: getErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  if (reviews.length === 0) {
    return (
      <EmptyState
        icon={MessageSquare}
        title="No reviews yet"
        description="Reviews appear here after students complete a session with this mentor."
      />
    );
  }

  return (
    <div>
      <ul className="grid gap-4">
        {reviews.map((review) => (
          <li key={review.id} className="rounded-xl border bg-card p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <RatingStars value={review.rating} />
              <time dateTime={review.created_at} className="text-sm text-muted-foreground">
                {formatDate(review.created_at, "UTC")}
              </time>
            </div>
            <p className="mt-3">{review.comment}</p>
            <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{review.reviewer_display_name}</span>
              <span aria-hidden="true">·</span>
              <span>{review.service_title}</span>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1 text-success">
                <CheckCircle2 className="size-3.5" aria-hidden="true" />
                Completed session
              </span>
            </p>
          </li>
        ))}
      </ul>
      {hasMore ? (
        <Button variant="outline" className="mt-4" onClick={loadMore} disabled={loading}>
          {loading ? "Loading…" : "Show more reviews"}
        </Button>
      ) : null}
    </div>
  );
}
