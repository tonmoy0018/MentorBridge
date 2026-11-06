"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback } from "react";
import { toast } from "sonner";
import { getErrorMessage, isApiError } from "@/lib/api/errors";

/** Path to the login page that returns the user to `pathname` afterwards. */
export function loginRedirectPath(pathname: string, reason?: "expired") {
  const params = new URLSearchParams({ next: pathname });
  if (reason) params.set("reason", reason);
  return `/login?${params.toString()}`;
}

/**
 * Returns a handler for errors from user actions (mutations): an expired session sends
 * the user to log in again; anything else shows a toast with a safe message.
 */
export function useApiErrorHandler() {
  const router = useRouter();
  const pathname = usePathname();

  return useCallback(
    (error: unknown, fallbackTitle = "Something went wrong") => {
      if (isApiError(error) && error.kind === "unauthenticated") {
        router.push(loginRedirectPath(pathname, "expired"));
        return;
      }
      toast.error(fallbackTitle, { description: getErrorMessage(error) });
    },
    [pathname, router],
  );
}
