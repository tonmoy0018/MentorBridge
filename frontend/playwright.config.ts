import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = 3200;
const API_PORT = 8001;
const baseURL = `http://localhost:${WEB_PORT}`;

/**
 * End-to-end tests against the real stack: a production build of the web app proxying to the
 * Django API (`api-e2e` compose service, dedicated `mentorbridge_e2e` database). Requires Docker.
 * Each run creates uniquely named accounts, so the database never needs resetting.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 60_000,
  globalTeardown: "./e2e/teardown.ts",
  use: {
    baseURL,
    timezoneId: "Europe/London",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    // The full journey runs once (desktop); public and auth pages are also checked on a phone.
    { name: "mobile", use: { ...devices["Pixel 7"] }, testIgnore: /journey\.spec\.ts/ },
  ],
  webServer: [
    {
      command:
        "docker compose up -d --wait db mailpit && docker compose --profile e2e up --no-deps --build api-e2e",
      cwd: "..",
      url: `http://localhost:${API_PORT}/api/v1/health/`,
      timeout: 300_000,
      reuseExistingServer: !process.env.CI,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: `pnpm build && pnpm exec next start -p ${WEB_PORT}`,
      url: baseURL,
      timeout: 300_000,
      reuseExistingServer: !process.env.CI,
      env: { INTERNAL_API_URL: `http://localhost:${API_PORT}` },
    },
  ],
});
