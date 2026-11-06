/** Public pages against the real API: no sign-in needed. */
import { expect, test } from "@playwright/test";

test.describe("public pages (live API)", () => {
  test("homepage renders categories from the backend", async ({ page, request }) => {
    const categories = await (await request.get("/api/v1/categories/")).json();
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Learn From Those Who've Already Been There.");
    await expect(page.getByRole("link", { name: new RegExp(categories[0].name) }).first()).toBeVisible();
    await expect(page.getByText(/fictional demo data/i)).toHaveCount(0); // no mock layer anymore
  });

  test("directory filters are applied by the backend and kept in the URL", async ({ page, isMobile }) => {
    await page.goto("/mentors");
    await expect(page.getByText(/mentors? found/)).toBeVisible();
    if (isMobile) await page.getByRole("button", { name: /filters/i }).click();
    const form = page.getByRole("form", { name: "Filter mentors" }).last();
    await form.getByLabel("Industry").selectOption("law");
    await form.getByLabel("Maximum").fill("40");
    await form.getByRole("button", { name: "Apply filters" }).click();
    await expect(page).toHaveURL(/industry=law/);
    await expect(page).toHaveURL(/price_max=40/);
    await page.reload();
    await expect(page.getByRole("link", { name: "Clear all" })).toBeVisible();
  });

  test("searching for nothing shows the empty state", async ({ page }) => {
    await page.goto("/mentors?q=zzzz-no-such-mentor");
    await expect(page.getByRole("heading", { name: "No mentors match your search" })).toBeVisible();
  });

  test("unknown mentors get a not-found page", async ({ page }) => {
    await page.goto("/mentors/does-not-exist-anywhere");
    await expect(page.getByRole("heading", { name: "Mentor not found" })).toBeVisible();
  });

  test("pages have no horizontal overflow", async ({ page }) => {
    for (const path of ["/", "/mentors", "/login", "/signup/student"]) {
      await page.goto(path);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `overflow on ${path}`).toBeLessThanOrEqual(0);
    }
  });
});
