import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BookingStatusBadge } from "@/components/bookings/booking-status-badge";
import { Pagination, pageWindow } from "@/components/common/pagination";
import { ErrorState } from "@/components/feedback/error-state";
import { MentorCard } from "@/components/mentors/mentor-card";
import { PriceDisplay } from "@/components/mentors/price-display";
import { RatingDisplay } from "@/components/mentors/rating-display";
import { VerifiedBadge } from "@/components/mentors/verified-badge";
import { networkError } from "@/lib/api/errors";
import { makeMentor } from "../fixtures";

describe("RatingDisplay", () => {
  it("never invents a score when there are no reviews", () => {
    render(<RatingDisplay rating={null} count={0} />);
    expect(screen.getByText("No reviews yet")).toBeInTheDocument();
  });

  it("announces the rating and review count", () => {
    render(<RatingDisplay rating="4.67" count={3} />);
    expect(screen.getByText("Rated 4.7 out of 5 from 3 reviews")).toBeInTheDocument();
  });
});

describe("VerifiedBadge / MentorCard", () => {
  it("renders nothing unless the backend says the mentor is verified", () => {
    const { container } = render(<VerifiedBadge verified={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the badge only for verified mentors", () => {
    const { rerender } = render(<MentorCard mentor={makeMentor({ is_verified: false })} />);
    expect(screen.queryByText("Verified")).not.toBeInTheDocument();
    rerender(<MentorCard mentor={makeMentor({ is_verified: true })} />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("links to the profile and summarises extra skills", () => {
    render(<MentorCard mentor={makeMentor()} />);
    expect(screen.getByRole("link", { name: "Test Mentor" })).toHaveAttribute("href", "/mentors/test-mentor");
    expect(screen.getByText("+1 more")).toBeInTheDocument();
    expect(screen.getByText("No open times right now")).toBeInTheDocument();
  });
});

describe("PriceDisplay", () => {
  it("shows starting prices and free intro options", () => {
    const { rerender } = render(<PriceDisplay price={{ amount_cents: 4500, currency: "USD" }} from />);
    expect(screen.getByText("From")).toBeInTheDocument();
    expect(screen.getByText("$45")).toBeInTheDocument();
    rerender(<PriceDisplay price={{ amount_cents: 0, currency: "USD" }} from />);
    expect(screen.getByText("Free intro available")).toBeInTheDocument();
  });
});

describe("BookingStatusBadge", () => {
  it("words requested bookings for the viewer", () => {
    const { rerender } = render(<BookingStatusBadge status="requested" perspective="student" />);
    expect(screen.getByText("Awaiting mentor")).toBeInTheDocument();
    rerender(<BookingStatusBadge status="requested" perspective="mentor" />);
    expect(screen.getByText("Needs your response")).toBeInTheDocument();
  });
});

describe("Pagination", () => {
  it("computes a compact page window", () => {
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(5, 10)).toEqual([1, null, 4, 5, 6, null, 10]);
  });

  it("marks the current page and links neighbours", () => {
    render(<Pagination page={2} totalPages={3} hrefForPage={(p) => `/mentors?page=${p}`} />);
    expect(screen.getByRole("link", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /next/i })).toHaveAttribute("href", "/mentors?page=3");
  });

  it("renders nothing for a single page", () => {
    const { container } = render(<Pagination page={1} totalPages={1} hrefForPage={() => "/"} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ErrorState", () => {
  it("explains network failures in an alert", () => {
    render(<ErrorState error={networkError()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection problem");
  });
});
