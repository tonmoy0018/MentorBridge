"use client";

import { Mail } from "lucide-react";
import { useState } from "react";
import type { NotificationStatus } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDateTime } from "@/lib/format";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge, type Tone } from "@/components/common/status-badge";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { EmptyState } from "@/components/feedback/empty-state";
import { NativeSelect } from "@/components/forms/native-select";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";
import { Pager } from "@/components/common/pager";

const STATUS: Record<NotificationStatus, { label: string; tone: Tone }> = {
  queued: { label: "Queued", tone: "info" },
  sent: { label: "Sent", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  skipped: { label: "Skipped", tone: "neutral" },
};

export function AdminNotifications() {
  const { user } = useCurrentUser();
  const [status, setStatus] = useState<NotificationStatus | "">("");
  const [page, setPage] = useState(1);
  const query = useApiQuery(`admin:notifications:${status}:${page}`, () =>
    api.admin.notifications({ status: status || undefined, page }),
  );

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Email delivery"
        description="Delivery status of transactional emails. Addresses and message content are deliberately not shown. Failed sends are retried automatically up to 3 times."
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="notification-status" className="text-sm whitespace-nowrap text-muted-foreground">
              Status
            </label>
            <NativeSelect
              id="notification-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as NotificationStatus | "");
                setPage(1);
              }}
              className="w-40"
            >
              <option value="">All statuses</option>
              {(Object.keys(STATUS) as NotificationStatus[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS[s].label}
                </option>
              ))}
            </NativeSelect>
          </div>
        }
      />
      <QueryView query={query} errorTitle="Couldn't load email delivery records">
        {(result) =>
          result.results.length === 0 ? (
            <EmptyState icon={Mail} title="No emails match this filter" />
          ) : (
            <>
              <div className="rounded-xl border bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Created</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Recipient</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Attempts</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.results.map((n) => (
                      <TableRow key={n.id}>
                        <TableCell className="whitespace-nowrap">{formatDateTime(n.created_at, user.timezone)}</TableCell>
                        <TableCell className="font-mono text-xs">{n.template}</TableCell>
                        <TableCell>{n.recipient_name}</TableCell>
                        <TableCell>
                          <StatusBadge tone={STATUS[n.status].tone}>{STATUS[n.status].label}</StatusBadge>
                          {n.last_error ? <span className="ml-2 font-mono text-xs text-muted-foreground">{n.last_error}</span> : null}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{n.attempts}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <Pager page={page} count={result.count} onPageChange={setPage} />
            </>
          )
        }
      </QueryView>
      <AdminSecurityNote />
    </div>
  );
}
