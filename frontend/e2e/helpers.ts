import { expect, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";

export const PASSWORD = "E2E-Journey-Pass-91";
export const ADMIN = { email: "e2e-admin@example.com", password: "E2E-Admin-Pass-2026" };

/** Unique per run so the shared e2e database never needs resetting. */
export const RUN = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;

export function email(label: string) {
  return `${label}.${RUN}@example.com`;
}

export async function signUp(
  page: Page,
  role: "student" | "mentor",
  person: { first: string; last: string; email: string },
) {
  await page.goto(`/signup/${role}`);
  await page.getByLabel("First name").fill(person.first);
  await page.getByLabel("Last name").fill(person.last);
  await page.getByLabel("Email").fill(person.email);
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirm password").fill(PASSWORD);
  await page.getByRole("button", { name: /create .* account/i }).click();
  await page.waitForURL(role === "mentor" ? "**/dashboard/mentor/profile" : "**/dashboard/student");
}

export async function logIn(page: Page, user: { email: string; password: string }) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL("**/dashboard/**");
}

/** Raw API call with the context's session cookie (and CSRF token for writes). */
export async function apiCall(
  context: BrowserContext,
  method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  data?: unknown,
) {
  const csrf = (await context.cookies()).find((c) => c.name === "csrftoken")?.value ?? "";
  const request: APIRequestContext = context.request;
  return request.fetch(`/api/v1${path}`, { method, data, headers: csrf ? { "X-CSRFToken": csrf } : {} });
}

export async function expectToast(page: Page, text: string | RegExp) {
  await expect(page.locator("[data-sonner-toast]").filter({ hasText: text }).first()).toBeVisible();
}
