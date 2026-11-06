"use client";

import { useEffect } from "react";

/**
 * Reloads the page when the browser restores it from the back/forward cache, e.g. after the
 * student presses Back on the payment provider's page. Without this the page reappears exactly
 * as it was left: a "Opening payment page…" button stuck in its busy state and stale data.
 */
export function useReloadOnBack() {
  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload();
    };
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, []);
}
