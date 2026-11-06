import type { CurrentUser, Role } from "@/lib/api/types";

export const ROUTES = {
  home: "/",
  mentors: "/mentors",
  mentor: (id: string) => `/mentors/${encodeURIComponent(id)}`,
  login: "/login",
  signup: "/signup",
  signupStudent: "/signup/student",
  signupMentor: "/signup/mentor",
  forgotPassword: "/forgot-password",
  resetPassword: "/reset-password",
  dashboard: "/dashboard",
} as const;

export function dashboardPathFor(role: Role): string {
  return `/dashboard/${role}`;
}

/**
 * Whether the user (as reported by Django) may open a dashboard section. The admin section also
 * needs `is_admin` (role=admin AND staff on the backend). The API enforces the same rules.
 */
export function canUseDashboard(user: CurrentUser, role: Role): boolean {
  return role === "admin" ? user.role === "admin" && user.is_admin : user.role === role;
}

/**
 * Returns `raw` only if it is a same-site relative path, otherwise `fallback`.
 * Prevents open redirects via ?next=https://evil.example or //evil.example.
 */
export function safeNextPath(raw: string | null | undefined, fallback: string): string {
  if (!raw) return fallback;
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  try {
    const url = new URL(raw, "http://internal.invalid");
    if (url.origin !== "http://internal.invalid") return fallback;
    const path = `${url.pathname}${url.search}${url.hash}`;
    // Check the *normalised* result too: dot-segments can turn "/.//evil.example" into
    // "//evil.example", a protocol-relative (off-site) URL.
    if (path.startsWith("//") || path.startsWith("/\\")) return fallback;
    return path;
  } catch {
    return fallback;
  }
}
