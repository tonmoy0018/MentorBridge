import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: vi.fn(), headers: vi.fn() }));

const { forwardedHeaders } = await import("@/lib/api/server-transport");

describe("forwardedHeaders", () => {
  it("forwards the session cookie and the proxy's view of the visitor to Django", () => {
    const incoming = new Headers({
      "x-forwarded-for": "203.0.113.7",
      "x-forwarded-proto": "https",
      "x-forwarded-host": "mentorbridge.example.com",
      "user-agent": "not forwarded",
    });
    expect(forwardedHeaders("sessionid=abc", incoming)).toEqual({
      Cookie: "sessionid=abc",
      "x-forwarded-for": "203.0.113.7",
      "x-forwarded-proto": "https",
      "x-forwarded-host": "mentorbridge.example.com",
    });
  });

  it("sends nothing it doesn't have", () => {
    expect(forwardedHeaders("", new Headers())).toEqual({});
  });
});
