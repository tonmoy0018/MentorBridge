import "server-only";
import { connection } from "next/server";
import { redirect } from "next/navigation";
import { cache } from "react";
import type { DataApi } from "@/lib/api/contract";
import { isApiError } from "@/lib/api/errors";
import { createLiveAuthApi, createLiveDataApi } from "@/lib/api/live";
import { createServerTransport } from "@/lib/api/server-transport";
import type { CurrentUser, Role } from "@/lib/api/types";
import { canUseDashboard, dashboardPathFor } from "@/lib/routes";

/**
 * Data access for Server Components. Marks the render as request-time (marketplace data
 * changes constantly), so callers must sit inside a <Suspense> boundary.
 */
export async function getServerApi(): Promise<DataApi> {
  await connection();
  return createLiveDataApi(createServerTransport());
}

/**
 * The signed-in user from Django (`GET /auth/me/`), or null. Reads the session cookie, so
 * callers must sit behind <Suspense>.
 */
export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
  await connection();
  try {
    return await createLiveAuthApi(createServerTransport()).me();
  } catch (error) {
    if (isApiError(error) && (error.kind === "unauthenticated" || error.kind === "forbidden")) {
      return null;
    }
    throw error;
  }
});

/**
 * Gate for dashboard sections, based only on the user returned by Django. The API enforces
 * the same rules on every request; this only decides which screen to render.
 */
export async function requireRole(role: Role, nextPath: string): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(nextPath)}`);
  if (!canUseDashboard(user, role)) {
    // An admin-role account without admin permissions has no dashboard of its own.
    redirect(user.role === role ? "/" : dashboardPathFor(user.role));
  }
  return user;
}
