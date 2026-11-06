import { describe, expect, it } from "vitest";
import { ApiError, errorFromResponse, getErrorMessage, kindForStatus, networkError } from "@/lib/api/errors";

describe("errorFromResponse", () => {
  it("maps DRF field errors from the standard envelope", () => {
    const error = errorFromResponse(400, {
      error: { code: "validation_error", message: "Check the form.", details: { fields: { email: ["Already in use."] } } },
    });
    expect(error.kind).toBe("validation");
    expect(error.code).toBe("validation_error");
    expect(error.message).toBe("Check the form.");
    expect(error.fieldErrors).toEqual({ email: ["Already in use."] });
  });

  it("falls back to safe default messages for non-JSON bodies", () => {
    const error = errorFromResponse(502, undefined);
    expect(error.kind).toBe("server");
    expect(error.message).toMatch(/something went wrong/i);
  });

  it("reads Retry-After for throttled responses", () => {
    const error = errorFromResponse(429, {}, "30");
    expect(error.kind).toBe("throttled");
    expect(error.retryAfterSeconds).toBe(30);
  });

  it.each([
    [401, "unauthenticated"],
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
    [500, "server"],
  ] as const)("maps status %i to %s", (status, kind) => {
    expect(kindForStatus(status)).toBe(kind);
  });
});

describe("getErrorMessage", () => {
  it("never exposes raw error details from unknown errors", () => {
    expect(getErrorMessage(new Error("TypeError: cannot read x of undefined"))).toMatch(/something went wrong/i);
  });

  it("uses the ApiError message", () => {
    expect(getErrorMessage(networkError())).toMatch(/couldn't reach/i);
    expect(networkError()).toBeInstanceOf(ApiError);
  });
});
