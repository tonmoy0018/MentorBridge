import { BROWSER_API_BASE } from "@/lib/config";
import { createTransport, isUnsafeMethod } from "./http";

const CSRF_COOKIE = "csrftoken";

export function readCookie(name: string, cookieString: string): string | null {
  for (const part of cookieString.split(";")) {
    const [rawKey, ...rest] = part.trim().split("=");
    if (rawKey === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  return readCookie(CSRF_COOKIE, document.cookie);
}

/**
 * Same-origin transport for Client Components. The session cookie is HttpOnly and sent
 * automatically; Django's CSRF token is echoed in the X-CSRFToken header for unsafe methods.
 */
export const browserTransport = createTransport({
  baseUrl: BROWSER_API_BASE,
  headers: (method): Record<string, string> => {
    const token = csrfToken();
    return isUnsafeMethod(method) && token ? { "X-CSRFToken": token } : {};
  },
  ensureCsrf: async () => {
    if (csrfToken()) return;
    // Sets the csrftoken cookie (GET /auth/csrf/ → 204).
    await fetch(`${BROWSER_API_BASE}/auth/csrf/`, { credentials: "same-origin" }).catch(() => {
      /* The real request below will report the network failure. */
    });
  },
});
