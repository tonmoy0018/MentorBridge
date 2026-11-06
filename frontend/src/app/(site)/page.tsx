import {
  ArrowRight,
  BadgeCheck,
  CalendarCheck,
  Compass,
  FileText,
  Handshake,
  MessagesSquare,
  Repeat,
  Search,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";
import { getServerApi } from "@/lib/data/server";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/feedback/empty-state";
import { CategoryCard } from "@/components/mentors/category-card";
import { MentorCard } from "@/components/mentors/mentor-card";
import { SearchBar } from "@/components/mentors/search-bar";
import { CardListSkeleton } from "@/components/feedback/loading-state";

const POPULAR_SEARCHES = ["Product management", "System design", "Case interviews", "Resume review", "Data science"];

const HELP_TOPICS = [
  { icon: Compass, title: "Choosing a direction", text: "Compare career paths with someone already on them." },
  { icon: MessagesSquare, title: "Interview practice", text: "Mock interviews with honest, specific feedback." },
  { icon: FileText, title: "CV & portfolio reviews", text: "Know what hiring teams actually look for." },
  { icon: Repeat, title: "Switching fields", text: "Plan a realistic move into a new industry." },
];

const STEPS = [
  { icon: Search, title: "Find your mentor", text: "Search by industry, skill, language, country and price. Read profiles and reviews from completed sessions." },
  { icon: CalendarCheck, title: "Pick a time", text: "See open times in your own timezone and choose the service that fits what you need." },
  { icon: ShieldCheck, title: "Request your session", text: "Send a request with a note about your goals. Your card is only charged once the mentor accepts." },
  { icon: Handshake, title: "Meet and grow", text: "Join the call, get practical advice, then leave a review to help other students." },
];

const STUDENT_BENEFITS = [
  { icon: BadgeCheck, title: "Reviewed profiles", text: "Mentors are approved by our team before they appear in search." },
  { icon: Target, title: "Focused, one-to-one time", text: "Every session is about your goals — not a generic webinar." },
  { icon: Star, title: "Honest reviews", text: "Only students who completed a session can leave a review." },
  { icon: Wallet, title: "Transparent pricing", text: "Prices and durations are shown upfront, with no subscription." },
];

const MENTOR_BENEFITS = [
  { icon: CalendarCheck, title: "Your schedule", text: "Set weekly availability, buffers and notice periods. Accept requests on your terms." },
  { icon: Sparkles, title: "Your services, your prices", text: "Offer intro calls, mock interviews or reviews at the length and price you choose." },
  { icon: Wallet, title: "Clear earnings", text: "See every session's earnings, fees and payouts in one place." },
  { icon: Handshake, title: "Meaningful impact", text: "Help the next generation avoid the mistakes you learned from." },
];

const FAQS = [
  {
    q: "How are mentors verified?",
    a: "Mentors submit their profile and professional details for review. Our team checks them before the profile is published. Only approved mentors appear in search, and the Verified badge is only shown once that review is complete.",
  },
  {
    q: "When am I charged for a session?",
    a: "Your card is authorised when you request a session and only charged when the mentor accepts. If the mentor declines or doesn't respond in time, the authorisation is released and you are not charged.",
  },
  {
    q: "Can I cancel or reschedule?",
    a: "Yes. You can cancel before the mentor accepts at no cost, and receive a full refund if you cancel at least 24 hours before an accepted session. If a mentor cancels, you are always refunded in full.",
  },
  {
    q: "How do sessions take place?",
    a: "Sessions are held over video. Once your booking is confirmed, the meeting link appears in your dashboard.",
  },
  {
    q: "What time zone are times shown in?",
    a: "All times are shown in your own time zone, which you can change in your account settings.",
  },
  {
    q: "How do mentors get paid?",
    a: "Earnings from completed sessions appear in the mentor dashboard, minus the platform fee, and are paid out by MentorBridge. Mentors can see each earning and payout record.",
  },
];

export default function HomePage() {
  return (
    <>
      <Hero />

      <section aria-labelledby="categories-heading" className="container-page py-16 sm:py-20">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="categories-heading" className="text-2xl font-semibold sm:text-3xl">
              Explore by career area
            </h2>
            <p className="mt-2 text-muted-foreground">Find mentors who work in the field you&apos;re aiming for.</p>
          </div>
          <Link href="/mentors" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
            Browse all mentors <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
        <Suspense fallback={<CategorySkeleton />}>
          <Categories />
        </Suspense>
      </section>

      <section aria-labelledby="featured-heading" className="border-y bg-muted/40">
        <div className="container-page py-16 sm:py-20">
          <h2 id="featured-heading" className="text-2xl font-semibold sm:text-3xl">
            Highly rated mentors
          </h2>
          <p className="mt-2 text-muted-foreground">Verified mentors with the best reviews from completed sessions.</p>
          <Suspense fallback={<CardListSkeleton count={3} className="mt-8 md:grid-cols-3" label="Loading mentors…" />}>
            <FeaturedMentors />
          </Suspense>
        </div>
      </section>

      <section id="how-it-works" aria-labelledby="how-heading" className="container-page py-16 sm:py-20">
        <h2 id="how-heading" className="text-2xl font-semibold sm:text-3xl">
          How it works
        </h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          From search to session in four steps. No subscriptions — you only pay for the sessions you book.
        </p>
        <ol className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative rounded-xl border bg-card p-6">
              <span className="text-sm font-semibold text-primary">Step {index + 1}</span>
              <step.icon className="mt-4 size-6 text-primary" aria-hidden="true" />
              <h3 className="mt-3 font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-t bg-muted/40">
        <div className="container-page grid grid-cols-1 gap-12 py-16 sm:py-20 lg:grid-cols-2">
          <BenefitList
            id="for-students"
            eyebrow="For students"
            title="Guidance you can act on"
            items={STUDENT_BENEFITS}
            cta={{ href: "/signup/student", label: "Create a student account" }}
          />
          <BenefitList
            id="for-mentors"
            eyebrow="For mentors"
            title="Share what you know, on your terms"
            items={MENTOR_BENEFITS}
            cta={{ href: "/signup/mentor", label: "Become a mentor" }}
          />
        </div>
      </section>

      <section id="faq" aria-labelledby="faq-heading" className="container-page py-16 sm:py-20">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_2fr]">
          <div>
            <h2 id="faq-heading" className="text-2xl font-semibold sm:text-3xl">
              Frequently asked questions
            </h2>
            <p className="mt-2 text-muted-foreground">
              What to expect before, during and after a session.
            </p>
          </div>
          <Accordion type="single" collapsible className="w-full">
            {FAQS.map((faq, index) => (
              <AccordionItem key={faq.q} value={`faq-${index}`}>
                <AccordionTrigger className="text-base">{faq.q}</AccordionTrigger>
                <AccordionContent className="text-muted-foreground">{faq.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      <section className="container-page pb-20">
        <div className="flex flex-col items-start gap-6 rounded-2xl bg-primary px-6 py-10 text-primary-foreground sm:px-10 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">Ready to take the next step?</h2>
            <p className="mt-2 text-primary-foreground/85">Browse mentors and book your first conversation.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild size="lg" variant="secondary">
              <Link href="/mentors">Find a Mentor</Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="border-primary-foreground/40 bg-transparent text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground"
            >
              <Link href="/signup/mentor">Become a Mentor</Link>
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}

function Hero() {
  return (
    <section className="border-b">
      <div className="container-page grid grid-cols-1 items-center gap-12 py-14 sm:py-20 lg:grid-cols-[1.2fr_1fr] lg:py-24">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-secondary px-3 py-1 text-sm font-medium text-secondary-foreground">
            <BadgeCheck className="size-4" aria-hidden="true" />
            One-to-one career mentorship
          </p>
          <h1 className="mt-6 text-4xl leading-[1.1] font-semibold sm:text-5xl lg:text-6xl">
            Learn From Those Who&apos;ve Already Been There.
          </h1>
          <p className="mt-6 max-w-xl text-lg text-muted-foreground">
            MentorBridge connects students and early-career professionals with experienced professionals for
            personalised guidance — from choosing a path to acing the interview.
          </p>
          <SearchBar size="lg" className="mt-8 max-w-xl" />
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted-foreground">Popular:</span>
            {POPULAR_SEARCHES.map((term) => (
              <Link
                key={term}
                href={`/mentors?q=${encodeURIComponent(term)}`}
                className="rounded-full border px-3 py-1 text-muted-foreground hover:border-primary/40 hover:text-foreground"
              >
                {term}
              </Link>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/mentors">
                Find a Mentor <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/signup/mentor">Become a Mentor</Link>
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border bg-muted/40 p-6 sm:p-8">
          <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
            What mentors can help with
          </h2>
          <ul className="mt-5 grid gap-4">
            {HELP_TOPICS.map((topic) => (
              <li key={topic.title} className="flex gap-4 rounded-xl bg-card p-4 ring-1 ring-border">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                  <topic.icon className="size-5" aria-hidden="true" />
                </span>
                <span>
                  <span className="block font-medium">{topic.title}</span>
                  <span className="block text-sm text-muted-foreground">{topic.text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

async function Categories() {
  const api = await getServerApi();
  const industries = await api.taxonomy.industriesWithCounts().catch(() => null);
  if (!industries) {
    return (
      <p className="mt-8 text-sm text-muted-foreground">
        Career areas are unavailable right now.{" "}
        <Link href="/mentors" className="font-medium text-primary hover:underline">
          Browse all mentors
        </Link>{" "}
        instead.
      </p>
    );
  }
  return (
    <ul className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {industries.map((industry) => (
        <li key={industry.id}>
          <CategoryCard industry={industry} />
        </li>
      ))}
    </ul>
  );
}

function CategorySkeleton() {
  return (
    <div role="status" className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <span className="sr-only">Loading career areas…</span>
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="h-[78px] rounded-xl" />
      ))}
    </div>
  );
}

async function FeaturedMentors() {
  const api = await getServerApi();
  const page = await api.mentors.search({ sort: "rating", page_size: 3 }).catch(() => null);
  if (!page) {
    return (
      <p className="mt-8 text-sm text-muted-foreground">
        Mentors couldn&apos;t be loaded right now. Please try again shortly.
      </p>
    );
  }
  if (page.results.length === 0) {
    return (
      <EmptyState
        className="mt-8"
        title="Mentors are joining soon"
        description="We're reviewing our first mentor profiles. Check back shortly, or apply to mentor."
        action={
          <Button asChild variant="outline">
            <Link href="/signup/mentor">Become a mentor</Link>
          </Button>
        }
      />
    );
  }
  return (
    <ul className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
      {page.results.map((mentor) => (
        <li key={mentor.id}>
          <MentorCard mentor={mentor} />
        </li>
      ))}
    </ul>
  );
}

function BenefitList({
  id,
  eyebrow,
  title,
  items,
  cta,
}: {
  id: string;
  eyebrow: string;
  title: string;
  items: { icon: typeof Star; title: string; text: string }[];
  cta: { href: string; label: string };
}) {
  return (
    <div id={id} className="scroll-mt-24">
      <p className="text-sm font-semibold text-primary">{eyebrow}</p>
      <h2 className="mt-2 text-2xl font-semibold sm:text-3xl">{title}</h2>
      <ul className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.title}>
            <item.icon className="size-6 text-primary" aria-hidden="true" />
            <h3 className="mt-3 font-semibold">{item.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{item.text}</p>
          </li>
        ))}
      </ul>
      <Button asChild variant="outline" className="mt-8">
        <Link href={cta.href}>
          {cta.label} <ArrowRight aria-hidden="true" />
        </Link>
      </Button>
    </div>
  );
}
