"use client";

import { BadgeCheck, CalendarDays, GraduationCap, Presentation } from "lucide-react";
import Link from "next/link";
import type { BookingStatus, FinanceTotals } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatMoney } from "@/lib/format";
import { BookingStatusBadge } from "@/components/bookings/booking-status-badge";
import { PageHeader, SectionHeading } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatCard } from "@/components/common/stat-card";
import { useApiQuery } from "@/hooks/use-api-query";
import { VerificationBadge } from "@/features/mentor/verification-status";
import { AdminSecurityNote } from "./admin-note";

const money = (m: Parameters<typeof formatMoney>[0]) => formatMoney(m, { showFree: false });

export function AdminOverview() {
  const stats = useApiQuery("admin:stats", () => api.admin.stats());

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title="Marketplace overview" description="Key numbers across students, mentors, bookings and payments." />
      <QueryView query={stats} errorTitle="Couldn't load marketplace statistics">
        {(s) => {
          const totalBookings = Object.values(s.bookings_by_status).reduce((a, b) => a + b, 0);
          return (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Students" value={s.users.student} icon={GraduationCap} />
                <StatCard label="Mentors" value={s.users.mentor} hint={`${s.mentors_by_status.approved} approved`} icon={Presentation} />
                <StatCard
                  label="Awaiting verification"
                  value={s.mentors_by_status.pending}
                  hint={
                    <Link href="/dashboard/admin/verification" className="text-primary hover:underline">
                      Review queue
                    </Link>
                  }
                  icon={BadgeCheck}
                />
                <StatCard label="Bookings" value={totalBookings} icon={CalendarDays} />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard label="Gross booking value" value={money(s.gross_booking_value)} hint="Live captured payments, all time" />
                <StatCard label="Net platform revenue" value={money(s.platform_fees)} hint="Commission minus refunded commission" />
                <StatCard label="Refunds" value={money(s.refunds)} />
              </div>
              <section aria-labelledby="period-heading" className="grid content-start gap-3">
                <SectionHeading
                  id="period-heading"
                  title={`${s.period.from} to ${s.period.to} (UTC)`}
                  description={`${s.period.new_users} new users · ${s.period.bookings_created} bookings created · ${s.period.sessions_completed} sessions completed`}
                />
                <FinanceRow title="Live payments" totals={s.period.live} />
                {s.period.test.captured_payments > 0 ? (
                  <FinanceRow title="Test mode (sandbox, not revenue)" totals={s.period.test} muted />
                ) : null}
              </section>
              <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
                <section aria-labelledby="bookings-status-heading" className="grid content-start gap-3">
                  <SectionHeading id="bookings-status-heading" title="Bookings by status" />
                  <ul className="divide-y rounded-xl border bg-card">
                    {(Object.entries(s.bookings_by_status) as [BookingStatus, number][]).map(([status, count]) => (
                      <li key={status} className="flex items-center justify-between p-3">
                        <BookingStatusBadge status={status} perspective="admin" />
                        <span className="font-medium tabular-nums">{count}</span>
                      </li>
                    ))}
                  </ul>
                </section>
                <section aria-labelledby="mentor-status-heading" className="grid content-start gap-3">
                  <SectionHeading id="mentor-status-heading" title="Mentor profiles by status" />
                  <ul className="divide-y rounded-xl border bg-card">
                    {(Object.entries(s.mentors_by_status) as [keyof typeof s.mentors_by_status, number][]).map(
                      ([status, count]) => (
                        <li key={status} className="flex items-center justify-between p-3">
                          <VerificationBadge status={status} />
                          <span className="font-medium tabular-nums">{count}</span>
                        </li>
                      ),
                    )}
                  </ul>
                </section>
              </div>
            </>
          );
        }}
      </QueryView>
      <AdminSecurityNote />
    </div>
  );
}

function FinanceRow({ title, totals, muted }: { title: string; totals: FinanceTotals; muted?: boolean }) {
  return (
    <div className={muted ? "grid gap-2 rounded-xl border border-dashed p-3" : "grid gap-2"}>
      <h3 className="text-sm font-medium text-muted-foreground">
        {title} · {totals.captured_payments} captured
      </h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Gross" value={money(totals.gross_booking_value)} />
        <StatCard label="Commission" value={money(totals.platform_commission)} />
        <StatCard label="Refunds" value={money(totals.refunds)} />
        <StatCard label="Net revenue" value={money(totals.net_platform_revenue)} />
        <StatCard label="Provider fees" value={money(totals.provider_fees)} hint="Borne by the platform" />
      </div>
    </div>
  );
}
