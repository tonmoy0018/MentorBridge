"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { PackagePurchase } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { cn } from "@/lib/utils";

const POLL_MS = 2_000;
const MAX_POLLS = 15;

/**
 * Shown when the student comes back from checkout (`?checkout=<purchase id>`). The return itself
 * proves nothing: this re-reads the purchase, which becomes `active` only when the backend has
 * verified the provider's signed notification.
 */
export function PackageCheckoutNotice({ onSettled }: { onSettled: () => void }) {
  const params = useSearchParams();
  const purchaseId = params.get("checkout");
  const cancelled = params.get("cancelled") === "1";
  const [purchase, setPurchase] = useState<PackagePurchase | null>(null);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    if (!purchaseId || cancelled) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let polls = 0;
    const check = async () => {
      polls += 1;
      const current = await api.student.package(purchaseId).catch(() => null);
      if (stopped) return;
      if (current) setPurchase(current);
      if (current && current.status !== "pending_payment") {
        onSettled();
        return;
      }
      if (polls >= MAX_POLLS) {
        setGaveUp(true);
        return;
      }
      timer = setTimeout(check, POLL_MS);
    };
    void check();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
    // `onSettled` is a stable reload callback; polling only depends on the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [purchaseId, cancelled]);

  if (!purchaseId) return null;

  const [tone, text] = cancelled
    ? ["info", "Payment was cancelled. You haven't been charged; you can choose the option again any time."]
    : purchase?.status === "active"
      ? ["success", `Payment confirmed. ${purchase.title} is ready: book your first session.`]
      : purchase && purchase.status !== "pending_payment"
        ? ["warning", "This purchase didn't go through. You haven't been charged."]
        : gaveUp
          ? [
              "warning",
              "We haven't received confirmation from the payment provider yet. This page will show the package as soon as it arrives.",
            ]
          : ["info", "Confirming your payment with the payment provider…"];

  return (
    <p
      role="status"
      className={cn(
        "rounded-lg p-4 text-sm",
        tone === "success" && "bg-success-soft text-success",
        tone === "info" && "bg-info-soft text-info",
        tone === "warning" && "bg-warning-soft text-warning",
      )}
    >
      {text}
    </p>
  );
}
