/**
 * Public (browser-safe) configuration. Only NEXT_PUBLIC_* values may be read here: they are
 * inlined into the client bundle, so they must never contain secrets.
 */

/** Browser requests always go to the same origin; Next.js rewrites /api/* to Django. */
export const BROWSER_API_BASE = "/api/v1";

export const SITE_NAME = "MentorBridge";
