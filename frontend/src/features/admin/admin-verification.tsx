"use client";

import { BadgeCheck, ExternalLink } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { VerificationRequest, VerificationRequestStatus } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { countryName, formatDateTime, pluralize } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/common/page-header";
import { Pager } from "@/components/common/pager";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge } from "@/components/common/status-badge";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { MentorAvatar } from "@/components/mentors/mentor-avatar";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";

const TABS: { value: VerificationRequestStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

export function AdminVerification() {
  const { user } = useCurrentUser();
  const [status, setStatus] = useState<VerificationRequestStatus>("pending");
  const [action, setAction] = useState<{ type: "approve" | "reject"; request: VerificationRequest } | null>(null);
  const [page, setPage] = useState(1);
  const query = useApiQuery(`admin:verification:${status}:${page}`, () => api.admin.verificationRequests(status, page));

  const remove = (id: string) =>
    query.mutate((page) => ({ ...page, count: page.count - 1, results: page.results.filter((r) => r.id !== id) }));

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Mentor verification"
        description="Approve mentors before their profiles become visible. Approval is what grants the Verified badge."
      />
      <Tabs value={status} onValueChange={(v) => {
          setStatus(v as VerificationRequestStatus);
          setPage(1);
        }}>
        <TabsList>
          {TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} className="px-3">
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <QueryView query={query} errorTitle="Couldn't load verification requests">
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState icon={BadgeCheck} title={status === "pending" ? "No profiles waiting for review" : `No ${status} requests`} />
          ) : (
            <ul className="grid grid-cols-1 gap-4">
              {page.results.map((request) => (
                <li key={request.id} className="rounded-xl border bg-card p-5">
                  <div className="flex flex-wrap items-start gap-4">
                    <MentorAvatar name={request.mentor.display_name} src={null} size="md" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="font-semibold">{request.mentor.display_name}</h2>
                        <StatusBadge tone={request.status === "approved" ? "success" : request.status === "rejected" ? "danger" : "info"}>
                          {TABS.find((t) => t.value === request.status)?.label ?? request.status}
                        </StatusBadge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {request.mentor.current_title}
                        {request.mentor.current_company ? ` at ${request.mentor.current_company}` : ""} ·{" "}
                        {pluralize(request.mentor.years_experience, "year")} · {countryName(request.mentor.country)}
                      </p>
                      <p className="mt-1 text-sm">{request.mentor.headline}</p>
                    </div>
                  </div>
                  <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-muted-foreground">Submitted</dt>
                      <dd>{formatDateTime(request.submitted_at, user.timezone)}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">LinkedIn</dt>
                      <dd>
                        {request.mentor.linkedin_url ? (
                          <a
                            href={request.mentor.linkedin_url}
                            target="_blank"
                            rel="noopener noreferrer nofollow"
                            className="inline-flex items-center gap-1 text-primary hover:underline"
                          >
                            Open profile <ExternalLink className="size-3.5" aria-hidden="true" />
                            <span className="sr-only">(opens in a new tab)</span>
                          </a>
                        ) : (
                          "Not provided"
                        )}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-muted-foreground">Notes from the mentor</dt>
                      <dd>{request.evidence_note || "None"}</dd>
                    </div>
                    {request.decision_reason ? (
                      <div className="sm:col-span-2">
                        <dt className="text-muted-foreground">Decision reason</dt>
                        <dd>{request.decision_reason}</dd>
                      </div>
                    ) : null}
                  </dl>
                  {request.status === "pending" ? (
                    <div className="mt-4 flex flex-wrap gap-2 border-t pt-4">
                      <Button size="sm" onClick={() => setAction({ type: "approve", request })}>
                        Approve
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setAction({ type: "reject", request })}>
                        Reject
                      </Button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
      <Pager page={page} count={query.data?.count ?? 0} onPageChange={setPage} />

      <ConfirmationDialog
        open={action?.type === "approve"}
        onOpenChange={(o) => !o && setAction(null)}
        title={`Approve ${action?.request.mentor.display_name ?? "mentor"}?`}
        description="Their profile will appear in search with a Verified badge, and they'll be notified by email."
        confirmLabel="Approve mentor"
        onConfirm={async () => {
          if (!action) return;
          await api.admin.approveVerification(action.request.id);
          remove(action.request.id);
          toast.success("Mentor approved");
        }}
      />
      <ConfirmationDialog
        open={action?.type === "reject"}
        onOpenChange={(o) => !o && setAction(null)}
        title={`Reject ${action?.request.mentor.display_name ?? "mentor"}?`}
        description="The mentor will see your feedback and can update their profile and resubmit."
        confirmLabel="Reject"
        destructive
        reason={{ label: "Feedback for the mentor", placeholder: "Explain what needs to change.", required: true }}
        onConfirm={async (reason) => {
          if (!action) return;
          await api.admin.rejectVerification(action.request.id, reason);
          remove(action.request.id);
          toast.success("Feedback sent to the mentor");
        }}
      />
      <AdminSecurityNote />
    </div>
  );
}
