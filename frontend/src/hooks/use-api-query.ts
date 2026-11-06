"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { isApiError } from "@/lib/api/errors";
import { loginRedirectPath } from "./use-api-error-handler";

type Settled<T> =
  | { key: string; status: "success"; data: T; error: null }
  | { key: string; status: "error"; data: undefined; error: unknown };

export type QueryState<T> =
  | { status: "loading"; data: T | undefined; error: null }
  | { status: "success"; data: T; error: null }
  | { status: "error"; data: undefined; error: unknown };

/**
 * Minimal client-side data loader for dashboard screens.
 * - `key` identifies the request; changing it refetches.
 * - An expired session redirects to /login?next=… instead of rendering an error.
 * - `mutate` lets screens apply optimistic/local updates after a successful mutation.
 */
export function useApiQuery<T>(key: string, fetcher: () => Promise<T>) {
  const router = useRouter();
  const pathname = usePathname();
  const [reloadCount, setReloadCount] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const requestKey = `${key}#${reloadCount}`;

  useEffect(() => {
    let cancelled = false;
    fetcher().then(
      (data) => {
        if (!cancelled) setSettled({ key: requestKey, status: "success", data, error: null });
      },
      (error: unknown) => {
        if (cancelled) return;
        if (isApiError(error) && error.kind === "unauthenticated") {
          router.replace(loginRedirectPath(pathname, "expired"));
          return;
        }
        setSettled({ key: requestKey, status: "error", data: undefined, error });
      },
    );
    return () => {
      cancelled = true;
    };
    // `fetcher` is intentionally excluded: callers pass inline closures; `key` captures inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey]);

  const reload = useCallback(() => setReloadCount((n) => n + 1), []);

  const mutate = useCallback(
    (update: (current: T) => T) => {
      setSettled((prev) =>
        prev && prev.status === "success" ? { ...prev, data: update(prev.data) } : prev,
      );
    },
    [],
  );

  let state: QueryState<T>;
  if (!settled || settled.key !== requestKey) {
    state = {
      status: "loading",
      data: settled?.status === "success" ? settled.data : undefined,
      error: null,
    };
  } else if (settled.status === "success") {
    state = { status: "success", data: settled.data, error: null };
  } else {
    state = { status: "error", data: undefined, error: settled.error };
  }

  return { ...state, reload, mutate };
}
