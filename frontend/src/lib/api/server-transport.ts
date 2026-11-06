import "server-only";
import { cookies } from "next/headers";
import { createTransport } from "./http";

/**
 * Server-side transport for Server Components. Talks to Django directly over the internal
 * network (INTERNAL_API_URL is server-only and never shipped to the browser) and forwards
 * the incoming request's cookies so Django sees the user's session.
 */
export function createServerTransport() {
  const baseUrl = `${process.env.INTERNAL_API_URL ?? "http://localhost:8000"}/api/v1`;
  return createTransport({
    baseUrl,
    headers: async (): Promise<Record<string, string>> => {
      const cookieHeader = (await cookies()).toString();
      return cookieHeader ? { Cookie: cookieHeader } : {};
    },
    timeoutMs: 10_000,
  });
}
