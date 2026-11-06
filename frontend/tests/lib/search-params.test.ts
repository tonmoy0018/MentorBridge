import { describe, expect, it } from "vitest";
import { countActiveFilters, mentorsHref, parseMentorSearchParams, toSearchQuery } from "@/lib/search-params";
import { toMentorQuery } from "@/lib/api/live";

describe("parseMentorSearchParams", () => {
  it("accepts valid values and normalises case", () => {
    expect(
      parseMentorSearchParams({ q: "  design ", industry: "finance", country: "de", language: "EN", sort: "price_asc", page: "2" }),
    ).toEqual({
      q: "design",
      industry: "finance",
      skill: undefined,
      country: "DE",
      language: "en",
      price_min: undefined,
      price_max: undefined,
      available_within: undefined,
      sort: "price_asc",
      page: 2,
    });
  });

  it("drops invalid or unsafe values", () => {
    const parsed = parseMentorSearchParams({
      industry: "<script>",
      country: "Germany",
      sort: "drop table",
      page: "-1",
      price_min: "abc",
      available_within: "0",
    });
    expect(parsed.industry).toBeUndefined();
    expect(parsed.country).toBeUndefined();
    expect(parsed.sort).toBeUndefined();
    expect(parsed.page).toBeUndefined();
    expect(parsed.price_min).toBeUndefined();
    expect(parsed.available_within).toBeUndefined();
  });

  it("swaps a reversed price range and uses the first repeated value", () => {
    const parsed = parseMentorSearchParams({ price_min: "100", price_max: "20", skill: ["sql", "python"] });
    expect(parsed).toMatchObject({ price_min: 20, price_max: 100, skill: "sql" });
  });
});

describe("toSearchQuery / mentorsHref", () => {
  it("omits defaults so URLs stay short and shareable", () => {
    expect(toSearchQuery({ sort: "relevance", page: 1 })).toBe("");
    expect(mentorsHref({ industry: "law", price_max: 50, page: 3 })).toBe("/mentors?industry=law&price_max=50&page=3");
  });

  it("round-trips through the parser", () => {
    const params = { q: "data science", skill: "sql", available_within: 7, sort: "rating" as const };
    const qs = new URLSearchParams(toSearchQuery(params));
    expect(parseMentorSearchParams(Object.fromEntries(qs))).toMatchObject(params);
  });
});

describe("countActiveFilters", () => {
  it("ignores search text, sort and page", () => {
    expect(countActiveFilters({ q: "x", sort: "rating", page: 2, industry: "law", price_min: 10 })).toBe(2);
  });
});

describe("toMentorQuery", () => {
  it("converts whole currency units to cents and maps sort keys", () => {
    expect(toMentorQuery({ price_min: 25, price_max: 99.5, sort: "price_desc" })).toMatchObject({
      price_min: 2500,
      price_max: 9950,
      ordering: "-min_price_cents",
    });
  });
});
