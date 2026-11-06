"use client";

import { Search, Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import type { AdminUser, Role } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/common/page-header";
import { Pager } from "@/components/common/pager";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge } from "@/components/common/status-badge";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { ROLE_LABEL } from "@/components/dashboard/nav-config";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { NativeSelect } from "@/components/forms/native-select";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";

export function AdminUsers() {
  const { user: me } = useCurrentUser();
  const [filters, setFilters] = useState<{ q: string; role: Role | "" }>({ q: "", role: "" });
  const [target, setTarget] = useState<AdminUser | null>(null);
  const [page, setPage] = useState(1);
  const query = useApiQuery(`admin:users:${filters.q}:${filters.role}:${page}`, () =>
    api.admin.users({ q: filters.q || undefined, role: filters.role || undefined, page }),
  );

  function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setFilters({ q: String(data.get("q") ?? "").trim(), role: (String(data.get("role") ?? "") as Role | "") });
    setPage(1);
  }

  const replace = (updated: AdminUser) =>
    query.mutate((page) => ({ ...page, results: page.results.map((u) => (u.id === updated.id ? updated : u)) }));

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader title="Users" description="Search students, mentors and admins. Suspended users can't log in." />
      <form onSubmit={onSearch} role="search" aria-label="Search users" className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <label htmlFor="user-q" className="sr-only">
            Name or email
          </label>
          <Input id="user-q" name="q" type="search" placeholder="Name or email" className="pl-9" defaultValue={filters.q} />
        </div>
        <label htmlFor="user-role" className="sr-only">
          Role
        </label>
        <NativeSelect id="user-role" name="role" defaultValue={filters.role} className="sm:w-40">
          <option value="">All roles</option>
          <option value="student">Students</option>
          <option value="mentor">Mentors</option>
          <option value="admin">Admins</option>
        </NativeSelect>
        <Button type="submit">Search</Button>
      </form>

      <QueryView query={query} errorTitle="Couldn't load users">
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState icon={Users} title="No users match your search" />
          ) : (
            <div className="rounded-xl border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Joined</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {page.results.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">{u.display_name}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>{ROLE_LABEL[u.role]}</TableCell>
                      <TableCell className="whitespace-nowrap">{formatDate(u.date_joined, me.timezone)}</TableCell>
                      <TableCell>
                        {u.is_active ? <StatusBadge tone="success">Active</StatusBadge> : <StatusBadge tone="danger">Suspended</StatusBadge>}
                      </TableCell>
                      <TableCell className="text-right">
                        {u.id === me.id ? (
                          <span className="text-xs text-muted-foreground">You</span>
                        ) : (
                          <Button size="sm" variant={u.is_active ? "ghost" : "outline"} onClick={() => setTarget(u)}>
                            {u.is_active ? "Suspend" : "Reactivate"}
                            <span className="sr-only"> {u.display_name}</span>
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )
        }
      </QueryView>
      <Pager page={page} count={query.data?.count ?? 0} onPageChange={setPage} />

      <ConfirmationDialog
        open={target !== null && target.is_active}
        onOpenChange={(o) => !o && setTarget(null)}
        title={`Suspend ${target?.display_name ?? "user"}?`}
        description="They will be logged out and can't log in until reactivated. Mentors are hidden from search."
        confirmLabel="Suspend user"
        destructive
        reason={{ label: "Reason (recorded in the audit log)", required: true }}
        onConfirm={async (reason) => {
          if (!target) return;
          replace(await api.admin.suspendUser(target.id, reason));
          toast.success("User suspended");
        }}
      />
      <ConfirmationDialog
        open={target !== null && !target.is_active}
        onOpenChange={(o) => !o && setTarget(null)}
        title={`Reactivate ${target?.display_name ?? "user"}?`}
        description="They will be able to log in again."
        confirmLabel="Reactivate user"
        onConfirm={async () => {
          if (!target) return;
          replace(await api.admin.reactivateUser(target.id));
          toast.success("User reactivated");
        }}
      />
      <AdminSecurityNote />
    </div>
  );
}
