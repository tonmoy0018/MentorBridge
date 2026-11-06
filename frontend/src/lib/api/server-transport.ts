import "server-only";
import { cookies, headers as requestHeaders } from "next/headers";
import { createTransport } from "./http";

/** Proxy headers passed on to Django so it sees the visitor's request, not this server's. */
const FORWARDED = ["x-forwarded-for", "x-forwarded-proto", "x-forwarded-host"] as const;

/**
 * Headers forwarded from the visitor's request to Django:
 * - the session cookie, so Django sees the user;
 * - X-Forwarded-For, so per-IP rate limits apply to the visitor rather than this server
 *   (otherwise every anonymous page view would share one rate-limit bucket);
 * - X-Forwarded-Proto / -Host, so Django knows the request arrived over HTTPS on the public
 *   host (no HTTPS redirect for this internal call, and absolute URLs such as avatars use the
 *   public origin).
 *
 * These are only trustworthy because Next.js is never exposed directly: the reverse proxy in
 * front of it overwrites any client-supplied values (docs/DEPLOYMENT.md).
 */
export function forwardedHeaders(cookieHeader: string, incoming: Pick<Headers, "get">): Record<string, string> {
  const result: Record<string, string> = {};
  if (cookieHeader) result.Cookie = cookieHeader;
  for (const name of FORWARDED) {
    const value = incoming.get(name);
    if (value) result[name] = value;
  }
  return result;
}

/**
 * Server-side transport for Server Components. Talks to Django directly over the internal
 * network (INTERNAL_API_URL is server-only and never shipped to the browser).
 */
export function createServerTransport() {
  const baseUrl = `${process.env.INTERNAL_API_URL ?? "http://localhost:8000"}/api/v1`;
  return createTransport({
    baseUrl,
    headers: async (): Promise<Record<string, string>> => {
      const [jar, incoming] = await Promise.all([cookies(), requestHeaders()]);
      return forwardedHeaders(jar.toString(), incoming);
    },
    timeoutMs: 10_000,
  });
}
