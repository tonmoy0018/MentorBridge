"use client";

import { CreditCard, Undo2 } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";
import type {
  DisputeStatus,
  PaymentRecord,
  PaymentStatus,
  RefundReason,
  RefundRecordStatus,
  RefundStatus,
} from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDate, formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, SectionHeading } from "@/components/common/page-header";
import { Pager } from "@/components/common/pager";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge, type Tone } from "@/components/common/status-badge";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { NativeSelect } from "@/components/forms/native-select";
import { useApiQuery } from "@/hooks/use-api-query";
import { AdminSecurityNote } from "./admin-note";

export const PAYMENT_STATUS: Record<PaymentStatus, { label: string; tone: Tone }> = {
  created: { label: "Checkout started", tone: "neutral" },
  authorized: { label: "Authorised", tone: "info" },
  captured: { label: "Captured", tone: "success" },
  failed: { label: "Attempt failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export const REFUND_STATUS: Record<RefundStatus, { label: string; tone: Tone }> = {
  none: { label: "—", tone: "neutral" },
  pending: { label: "Refund pending", tone: "warning" },
  partial: { label: "Partly refunded", tone: "warning" },
  full: { label: "Refunded", tone: "neutral" },
  failed: { label: "Refund failed", tone: "danger" },
};

const DISPUTE: Record<Exclude<DisputeStatus, "none">, { label: string; tone: Tone }> = {
  open: { label: "Dispute open", tone: "danger" },
  won: { label: "Dispute won", tone: "success" },
  lost: { label: "Dispute lost", tone: "danger" },
};

const REFUND_RECORD: Record<RefundRecordStatus, { label: string; tone: Tone }> = {
  pending: { label: "Pending", tone: "warning" },
  succeeded: { label: "Succeeded", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

const REFUND_REASON: Record<RefundReason, string> = {
  student_cancellation: "Student cancelled",
  mentor_cancellation: "Mentor cancelled",
  admin: "Admin",
  dispute_lost: "Dispute lost",
  system: "Automatic (booking didn't go ahead)",
};

const money = (m: Parameters<typeof formatMoney>[0]) => formatMoney(m, { showFree: false });
const percent = (bps: number) => `${(bps / 100).toLocaleString("en-US", { maximumFractionDigits: 2 })}%`;

export function AdminPayments() {
  const { user } = useCurrentUser();
  const [status, setStatus] = useState<PaymentStatus | "">("");
  const [refunding, setRefunding] = useState<PaymentRecord | null>(null);
  const [page, setPage] = useState(1);
  const [refundPage, setRefundPage] = useState(1);
  const query = useApiQuery(`admin:payments:${status}:${page}`, () =>
    api.admin.payments({ status: status || undefined, page }),
  );
  const refunds = useApiQuery(`admin:refunds:${refundPage}`, () => api.admin.refunds(refundPage));

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Payments & refunds"
        description="Written only from verified payment-provider data; nothing here can mark a booking as paid. Test-mode (sandbox) payments are labelled and never counted as revenue."
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="payment-status" className="text-sm whitespace-nowrap text-muted-foreground">
              Status
            </label>
            <NativeSelect
              id="payment-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as PaymentStatus | "");
                setPage(1);
              }}
              className="w-44"
            >
              <option value="">All statuses</option>
              {(Object.keys(PAYMENT_STATUS) as PaymentStatus[]).map((s) => (
                <option key={s} value={s}>
                  {PAYMENT_STATUS[s].label}
                </option>
              ))}
            </NativeSelect>
          </div>
        }
      />
      <QueryView query={query} errorTitle="Couldn't load payments">
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState icon={CreditCard} title="No payments match this filter" />
          ) : (
            <div className="rounded-xl border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Student → mentor</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Commission</TableHead>
                    <TableHead className="text-right">Mentor share</TableHead>
                    <TableHead className="text-right">Provider fee</TableHead>
                    <TableHead className="text-right">Refunded</TableHead>
                    <TableHead>
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {page.results.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="whitespace-nowrap">{formatDate(p.created_at, user.timezone)}</TableCell>
                      <TableCell>
                        {p.student_display_name} → {p.mentor_display_name}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          <StatusBadge tone={PAYMENT_STATUS[p.status].tone}>{PAYMENT_STATUS[p.status].label}</StatusBadge>
                          {p.refund_status !== "none" ? (
                            <StatusBadge tone={REFUND_STATUS[p.refund_status].tone}>
                              {REFUND_STATUS[p.refund_status].label}
                            </StatusBadge>
                          ) : null}
                          {p.dispute_status !== "none" ? (
                            <StatusBadge tone={DISPUTE[p.dispute_status].tone}>{DISPUTE[p.dispute_status].label}</StatusBadge>
                          ) : null}
                          {!p.livemode ? <StatusBadge tone="warning">Test mode</StatusBadge> : null}
                        </div>
                        {p.failure_code ? (
                          <p className="mt-1 font-mono text-xs text-muted-foreground">{p.failure_code}</p>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{money(p.amount)}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {money(p.platform_fee)}{" "}
                        <span className="text-xs text-muted-foreground">({percent(p.commission_bps)})</span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{money(p.mentor_share)}</TableCell>
                      <TableCell className="text-right tabular-nums">{p.provider_fee ? money(p.provider_fee) : "—"}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {p.refunded.amount_cents ? money(p.refunded) : "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        {p.status === "captured" && p.refundable.amount_cents > 0 ? (
                          <Button size="sm" variant="outline" onClick={() => setRefunding(p)}>
                            <Undo2 aria-hidden="true" />
                            Refund
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

      <section aria-labelledby="refunds-heading" className="grid grid-cols-1 gap-3">
        <SectionHeading id="refunds-heading" title="Refunds" />
        <QueryView query={refunds} errorTitle="Couldn't load refunds">
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState icon={Undo2} title="No refunds yet" />
            ) : (
              <div className="rounded-xl border bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead className="text-right">Commission reversed</TableHead>
                      <TableHead className="text-right">Mentor share reversed</TableHead>
                      <TableHead>Note</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {page.results.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="whitespace-nowrap">{formatDate(r.created_at, user.timezone)}</TableCell>
                        <TableCell>
                          {REFUND_REASON[r.reason]}
                          {r.initiated_by_name ? (
                            <span className="block text-xs text-muted-foreground">by {r.initiated_by_name}</span>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <StatusBadge tone={REFUND_RECORD[r.status].tone}>{REFUND_RECORD[r.status].label}</StatusBadge>
                          {r.failure_code ? (
                            <p className="mt-1 font-mono text-xs text-muted-foreground">{r.failure_code}</p>
                          ) : null}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{money(r.amount)}</TableCell>
                        <TableCell className="text-right tabular-nums">{money(r.commission_reversed)}</TableCell>
                        <TableCell className="text-right tabular-nums">{money(r.mentor_share_reversed)}</TableCell>
                        <TableCell className="max-w-64 text-sm text-muted-foreground">{r.note || "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )
          }
        </QueryView>
        <Pager page={refundPage} count={refunds.data?.count ?? 0} onPageChange={setRefundPage} />
      </section>

      {refunding ? (
        <RefundDialog
          payment={refunding}
          onClose={() => setRefunding(null)}
          onDone={() => {
            query.reload();
            refunds.reload();
          }}
        />
      ) : null}
      <AdminSecurityNote />
    </div>
  );
}

/** Amount in major units ("12.50") → minor units, or null if invalid. Empty = full remaining amount. */
export function parseRefundAmount(text: string, maxCents: number): number | null | undefined {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  const cents = Math.round(Number(trimmed) * 100);
  return cents >= 1 && cents <= maxCents ? cents : null;
}

function RefundDialog({ payment, onClose, onDone }: { payment: PaymentRecord; onClose: () => void; onDone: () => void }) {
  const [amount, setAmount] = useState("");
  const amountId = useId();
  const parsed = parseRefundAmount(amount, payment.refundable.amount_cents);

  return (
    <ConfirmationDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title="Refund this payment?"
      description={`The refund is sent through ${payment.provider} and recorded when the provider confirms it. Up to ${money(payment.refundable)} can be refunded. Commission and mentor share are reversed in proportion.`}
      confirmLabel="Issue refund"
      destructive
      reason={{ label: "Note (recorded in the audit log)", required: true }}
      onConfirm={async (note) => {
        if (parsed === null) throw new Error(`Enter an amount between 0.01 and ${money(payment.refundable)}.`);
        const refund = await api.admin.refundPayment(payment.id, { amount_cents: parsed, note });
        toast.success(refund.status === "failed" ? "The provider rejected the refund" : "Refund sent to the provider", {
          description: refund.status === "failed" ? refund.failure_code : undefined,
        });
        onDone();
      }}
    >
      <div className="grid gap-2">
        <Label htmlFor={amountId}>
          Amount in {payment.amount.currency}{" "}
          <span className="font-normal text-muted-foreground">(leave empty to refund {money(payment.refundable)})</span>
        </Label>
        <Input
          id={amountId}
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder={(payment.refundable.amount_cents / 100).toFixed(2)}
          aria-invalid={parsed === null}
        />
        {!payment.livemode ? (
          <p className="text-xs text-warning">Test-mode payment: the refund happens in the provider&apos;s sandbox.</p>
        ) : null}
      </div>
    </ConfirmationDialog>
  );
}
