"use client";

import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { Booking, BookingStatus } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDateTime, formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BookingStatusBadge, bookingStatusLabel } from "@/components/bookings/booking-status-badge";
import { PageHeader } from "@/components/common/page-header";
import { Pager } from "@/components/common/pager";
import { QueryView } from "@/components/common/query-view";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { NativeSelect } from "@/components/forms/native-select";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";

const CANCELLABLE = new Set<BookingStatus>(["pending_payment", "requested", "confirmed"]);
const STATUSES: BookingStatus[] = ["pending_payment", "requested", "confirmed", "completed", "declined", "cancelled", "expired"];

export function AdminBookings() {
  const { user } = useCurrentUser();
  const [status, setStatus] = useState<BookingStatus | "">("");
  const [cancelling, setCancelling] = useState<Booking | null>(null);
  const [refund, setRefund] = useState(true);
  const [page, setPage] = useState(1);
  const query = useApiQuery(`admin:bookings:${status}:${page}`, () =>
    api.admin.bookings({ status: status || undefined, page }),
  );

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Bookings"
        description="All bookings across the marketplace. Admins can cancel any active booking, with or without a refund of a captured payment."
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="booking-status" className="text-sm whitespace-nowrap text-muted-foreground">
              Status
            </label>
            <NativeSelect id="booking-status" value={status} onChange={(e) => {
                setStatus(e.target.value as BookingStatus | "");
                setPage(1);
              }} className="w-48">
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {bookingStatusLabel(s, "admin")}
                </option>
              ))}
            </NativeSelect>
          </div>
        }
      />
      <QueryView query={query} errorTitle="Couldn't load bookings">
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState icon={CalendarDays} title="No bookings match this filter" />
          ) : (
            <div className="rounded-xl border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Service</TableHead>
                    <TableHead>Mentor</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                    <TableHead>
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {page.results.map((b) => (
                    <TableRow key={b.id}>
                      <TableCell className="whitespace-nowrap">{formatDateTime(b.start_at, user.timezone)}</TableCell>
                      <TableCell>{b.service_title}</TableCell>
                      <TableCell>{b.mentor.display_name}</TableCell>
                      <TableCell>{b.student.display_name}</TableCell>
                      <TableCell>
                        <BookingStatusBadge status={b.status} perspective="admin" />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{formatMoney(b.price)}</TableCell>
                      <TableCell className="text-right">
                        {CANCELLABLE.has(b.status) && new Date(b.start_at).getTime() > Date.now() ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => {
                              setRefund(true);
                              setCancelling(b);
                            }}
                          >
                            Cancel
                          </Button>
                        ) : null}
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
        open={cancelling !== null}
        onOpenChange={(open) => !open && setCancelling(null)}
        title="Cancel this booking?"
        description="Both the student and the mentor are emailed. An unpaid hold or an authorised (uncaptured) payment is released; nobody is charged."
        confirmLabel="Cancel booking"
        cancelLabel="Keep booking"
        destructive
        reason={{ label: "Reason (shown to both parties and recorded in the audit log)", required: true }}
        onConfirm={async (reason) => {
          if (!cancelling) return;
          const updated = await api.admin.cancelBooking(cancelling.id, { reason, refund });
          query.mutate((page) => ({ ...page, results: page.results.map((b) => (b.id === updated.id ? updated : b)) }));
          toast.success(updated.refund_outcome === "full_refund" ? "Booking cancelled; refund sent to the provider" : "Booking cancelled");
        }}
      >
        {cancelling?.status === "confirmed" && cancelling.price.amount_cents > 0 ? (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-primary" checked={refund} onChange={(e) => setRefund(e.target.checked)} />
            Refund the captured payment in full
          </label>
        ) : null}
      </ConfirmationDialog>
      <AdminSecurityNote />
    </div>
  );
}
