"use client";

import { Banknote, Clock, Landmark, TrendingUp } from "lucide-react";
import type { LedgerKind, PayoutStatus } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDate, formatMoney } from "@/lib/format";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, SectionHeading } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatCard } from "@/components/common/stat-card";
import { StatusBadge, type Tone } from "@/components/common/status-badge";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { EmptyState } from "@/components/feedback/empty-state";
import { useApiQuery } from "@/hooks/use-api-query";

const LEDGER_LABEL: Record<LedgerKind, string> = {
  earning: "Session earning",
  refund_reversal: "Refund",
  payout: "Payout",
  adjustment: "Adjustment",
};

const PAYOUT_STATUS: Record<PayoutStatus, { label: string; tone: Tone }> = {
  pending: { label: "Pending", tone: "warning" },
  paid: { label: "Paid", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

const money = (m: Parameters<typeof formatMoney>[0]) => formatMoney(m, { showFree: false });

export function Earnings() {
  const { user } = useCurrentUser();
  const summary = useApiQuery("mentor:earnings", () => api.mentor.earningsSummary());
  const ledger = useApiQuery("mentor:ledger", () => api.mentor.ledger());
  const payouts = useApiQuery("mentor:payouts", () => api.mentor.payouts());
  const profile = useApiQuery("mentor:profile", () => api.mentor.profile());
  const rate =
    profile.status === "success" ? `${(profile.data.commission_bps / 100).toLocaleString("en-US", { maximumFractionDigits: 2 })}%` : null;

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader
        title="Earnings"
        description={`Earnings are recorded when a paid session is accepted and become available after it's completed. Amounts are your share after the platform commission${rate ? ` (${rate})` : ""}; refunds reduce them proportionally. Payouts are made manually by MentorBridge; there are no automatic payouts.`}
      />

      <QueryView query={summary} errorTitle="Couldn't load your earnings summary">
        {(s) => (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Available" value={money(s.available)} hint="Ready for the next payout" icon={Banknote} />
            <StatCard label="Pending" value={money(s.pending)} hint="From upcoming sessions" icon={Clock} />
            <StatCard label="Paid out" value={money(s.paid_out)} icon={Landmark} />
            <StatCard label="Lifetime earnings" value={money(s.lifetime)} icon={TrendingUp} />
          </div>
        )}
      </QueryView>

      <section aria-labelledby="ledger-heading" className="grid grid-cols-1 gap-4">
        <SectionHeading id="ledger-heading" title="Activity" />
        <QueryView query={ledger} errorTitle="Couldn't load earnings activity">
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState icon={Banknote} title="No earnings yet" description="Earnings appear here once you accept a paid booking." />
            ) : (
              <div className="rounded-xl border bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Available from</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {page.results.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="whitespace-nowrap">{formatDate(entry.created_at, user.timezone)}</TableCell>
                        <TableCell>{LEDGER_LABEL[entry.kind]}</TableCell>
                        <TableCell className="min-w-56">{entry.description}</TableCell>
                        <TableCell className="whitespace-nowrap">
                          {entry.available_at ? formatDate(entry.available_at, user.timezone) : "—"}
                        </TableCell>
                        <TableCell
                          className={`text-right font-medium tabular-nums ${entry.amount.amount_cents < 0 ? "text-muted-foreground" : ""}`}
                        >
                          {money(entry.amount)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )
          }
        </QueryView>
      </section>

      <section aria-labelledby="payouts-heading" className="grid grid-cols-1 gap-4">
        <SectionHeading
          id="payouts-heading"
          title="Payouts"
          description="MentorBridge pays out your available balance. Each payout lists its bank or transfer reference."
        />
        <QueryView query={payouts} errorTitle="Couldn't load payouts">
          {(page) =>
            page.results.length === 0 ? (
              <EmptyState icon={Landmark} title="No payouts yet" />
            ) : (
              <div className="rounded-xl border bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Created</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Reference</TableHead>
                      <TableHead>Paid on</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {page.results.map((payout) => (
                      <TableRow key={payout.id}>
                        <TableCell className="whitespace-nowrap">{formatDate(payout.created_at, user.timezone)}</TableCell>
                        <TableCell>
                          <StatusBadge tone={PAYOUT_STATUS[payout.status].tone}>{PAYOUT_STATUS[payout.status].label}</StatusBadge>
                        </TableCell>
                        <TableCell className="font-mono text-xs">{payout.external_reference || "—"}</TableCell>
                        <TableCell className="whitespace-nowrap">
                          {payout.paid_at ? formatDate(payout.paid_at, user.timezone) : "—"}
                        </TableCell>
                        <TableCell className="text-right font-medium tabular-nums">{money(payout.amount)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )
          }
        </QueryView>
      </section>
    </div>
  );
}
