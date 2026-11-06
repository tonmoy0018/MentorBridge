import { CalendarCheck, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { isApiError } from "@/lib/api/errors";
import type { MentorProfile } from "@/lib/api/types";
import { getServerApi } from "@/lib/data/server";
import { languageName } from "@/lib/format";
import { mentorsHref } from "@/lib/search-params";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/feedback/error-state";
import { BookingWidget } from "@/components/mentors/booking-widget";
import { ExperienceTimeline } from "@/components/mentors/experience-timeline";
import { PriceDisplay } from "@/components/mentors/price-display";
import { ProfileHeader } from "@/components/mentors/profile-header";
import { ReviewList } from "@/components/mentors/review-list";
import { SaveMentorButton } from "@/components/mentors/save-mentor-button";
import { ServiceList } from "@/components/mentors/service-list";

type Props = PageProps<"/mentors/[id]">;

/** Loads the mentor, mapping a 404 to Next's not-found page. Other errors propagate. */
async function loadMentor(id: string): Promise<MentorProfile> {
  const api = await getServerApi();
  try {
    return await api.mentors.get(id);
  } catch (error) {
    if (isApiError(error) && error.kind === "not_found") notFound();
    throw error;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const mentor = await loadMentor(id);
    return {
      title: `${mentor.display_name} — ${mentor.current_title}`,
      description: mentor.headline,
    };
  } catch {
    return { title: "Mentor profile" };
  }
}

export default function MentorProfilePage({ params, searchParams }: Props) {
  return (
    <div className="container-page py-8 sm:py-10">
      <Suspense fallback={<ProfileSkeleton />}>
        <Profile params={params} searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Profile({ params, searchParams }: Pick<Props, "params" | "searchParams">) {
  const { id } = await params;
  const query = await searchParams;
  const initialServiceId = typeof query.service === "string" ? query.service : undefined;

  let mentor: MentorProfile;
  try {
    mentor = await loadMentor(id);
  } catch (error) {
    if (!isApiError(error)) throw error; // let notFound() and unexpected errors propagate
    return <ErrorState error={error} title="We couldn't load this mentor" retryHref={`/mentors/${encodeURIComponent(id)}`} />;
  }

  const api = await getServerApi();
  const [reviews, config] = await Promise.all([
    api.mentors.reviews(mentor.slug).catch(() => ({ count: 0, next: null, previous: null, results: [] })),
    // Fail closed: if config can't be read, treat payments as unavailable.
    api.config.get().catch(() => null),
  ]);
  const paymentsEnabled = config?.payments_enabled ?? false;
  const firstName = mentor.display_name.split(" ")[0] ?? mentor.display_name;
  const cheapest = mentor.starting_price;

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-6 text-sm text-muted-foreground">
        <ol className="flex items-center gap-1">
          <li>
            <Link href="/mentors" className="hover:text-foreground">
              Mentors
            </Link>
          </li>
          <li aria-hidden="true">
            <ChevronRight className="size-4" />
          </li>
          <li aria-current="page" className="truncate text-foreground">
            {mentor.display_name}
          </li>
        </ol>
      </nav>

      <ProfileHeader
        mentor={mentor}
        actions={
          <>
            <Button asChild size="lg">
              <a href="#book">
                <CalendarCheck aria-hidden="true" />
                Book a session
              </a>
            </Button>
            <SaveMentorButton mentorId={mentor.slug} />
          </>
        }
      />

      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-[1fr_24rem]">
        <div className="grid min-w-0 gap-12">
          <section aria-labelledby="about-heading">
            <h2 id="about-heading" className="text-xl font-semibold">
              About {firstName}
            </h2>
            <div className="mt-3 grid max-w-prose gap-3 leading-relaxed">
              {mentor.bio.split(/\n{2,}/).map((paragraph, i) => (
                <p key={i}>{paragraph}</p>
              ))}
            </div>
          </section>

          <section aria-labelledby="expertise-heading">
            <h2 id="expertise-heading" className="text-xl font-semibold">
              Expertise
            </h2>
            <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {mentor.profession ? (
                <div>
                  <dt className="text-sm text-muted-foreground">Profession</dt>
                  <dd className="mt-1">{mentor.profession.name}</dd>
                </div>
              ) : null}
              <div>
                <dt className="text-sm text-muted-foreground">Industries</dt>
                <dd className="mt-1 flex flex-wrap gap-1.5">
                  {mentor.industries.map((industry) => (
                    <Link
                      key={industry.id}
                      href={mentorsHref({ industry: industry.slug })}
                      className="rounded-full bg-secondary px-2.5 py-0.5 text-sm text-secondary-foreground hover:underline"
                    >
                      {industry.name}
                    </Link>
                  ))}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-sm text-muted-foreground">Skills</dt>
                <dd className="mt-1">
                  <ul className="flex flex-wrap gap-1.5">
                    {mentor.skills.map((skill) => (
                      <li key={skill.id} className="rounded-full bg-muted px-2.5 py-0.5 text-sm">
                        {skill.name}
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-sm text-muted-foreground">Languages</dt>
                <dd className="mt-1">{mentor.languages.map(languageName).join(", ")}</dd>
              </div>
            </dl>
          </section>

          {mentor.experiences.length > 0 ? (
            <section aria-labelledby="experience-heading">
              <h2 id="experience-heading" className="mb-5 text-xl font-semibold">
                Experience
              </h2>
              <ExperienceTimeline experiences={mentor.experiences} />
            </section>
          ) : null}

          <section aria-labelledby="services-heading">
            <h2 id="services-heading" className="mb-4 text-xl font-semibold">
              Mentorship services
            </h2>
            {mentor.services.length > 0 ? (
              <ServiceList services={mentor.services} mentorSlug={mentor.slug} paymentsEnabled={paymentsEnabled} />
            ) : (
              <p className="text-muted-foreground">{firstName} hasn&apos;t published any services yet.</p>
            )}
          </section>

          <section aria-labelledby="reviews-heading">
            <h2 id="reviews-heading" className="text-xl font-semibold">
              Reviews
            </h2>
            <p className="mt-1 mb-4 text-sm text-muted-foreground">
              Reviews can only be left by students after a completed session.
            </p>
            <ReviewList mentorId={mentor.slug} initial={reviews} />
          </section>
        </div>

        <aside id="book" aria-labelledby="book-heading" className="min-w-0 scroll-mt-24 lg:sticky lg:top-24 lg:self-start">
          <div className="min-w-0 rounded-xl border bg-card p-5 shadow-sm">
            <h2 id="book-heading" className="text-lg font-semibold">
              Book a session
            </h2>
            <p className="mt-1 mb-5 text-sm text-muted-foreground">
              Pick a service and a time that works for you.
            </p>
            <BookingWidget
              key={initialServiceId ?? "default"}
              mentorId={mentor.slug}
              mentorFirstName={firstName}
              services={mentor.services}
              initialServiceId={initialServiceId}
              paymentsEnabled={paymentsEnabled}
              paymentsLivemode={config?.payments_livemode ?? false}
              freeCancellationHours={config?.free_cancellation_hours ?? 24}
            />
          </div>
        </aside>
      </div>

      {/* Mobile: keep the booking action within reach. */}
      <div className="sticky bottom-0 z-30 -mx-4 mt-10 flex items-center justify-between gap-4 border-t bg-background/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:hidden">
        <PriceDisplay price={cheapest} from />
        <Button asChild>
          <a href="#book">Book a session</a>
        </Button>
      </div>
    </>
  );
}

function ProfileSkeleton() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading mentor profile…</span>
      <div className="flex flex-col gap-6 sm:flex-row" aria-hidden="true">
        <Skeleton className="size-24 rounded-full sm:size-28" />
        <div className="flex-1 space-y-3">
          <Skeleton className="h-9 w-64" />
          <Skeleton className="h-5 w-80 max-w-full" />
          <Skeleton className="h-5 w-full max-w-xl" />
        </div>
      </div>
      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-[1fr_24rem]" aria-hidden="true">
        <div className="space-y-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-40 w-full" />
        </div>
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    </div>
  );
}
