import { describe, expect, it } from "vitest";
import type { MentorPackage, MentorService } from "@/lib/api/types";
import { packageSaving, perSessionPrice, serviceFormats, sessionPrice } from "@/lib/sessions";

const usd = (amount_cents: number) => ({ amount_cents, currency: "USD" });

const service: MentorService = {
  id: "s1",
  title: "Mock interview",
  description: "Practice",
  duration_minutes: 60,
  price: usd(5000),
  online: true,
  in_person: true,
  in_person_extra: usd(1500),
  in_person_area: "Gulshan, Dhaka",
  is_active: true,
};

const pkg = (online: number, regular: number): MentorPackage => ({
  id: "p1",
  title: "3 × Mock interview",
  session_count: 3,
  discount_percent: 20,
  validity_days: 30,
  prices: { online: usd(online), in_person: null },
  regular_prices: { online: usd(regular), in_person: null },
  service: { id: "s1", title: "Mock interview", duration_minutes: 60 },
  is_active: true,
});

describe("sessions", () => {
  it("lists formats online first", () => {
    expect(serviceFormats(service)).toEqual(["online", "in_person"]);
    expect(serviceFormats({ ...service, online: false })).toEqual(["in_person"]);
  });

  it("adds the in-person extra", () => {
    expect(sessionPrice(service, "online")).toEqual(usd(5000));
    expect(sessionPrice(service, "in_person")).toEqual(usd(6500));
  });

  it("computes package savings and per-session price per format", () => {
    expect(packageSaving(pkg(12000, 15000), "online")).toEqual(usd(3000));
    expect(packageSaving(pkg(15000, 15000), "online")).toBeNull();
    expect(perSessionPrice(pkg(10000, 15000), "online")).toEqual(usd(3333));
    // Not offered in person: no price, no saving.
    expect(packageSaving(pkg(12000, 15000), "in_person")).toBeNull();
    expect(perSessionPrice(pkg(12000, 15000), "in_person")).toBeNull();
  });
});
