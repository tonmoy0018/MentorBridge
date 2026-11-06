import type { MentorSummary } from "@/lib/api/types";

/** Minimal test mentor (test data only). */
export function makeMentor(overrides: Partial<MentorSummary> = {}): MentorSummary {
  return {
    id: "m-1",
    slug: "test-mentor",
    display_name: "Test Mentor",
    headline: "Helps with testing",
    avatar_url: null,
    current_title: "Engineer",
    current_company: "Example Co",
    profession: null,
    industries: [],
    skills: [
      { id: 1, name: "SQL", slug: "sql" },
      { id: 2, name: "Python", slug: "python" },
      { id: 3, name: "Statistics", slug: "statistics" },
      { id: 4, name: "Leadership", slug: "leadership" },
    ],
    country: "GB",
    city: "",
    languages: ["en"],
    years_experience: 5,
    is_verified: false,
    rating_avg: null,
    rating_count: 0,
    starting_price: { amount_cents: 4000, currency: "USD" },
    next_available_at: null,
    ...overrides,
  };
}
