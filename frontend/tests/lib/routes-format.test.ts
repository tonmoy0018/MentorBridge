import { describe, expect, it } from "vitest";
import { formatDuration, formatMoney, initials } from "@/lib/format";
import { dashboardPathFor, safeNextPath } from "@/lib/routes";

describe("safeNextPath", () => {
  it.each([
    ["/dashboard/student/bookings?tab=past", "/dashboard/student/bookings?tab=past"],
    ["https://evil.example/phish", "/fallback"],
    ["//evil.example", "/fallback"],
    ["/\\evil.example", "/fallback"],
    ["javascript:alert(1)", "/fallback"],
    ["", "/fallback"],
    [null, "/fallback"],
  ])("safeNextPath(%s) → %s", (input, expected) => {
    expect(safeNextPath(input, "/fallback")).toBe(expected);
  });

  it("maps roles to dashboards", () => {
    expect(dashboardPathFor("mentor")).toBe("/dashboard/mentor");
  });
});

describe("formatting", () => {
  it("formats money from integer cents", () => {
    expect(formatMoney({ amount_cents: 4500, currency: "USD" })).toBe("$45");
    expect(formatMoney({ amount_cents: 8075, currency: "USD" })).toBe("$80.75");
    expect(formatMoney({ amount_cents: 0, currency: "USD" })).toBe("Free");
    expect(formatMoney({ amount_cents: 0, currency: "USD" }, { showFree: false })).toBe("$0");
    expect(formatMoney({ amount_cents: -3825, currency: "USD" })).toBe("-$38.25");
  });

  it("formats durations", () => {
    expect(formatDuration(45)).toBe("45 min");
    expect(formatDuration(60)).toBe("1 hr");
    expect(formatDuration(90)).toBe("1 hr 30 min");
  });

  it("builds initials for avatar placeholders", () => {
    expect(initials("Mei Lin Chen")).toBe("ML");
    expect(initials("Amara")).toBe("A");
  });
});
