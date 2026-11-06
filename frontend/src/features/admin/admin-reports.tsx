"use client";

import { Flag } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { ContentReport, ReportReason, ReportStatus } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge, type Tone } from "@/components/common/status-badge";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";

const REASON: Record<ReportReason, string> = {
  spam: "Spam",
  inappropriate: "Inappropriate",
  misleading: "Misleading",
  harassment: "Harassment",
  no_show: "No-show",
  other: "Other",
};

const STATUS: Record<ReportStatus, { label: string; tone: Tone }> = {
  open: { label: "Open", tone: "warning" },
  in_review: { label: "In review", tone: "info" },
  actioned: { label: "Actioned", tone: "success" },
  dismissed: { label: "Dismissed", tone: "neutral" },
};

export function AdminReports() {
  const { user } = useCurrentUser();
  const [tab, setTab] = useState<"open" | "resolved">("open");
  const [resolving, setResolving] = useState<{ report: ContentReport; resolution: "actioned" | "dismissed" } | null>(null);
  const [hideReview, setHideReview] = useState(true);
  const query = useApiQuery(`admin:reports:${tab}`, () => api.admin.reports(tab === "open" ? "open" : "resolved"));

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader title="Reported content" description="Reports from students and mentors about reviews, profiles and bookings." />
      <Tabs value={tab} onValueChange={(v) => setTab(v as "open" | "resolved")}>
        <TabsList>
          <TabsTrigger value="open" className="px-3">
            Needs review
          </TabsTrigger>
          <TabsTrigger value="resolved" className="px-3">
            Resolved
          </TabsTrigger>
        </TabsList>
      </Tabs>
      <QueryView query={query} errorTitle="Couldn't load reports">
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState icon={Flag} title={tab === "open" ? "No reports need review" : "No resolved reports"} />
          ) : (
            <ul className="grid grid-cols-1 gap-4">
              {page.results.map((report) => (
                <li key={report.id} className="rounded-xl border bg-card p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">{report.target_label}</h2>
                    <StatusBadge tone={STATUS[report.status].tone}>{STATUS[report.status].label}</StatusBadge>
                    <StatusBadge tone="neutral">{REASON[report.reason]}</StatusBadge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Reported by {report.reporter_display_name} · {formatDateTime(report.created_at, user.timezone)}
                  </p>
                  {report.details ? <p className="mt-3 text-sm">{report.details}</p> : null}
                  {report.resolution_note ? (
                    <p className="mt-3 rounded-lg bg-muted/60 p-3 text-sm">
                      <span className="font-medium">Resolution:</span> {report.resolution_note}
                    </p>
                  ) : null}
                  {tab === "open" ? (
                    <div className="mt-4 flex flex-wrap gap-2 border-t pt-4">
                      <Button size="sm" onClick={() => setResolving({ report, resolution: "actioned" })}>
                        Mark as actioned
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setResolving({ report, resolution: "dismissed" })}>
                        Dismiss
                      </Button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
      <ConfirmationDialog
        open={resolving !== null}
        onOpenChange={(o) => {
          if (!o) setResolving(null);
          else setHideReview(true);
        }}
        title={resolving?.resolution === "actioned" ? "Mark this report as actioned?" : "Dismiss this report?"}
        description={
          resolving?.resolution === "actioned"
            ? "Record what you did (for example, hid the review or contacted the mentor)."
            : "Record why no action is needed."
        }
        confirmLabel={resolving?.resolution === "actioned" ? "Mark actioned" : "Dismiss report"}
        reason={{ label: "Resolution note (recorded in the audit log)", required: true }}
        onConfirm={async (note) => {
          if (!resolving) return;
          const canHide = resolving.resolution === "actioned" && resolving.report.target_type === "review";
          await api.admin.resolveReport(resolving.report.id, {
            resolution: resolving.resolution,
            note,
            hide_review: canHide && hideReview,
          });
          query.mutate((p) => ({ ...p, count: p.count - 1, results: p.results.filter((r) => r.id !== resolving.report.id) }));
          toast.success("Report resolved");
        }}
      >
        {resolving?.resolution === "actioned" && resolving.report.target_type === "review" ? (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={hideReview}
              onChange={(e) => setHideReview(e.target.checked)}
            />
            Hide this review from the mentor&apos;s profile
          </label>
        ) : null}
      </ConfirmationDialog>
      <AdminSecurityNote />
    </div>
  );
}
