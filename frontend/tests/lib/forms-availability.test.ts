import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { applyServerErrors } from "@/lib/forms";
import { validateDay } from "@/features/mentor/availability-editor";

describe("applyServerErrors", () => {
  it("attaches known field errors and returns null when all matched", () => {
    const setError = vi.fn();
    const error = new ApiError({
      kind: "validation",
      status: 400,
      code: "validation_error",
      message: "Invalid",
      fieldErrors: { email: ["Already registered."] },
    });
    expect(applyServerErrors(error, setError, ["email", "password"])).toBeNull();
    expect(setError).toHaveBeenCalledWith("email", { type: "server", message: "Already registered." });
  });

  it("returns unmatched messages for display at form level", () => {
    const error = new ApiError({
      kind: "validation",
      status: 400,
      code: "validation_error",
      message: "Invalid",
      fieldErrors: { non_field_errors: ["Too many attempts."] },
    });
    expect(applyServerErrors(error, vi.fn(), ["email"])).toBe("Too many attempts.");
  });

  it("falls back to the error message when there are no field errors", () => {
    const error = new ApiError({ kind: "network", status: 0, code: "network_error", message: "Offline" });
    expect(applyServerErrors(error, vi.fn(), ["email"])).toBe("Offline");
  });
});

describe("validateDay (availability)", () => {
  it("accepts non-overlapping ranges in any order", () => {
    expect(
      validateDay([
        { start_time: "13:00", end_time: "15:00" },
        { start_time: "09:00", end_time: "12:00" },
      ]),
    ).toBeNull();
  });

  it("rejects reversed and overlapping ranges", () => {
    expect(validateDay([{ start_time: "10:00", end_time: "09:00" }])).toMatch(/after start/);
    expect(
      validateDay([
        { start_time: "09:00", end_time: "12:00" },
        { start_time: "11:00", end_time: "13:00" },
      ]),
    ).toMatch(/overlap/);
  });
});
