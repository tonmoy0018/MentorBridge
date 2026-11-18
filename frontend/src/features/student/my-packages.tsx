"use client";

import { Layers } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";
import type { PackagePurchase } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDate, formatDuration, pluralize } from "@/lib/format";
import { ROUTES } from "@/lib/routes";
import { FORMAT_LABEL } from "@/lib/sessions";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge } from "@/components/common/status-badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { MentorAvatar } from "@/components/mentors/mentor-avatar";
import { useApiQuery } from "@/hooks/use-api-query";
import { PackageCheckoutNotice } from "./package-checkout-notice";

function PackageCard({ purchase }: { purchase: PackagePurchase }) {
  const active = purchase.status === "active";
  const usable = active && !purchase.is_expired && purchase.sessions_remaining > 0;
  return (
    <li className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <MentorAvatar name={purchase.mentor.display_name} src={purchase.mentor.avatar_url} size="md" />
          <div className="min-w-0">
            <h2 className="font-semibold">{purchase.title}</h2>
            <p className="truncate text-sm text-muted-foreground">
              with{" "}
              <Link href={ROUTES.mentor(purchase.mentor.slug)} className="underline-offset-4 hover:underline">
                {purchase.mentor.display_name}
              </Link>
            </p>
          </div>
        </div>
        {purchase.status === "pending_payment" ? (
          <StatusBadge tone="warning">Awaiting payment</StatusBadge>
        ) : purchase.status === "refunded" ? (
          <StatusBadge tone="neutral">Refunded</StatusBadge>
        ) : purchase.is_expired ? (
          <StatusBadge tone="neutral">Expired</StatusBadge>
        ) : purchase.sessions_remaining === 0 ? (
          <StatusBadge tone="neutral">All used</StatusBadge>
        ) : (
          <StatusBadge tone="success">Active</StatusBadge>
        )}
      </div>

      <div className="mt-4">
        <div className="flex justify-between text-sm">
          <span>
            <span className="font-semibold">{purchase.sessions_remaining}</span> of {purchase.session_count} sessions left
          </span>
          {purchase.expires_at ? (
            <span className="text-muted-foreground">
              {purchase.is_expired ? "Expired" : "Use by"} {formatDate(purchase.expires_at)}
            </span>
          ) : null}
        </div>
        <div
          className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-label="Sessions used"
          aria-valuemin={0}
          aria-valuemax={purchase.session_count}
          aria-valuenow={purchase.sessions_used}
        >
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${(purchase.sessions_used / purchase.session_count) * 100}%` }}
          />
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          {formatDuration(purchase.duration_minutes)} sessions · {FORMAT_LABEL[purchase.format]} ·{" "}
          {pluralize(purchase.sessions_used, "session")} booked or used
        </p>
      </div>

      {purchase.status === "pending_payment" ? (
        <p className="mt-4 border-t pt-4 text-sm text-muted-foreground">
          You can book sessions once your payment is confirmed. If you didn&apos;t finish paying, choose the option
          again on {purchase.mentor.display_name}&apos;s profile.
        </p>
      ) : null}
      {usable ? (
        <div className="mt-4 border-t pt-4">
          <Button asChild size="sm">
            <Link href={`${ROUTES.mentor(purchase.mentor.slug)}?package=${encodeURIComponent(purchase.id)}#book`}>
              Book a session
            </Link>
          </Button>
        </div>
      ) : null}
    </li>
  );
}

export function MyPackages() {
  const query = useApiQuery("student:packages", () => api.student.packages());
  const reload = query.reload;

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Packages"
        description="Sessions you've got with a mentor. Book each one when it suits you, before the package expires."
      />
      <Suspense fallback={null}>
        <PackageCheckoutNotice onSettled={reload} />
      </Suspense>
      <QueryView query={query} errorTitle="Couldn't load your packages">
        {(purchases) =>
          purchases.length === 0 ? (
            <EmptyState
              icon={Layers}
              title="No packages yet"
              description="Some mentors offer packages of several sessions. You'll find them on their profiles."
              action={
                <Button asChild>
                  <Link href="/mentors">Browse mentors</Link>
                </Button>
              }
            />
          ) : (
            <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {purchases.map((purchase) => (
                <PackageCard key={purchase.id} purchase={purchase} />
              ))}
            </ul>
          )
        }
      </QueryView>
    </div>
  );
}
