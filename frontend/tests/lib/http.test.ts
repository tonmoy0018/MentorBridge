import { describe, expect, it, vi } from "vitest";
import { isApiError } from "@/lib/api/errors";
import { buildQueryString, createTransport } from "@/lib/api/http";
import { readCookie } from "@/lib/api/browser-transport";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("buildQueryString", () => {
  it("omits empty values and repeats arrays", () => {
    expect(buildQueryString({ q: "pm", empty: "", none: undefined, status: ["requested", "confirmed"], page: 2 })).toBe(
      "?q=pm&status=requested&status=confirmed&page=2",
    );
    expect(buildQueryString({})).toBe("");
  });
});

describe("createTransport", () => {
  it("sends JSON with per-method headers and only ensures CSRF for unsafe methods", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json(200, { ok: true }));
    const ensureCsrf = vi.fn().mockResolvedValue(undefined);
    const request = createTransport({
      baseUrl: "/api/v1",
      headers: (method): Record<string, string> => (method === "GET" ? {} : { "X-CSRFToken": "token" }),
      ensureCsrf,
      fetchImpl,
    });

    await request("/mentors/", { query: { q: "design" } });
    expect(ensureCsrf).not.toHaveBeenCalled();
    expect(fetchImpl.mock.calls[0]![0]).toBe("/api/v1/mentors/?q=design");

    await request("/auth/login/", { method: "POST", body: { email: "a@example.com" } });
    expect(ensureCsrf).toHaveBeenCalledTimes(1);
    const init = fetchImpl.mock.calls[1]![1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers).toMatchObject({ "X-CSRFToken": "token", "Content-Type": "application/json" });
    expect(init.body).toBe(JSON.stringify({ email: "a@example.com" }));
  });

  it("returns undefined for 204 responses", async () => {
    const request = createTransport({ baseUrl: "", headers: () => ({}), fetchImpl: vi.fn().mockResolvedValue(new Response(null, { status: 204 })) });
    await expect(request("/auth/logout/", { method: "POST" })).resolves.toBeUndefined();
  });

  it("throws a typed ApiError for error responses", async () => {
    const request = createTransport({
      baseUrl: "",
      headers: () => ({}),
      fetchImpl: vi.fn().mockResolvedValue(json(409, { error: { code: "slot_unavailable", message: "Taken." } })),
    });
    const error = await request("/bookings/", { method: "POST" }).catch((e: unknown) => e);
    expect(isApiError(error) && error.kind).toBe("conflict");
    expect(isApiError(error) && error.code).toBe("slot_unavailable");
  });

  it("turns fetch failures into network errors", async () => {
    const request = createTransport({ baseUrl: "", headers: () => ({}), fetchImpl: vi.fn().mockRejectedValue(new TypeError("Failed to fetch")) });
    const error = await request("/mentors/").catch((e: unknown) => e);
    expect(isApiError(error) && error.kind).toBe("network");
  });
});

describe("readCookie", () => {
  it("finds a cookie by exact name", () => {
    expect(readCookie("csrftoken", "sessionid=x; csrftoken=abc%3D; other=1")).toBe("abc=");
    expect(readCookie("csrf", "csrftoken=abc")).toBeNull();
  });
});
