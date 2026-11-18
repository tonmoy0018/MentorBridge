"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import type { MentorPackage, SessionFormat } from "@/lib/api/types";
import { isApiError } from "@/lib/api/errors";
import { goToCheckout } from "@/lib/checkout";
import { api } from "@/lib/data/client";
import { formatDuration, formatMoney } from "@/lib/format";
import { FORMAT_LABEL, packagePrice, packageSaving, perSessionPrice } from "@/lib/sessions";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { loginRedirectPath } from "@/hooks/use-api-error-handler";

/**
 * Buy a multi-session option. Payment happens on the provider's page; the bundle becomes usable
 * only when the backend has verified the provider's notification, never because of the redirect.
 */
export function BundleCheckout({
  bundle,
  format,
  mentorSlug,
  mentorFirstName,
  paymentsEnabled,
  paymentsLivemode,
}: {
  bundle: MentorPackage;
  format: SessionFormat;
  mentorSlug: string;
  mentorFirstName: string;
  paymentsEnabled: boolean;
  paymentsLivemode: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const price = packagePrice(bundle, format);
  const saving = packageSaving(bundle, format);
  const each = perSessionPrice(bundle, format);
  if (!price) return null;
  const paid = price.amount_cents > 0;
  const blocked = paid && !paymentsEnabled;

  async function buy() {
    let result;
    try {
      result = await api.student.buyPackage(bundle.id, format);
    } catch (error) {
      if (isApiError(error) && error.kind === "unauthenticated") {
        router.push(loginRedirectPath(pathname));
        return;
      }
      if (isApiError(error) && error.kind === "forbidden" && error.code === "permission_denied") {
        throw new Error("Only student accounts can buy sessions.");
      }
      throw error;
    }
    if (result.checkout_url) {
      goToCheckout(result.checkout_url);
      await new Promise(() => {}); // keep the dialog busy while the browser leaves
      return;
    }
    router.push(`/mentors/${encodeURIComponent(mentorSlug)}?package=${encodeURIComponent(result.purchase.id)}#book`);
    router.refresh();
  }

  return (
    <div className="grid min-w-0 gap-4">
      <div className="rounded-lg bg-muted/60 p-4 text-sm">
        <p>
          <span className="font-medium">{bundle.title}</span> · {formatDuration(bundle.service.duration_minutes)} each ·{" "}
          {FORMAT_LABEL[format]}
        </p>
        <p className="mt-1">
          <span className="font-semibold">{formatMoney(price)}</span>
          {each ? <span className="text-muted-foreground"> · {formatMoney(each)} per session</span> : null}
          {saving ? <span className="text-muted-foreground"> · you save {formatMoney(saving)}</span> : null}
        </p>
        <p className="mt-2 text-muted-foreground">
          Pay once, then book each session when it suits you within {bundle.validity_days} days.
        </p>
      </div>
      {blocked ? (
        <p role="note" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
          Online payment isn&apos;t available yet, so sessions can&apos;t be bought. Please check back soon.
        </p>
      ) : null}
      <Button size="lg" disabled={blocked} onClick={() => setConfirmOpen(true)}>
        Buy {bundle.session_count} sessions
      </Button>
      <ConfirmationDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={paid ? "Continue to payment?" : "Get these sessions?"}
        description={
          paid
            ? `You'll pay ${formatMoney(price)} on our payment provider's secure page. Your ${bundle.session_count} sessions with ${mentorFirstName} are ready to book once the payment is confirmed.`
            : `Your ${bundle.session_count} sessions with ${mentorFirstName} are ready to book straight away.`
        }
        confirmLabel={paid ? "Continue to payment" : "Get sessions"}
        onConfirm={buy}
      >
        {paid && !paymentsLivemode ? (
          <p role="note" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
            Test mode: payments run in the provider&apos;s sandbox. Use a test card; no real money is taken.
          </p>
        ) : null}
      </ConfirmationDialog>
    </div>
  );
}
