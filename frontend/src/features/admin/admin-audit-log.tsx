"use client";

import { ScrollText } from "lucide-react";
import { useId, useState } from "react";
import { api } from "@/lib/data/client";
import { formatDateTime } from "@/lib/format";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { EmptyState } from "@/components/feedback/empty-state";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";
import { Pager } from "@/components/common/pager";

export function AdminAuditLog() {
  const { user } = useCurrentUser();
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const filterId = useId();
  const filter = action.trim();
  const query = useApiQuery(`admin:audit:${filter}:${page}`, () =>
    api.admin.auditLog({ action: filter || undefined, page }),
  );

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Audit log"
        description="Every administrative action and payment event that needs a trail: who did what, to which record, and when. Entries can't be edited or deleted."
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor={filterId} className="text-sm whitespace-nowrap text-muted-foreground">
              Action starts with
            </label>
            <Input
              id={filterId}
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
              placeholder="e.g. payment."
              className="w-44"
            />
          </div>
        }
      />
      <QueryView query={query} errorTitle="Couldn't load the audit log">
        {(result) =>
          result.results.length === 0 ? (
            <EmptyState icon={ScrollText} title="No audit entries match" />
          ) : (
            <>
              <div className="rounded-xl border bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>When</TableHead>
                      <TableHead>Actor</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Target</TableHead>
                      <TableHead>Details</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.results.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="whitespace-nowrap">{formatDateTime(entry.created_at, user.timezone)}</TableCell>
                        <TableCell>{entry.actor_name || "System"}</TableCell>
                        <TableCell className="font-mono text-xs">{entry.action}</TableCell>
                        <TableCell className="font-mono text-xs">
                          {entry.target_type}
                          <span className="block text-muted-foreground">{entry.target_id}</span>
                        </TableCell>
                        <TableCell className="max-w-80 font-mono text-xs break-all text-muted-foreground">
                          {entry.metadata && Object.keys(entry.metadata as object).length ? JSON.stringify(entry.metadata) : "—"}
                        </TableCell>
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
