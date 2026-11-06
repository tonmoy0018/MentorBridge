/** Authentication pages against the real API. */
import { expect, test } from "@playwright/test";
import { PASSWORD, email, signUp } from "./helpers";

test.describe("authentication (live API)", () => {
  test("login validates input accessibly", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByLabel("Email")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByText("Enter your password.")).toBeVisible();
  });

  test("wrong credentials get one generic message from the backend", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email("nobody"));
    await page.getByRole("textbox", { name: "Password", exact: true }).fill("not-the-password-1");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.locator("form").getByRole("alert")).toContainText("Email or password is incorrect.");
  });

  test("duplicate email is rejected by the backend", async ({ browser }) => {
    const address = email("dupe");
    const first = await browser.newContext();
    await signUp(await first.newPage(), "student", { first: "Dee", last: "Dupe", email: address });
    await first.close();

    const second = await browser.newContext();
    const page = await second.newPage();
    await page.goto("/signup/student");
    await page.getByLabel("First name").fill("Dee");
    await page.getByLabel("Last name").fill("Again");
    await page.getByLabel("Email").fill(address.toUpperCase());
    await page.getByRole("textbox", { name: "Password", exact: true }).fill(PASSWORD);
    await page.getByLabel("Confirm password").fill(PASSWORD);
    await page.getByRole("button", { name: "Create student account" }).click();
    await expect(page.getByText("An account with this email already exists.")).toBeVisible();
    await second.close();
  });

  test("signed-in users skip the login page; sessions survive reloads", async ({ page }) => {
    await signUp(page, "student", { first: "Rae", last: "Reload", email: email("reload") });
    await page.reload();
    await expect(page.getByRole("heading", { name: "Welcome back, Rae" })).toBeVisible();
    await page.goto("/login");
    await page.waitForURL("**/dashboard/student");
  });

  test("protected pages send visitors to log in, then back", async ({ page }) => {
    await page.goto("/dashboard/student/goals");
    await page.waitForURL("**/login?next=%2Fdashboard%2Fstudent%2Fgoals");
  });

  test("invalid reset and verification links explain what to do", async ({ page }) => {
    await page.goto("/reset-password?uid=abc&token=bad-token");
    await page.getByRole("textbox", { name: "New password", exact: true }).fill(PASSWORD);
    await page.getByLabel("Confirm new password").fill(PASSWORD);
    await page.getByRole("button", { name: "Set new password" }).click();
    await expect(page.getByText("This link is invalid or has expired")).toBeVisible();

    await page.goto("/verify-email?uid=abc&token=bad-token");
    await page.getByRole("button", { name: "Confirm my email" }).click();
    await expect(page.getByText("This link is invalid or has expired")).toBeVisible();
  });
});
