/**
 * The full marketplace journey against the real Django API (steps A–L of the integration brief):
 * accounts, mentor onboarding, admin approval, discovery, booking, conflicts, mentor acceptance,
 * dashboards, cancellation and access control. Runs serially: each step builds on the last.
 */
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { ADMIN, RUN, apiCall, email, expectToast, logIn, signUp } from "./helpers";

const mentor = { first: "Priya", last: `Tester${RUN}`, email: email("mentor") };
const student = { first: "Jordan", last: `Lee${RUN}`, email: email("student") };
const rival = { first: "Sam", last: `Rival${RUN}`, email: email("rival") };
const mentorName = `${mentor.first} ${mentor.last}`;

test.describe.serial("marketplace journey", () => {
  let mentorCtx: BrowserContext, studentCtx: BrowserContext, rivalCtx: BrowserContext, adminCtx: BrowserContext;
  let mentorPage: Page, studentPage: Page, rivalPage: Page, adminPage: Page;
  let bookingId = "";

  test.beforeAll(async ({ browser }) => {
    const open = async () => {
      const ctx = await browser.newContext({ timezoneId: "Europe/London" });
      return [ctx, await ctx.newPage()] as const;
    };
    [mentorCtx, mentorPage] = await open();
    [studentCtx, studentPage] = await open();
    [rivalCtx, rivalPage] = await open();
    [adminCtx, adminPage] = await open();
  });

  test.afterAll(async () => {
    await Promise.all([mentorCtx, studentCtx, rivalCtx, adminCtx].map((c) => c.close()));
  });

  test("A. a student registers", async () => {
    await signUp(studentPage, "student", student);
    await expect(studentPage.getByRole("heading", { name: `Welcome back, ${student.first}` })).toBeVisible();
    const me = await (await apiCall(studentCtx, "GET", "/auth/me/")).json();
    expect(me).toMatchObject({ role: "student", is_admin: false, email: student.email });
    const cookies = await studentCtx.cookies();
    expect(cookies.find((c) => c.name === "sessionid")?.httpOnly).toBe(true);
  });

  test("B. a mentor registers", async () => {
    await signUp(mentorPage, "mentor", mentor);
    await expect(mentorPage.getByText("Not submitted").first()).toBeVisible();
  });

  test("D. the mentor completes their profile and services", async () => {
    const page = mentorPage;
    await page.getByRole("textbox", { name: "Headline", exact: true }).fill("Product manager helping career switchers");
    await page.getByLabel("Current job title").fill("Senior Product Manager");
    await page.getByLabel("Company").fill("Example Health");
    await page.getByRole("combobox", { name: "Profession", exact: true }).selectOption({ label: "Product Manager" });
    await page.getByRole("spinbutton", { name: "Years of experience", exact: true }).fill("9");
    await page.getByRole("combobox", { name: "Country", exact: true }).selectOption("GB");
    await page.getByLabel("City or region").fill("London");
    await page.getByLabel("Default meeting link").fill("https://meet.example.com/priya");
    await page.getByRole("combobox", { name: "Time zone", exact: true }).selectOption("Europe/London");
    await page
      .getByLabel("About you")
      .fill("I moved from consulting into product management and help others make the same switch with confidence.");
    await page.getByRole("checkbox", { name: "Technology" }).check();
    await page.getByRole("checkbox", { name: "Product strategy" }).check();
    await page.getByRole("checkbox", { name: "English" }).check();
    await page.getByRole("button", { name: "Save profile" }).click();
    await expectToast(page, "Profile saved");

    await page.goto("/dashboard/mentor/services");
    for (const svc of [
      { title: "Intro chat", what: "A short conversation about moving into product.", length: "30", price: "0" },
      { title: "Mock interview", what: "A realistic product-sense interview with feedback.", length: "60", price: "95" },
    ]) {
      await page.getByRole("button", { name: "Add service" }).click();
      const dialog = page.getByRole("dialog");
      await dialog.getByLabel("Title").fill(svc.title);
      await dialog.getByLabel("What's included").fill(svc.what);
      await dialog.getByLabel("Length").selectOption(svc.length);
      await dialog.getByLabel("Price (USD)").fill(svc.price);
      await dialog.getByRole("button", { name: "Save service" }).click();
      await expect(page.getByRole("heading", { name: svc.title })).toBeVisible();
    }
  });

  test("E. the mentor configures weekly availability", async () => {
    const page = mentorPage;
    await page.goto("/dashboard/mentor/availability");
    for (const day of ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]) {
      await page.getByRole("switch", { name: `Available on ${day}` }).click();
    }
    await page.getByRole("button", { name: "Save weekly hours" }).click();
    await expectToast(page, "Weekly hours saved");

    await page.goto("/dashboard/mentor/profile");
    await page.getByRole("button", { name: "Submit for review" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Submit for review" }).click();
    await expect(page.getByText("Under review").first()).toBeVisible();
  });

  test("the mentor is not public before approval", async () => {
    await studentPage.goto(`/mentors?q=${mentor.last}`);
    await expect(studentPage.getByRole("heading", { name: "No mentors match your search" })).toBeVisible();
  });

  test("C. an administrator approves the mentor", async () => {
    await logIn(adminPage, ADMIN);
    await adminPage.goto("/dashboard/admin/verification");
    const card = adminPage.getByRole("listitem").filter({ hasText: mentorName });
    await card.getByRole("button", { name: "Approve" }).click();
    await adminPage.getByRole("alertdialog").getByRole("button", { name: "Approve mentor" }).click();
    await expectToast(adminPage, "Mentor approved");
    await expect(adminPage.getByRole("listitem").filter({ hasText: mentorName })).toHaveCount(0);
  });

  test("F. the student finds the mentor through backend search and filters", async () => {
    const page = studentPage;
    await page.goto(`/mentors?q=${mentor.last}&industry=technology&country=GB`);
    await expect(page.getByText(/1 mentor found/)).toBeVisible();
    const card = page.getByRole("article").filter({ hasText: mentorName });
    await expect(card.getByText("Free intro available")).toBeVisible();

    // Filters run on the server: a non-matching category returns nothing.
    await page.goto(`/mentors?q=${mentor.last}&industry=law`);
    await expect(page.getByRole("heading", { name: "No mentors match your search" })).toBeVisible();
  });

  test("G. the student opens the profile: verified, services, availability, no reviews yet", async () => {
    const page = studentPage;
    await page.goto(`/mentors?q=${mentor.last}`);
    await page.getByRole("link", { name: mentorName }).click();
    await expect(page.getByRole("heading", { level: 1, name: mentorName })).toBeVisible();
    await expect(page.getByText("Verified").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Intro chat" })).toBeVisible();
    await expect(page.getByText("Online payment coming soon", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "No reviews yet" })).toBeVisible();

    // Paid sessions can't be booked until payments exist.
    const panel = page.locator("#book");
    await panel.getByLabel("Service").selectOption({ label: "Mock interview · 1 hr · $95 (online payment coming soon)" });
    await expect(panel.getByText(/online payment isn.t available yet/i)).toBeVisible();
    await expect(panel.getByRole("button", { name: "Request booking" })).toBeDisabled();
    await panel.getByLabel("Service").selectOption({ label: "Intro chat · 30 min · Free" });
    await expect(panel.getByRole("group", { name: /time/i }).getByRole("button").first()).toBeVisible();
  });

  test("H + K. two students race for one slot: one booking, one clear conflict", async () => {
    await signUp(rivalPage, "student", rival);
    const mentorUrl = studentPage.url();
    await rivalPage.goto(mentorUrl);

    const choose = async (page: Page) => {
      const panel = page.locator("#book");
      await panel.getByRole("group", { name: /time/i }).getByRole("button").first().click();
      await panel.getByRole("button", { name: "Request booking" }).click();
      return page.getByRole("alertdialog");
    };
    const studentDialog = await choose(studentPage);
    const rivalDialog = await choose(rivalPage);
    await expect(studentDialog.getByRole("definition").nth(1)).toHaveText(
      await rivalDialog.getByRole("definition").nth(1).innerText(),
    ); // same time

    await studentDialog.getByLabel(`Note for ${mentor.first}`).fill("I'd love advice on moving into product.");
    await studentDialog.getByRole("button", { name: "Send request" }).click();
    await studentPage.waitForURL("**/dashboard/student/bookings");
    await expect(studentPage.getByText("Awaiting mentor").first()).toBeVisible();

    await rivalDialog.getByRole("button", { name: "Send request" }).click();
    await expect(rivalDialog.getByRole("alert")).toContainText("no longer available");

    const list = await (await apiCall(studentCtx, "GET", "/bookings/")).json();
    expect(list.count).toBe(1);
    bookingId = list.results[0].id;
    expect(list.results[0]).toMatchObject({ status: "requested", price: { amount_cents: 0, currency: "USD" } });
  });

  test("I. the mentor confirms the request (free session; no payment step)", async () => {
    await mentorPage.goto("/dashboard/mentor/bookings");
    const request = mentorPage.getByRole("tabpanel").getByRole("article").filter({ hasText: student.first });
    await expect(request.getByText("Needs your response")).toBeVisible();
    await expect(request.getByText("I'd love advice on moving into product.")).toBeVisible();
    await request.getByRole("button", { name: "Accept" }).click();
    await mentorPage.getByRole("alertdialog").getByRole("button", { name: "Accept request" }).click();
    await expectToast(mentorPage, "Booking confirmed");
  });

  test("J. both dashboards show the confirmed session", async () => {
    await studentPage.goto("/dashboard/student");
    const section = (page: Page, heading: string) =>
      page.locator("section").filter({ has: page.getByRole("heading", { name: heading }) });
    const upcoming = section(studentPage, "Upcoming sessions");
    await expect(upcoming.getByText("Confirmed").first()).toBeVisible();
    await expect(upcoming.getByRole("link", { name: /join meeting/i })).toHaveAttribute(
      "href",
      "https://meet.example.com/priya",
    );

    await mentorPage.goto("/dashboard/mentor");
    await expect(section(mentorPage, "Upcoming sessions").getByText(`with ${student.first} ${student.last}`)).toBeVisible();
    await expect(section(mentorPage, "Requests waiting for you").getByText("You're all caught up")).toBeVisible();
  });

  test("K. the student cancels under the policy and the slot is released", async () => {
    await studentPage.goto("/dashboard/student/bookings");
    await studentPage.getByRole("button", { name: "Cancel booking" }).click();
    const dialog = studentPage.getByRole("alertdialog");
    await dialog.getByRole("button", { name: "Cancel booking" }).click();
    await expectToast(studentPage, "Booking cancelled");
    await studentPage.getByRole("tab", { name: /cancelled/i }).click();
    await expect(studentPage.getByRole("tabpanel").getByText("Cancelled").first()).toBeVisible();

    const detail = await (await apiCall(studentCtx, "GET", `/bookings/${bookingId}/`)).json();
    expect(detail).toMatchObject({ status: "cancelled", meeting_url: null, refund_outcome: "" });

    // The released slot can now be booked by the other student.
    await rivalPage.reload();
    const panel = rivalPage.locator("#book");
    await panel.getByRole("group", { name: /time/i }).getByRole("button").first().click();
    await panel.getByRole("button", { name: "Request booking" }).click();
    await rivalPage.getByRole("alertdialog").getByRole("button", { name: "Send request" }).click();
    await rivalPage.waitForURL("**/dashboard/student/bookings");
    await expect(rivalPage.getByText("Awaiting mentor").first()).toBeVisible();
  });

  test("L. protected data and pages stay protected", async ({ browser }) => {
    // Other users' bookings are invisible.
    expect((await apiCall(rivalCtx, "GET", `/bookings/${bookingId}/`)).status()).toBe(404);
    // Role boundaries are enforced by the API…
    expect((await apiCall(studentCtx, "GET", "/admin/users/")).status()).toBe(403);
    expect((await apiCall(studentCtx, "POST", `/bookings/${bookingId}/accept/`)).status()).toBe(403);
    expect((await apiCall(mentorCtx, "GET", "/me/student/goals/")).status()).toBe(403);
    // …and by the dashboard routing.
    await studentPage.goto("/dashboard/admin");
    await studentPage.waitForURL("**/dashboard/student");
    await mentorPage.goto("/dashboard/student/bookings");
    await mentorPage.waitForURL("**/dashboard/mentor");

    const anonymous = await browser.newContext();
    const anonPage = await anonymous.newPage();
    expect((await anonymous.request.get("/api/v1/bookings/")).status()).toBe(401);
    await anonPage.goto("/dashboard/student/bookings");
    await anonPage.waitForURL("**/login?next=%2Fdashboard%2Fstudent%2Fbookings");
    await anonymous.close();

    // Logging out ends the session server-side.
    await studentPage.goto("/dashboard/student");
    await studentPage.getByRole("button", { name: /open account menu/i }).click();
    await studentPage.getByRole("menuitem", { name: "Log out" }).click();
    await studentPage.waitForURL((url) => url.pathname === "/");
    expect((await apiCall(studentCtx, "GET", "/auth/me/")).status()).toBe(401);
  });
});
