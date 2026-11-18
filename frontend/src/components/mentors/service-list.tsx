import { Clock, MapPin, Video } from "lucide-react";
import Link from "next/link";
import type { MentorPackage, MentorService } from "@/lib/api/types";
import { formatDuration, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { PriceDisplay } from "./price-display";

/** Public list of a mentor's services. "Choose" preselects the service in the booking panel. */
export function ServiceList({
  services,
  packages = [],
  mentorSlug,
  paymentsEnabled,
}: {
  services: MentorService[];
  /** Multi-session options, shown under their service. */
  packages?: MentorPackage[];
  mentorSlug: string;
  paymentsEnabled: boolean;
}) {
  return (
    <ul className="grid gap-3">
      {services.map((service) => (
        <li key={service.id} className="flex flex-col gap-4 rounded-xl border bg-card p-5 sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold">{service.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{service.description}</p>
            <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Clock className="size-4" aria-hidden="true" />
                {formatDuration(service.duration_minutes)}
              </span>
              {service.online ? (
                <span className="flex items-center gap-1.5">
                  <Video className="size-4" aria-hidden="true" />
                  Online
                </span>
              ) : null}
              {service.in_person ? (
                <span className="flex items-center gap-1.5">
                  <MapPin className="size-4" aria-hidden="true" />
                  In person in {service.in_person_area}
                  {service.online && service.in_person_extra.amount_cents > 0
                    ? ` (+${formatMoney(service.in_person_extra)})`
                    : ""}
                </span>
              ) : null}
            </p>
            {packages.some((p) => p.service.id === service.id) ? (
              <p className="mt-2 flex flex-wrap gap-1.5 text-xs">
                {packages
                  .filter((p) => p.service.id === service.id)
                  .map((p) => (
                    <span key={p.id} className="rounded-full bg-secondary px-2.5 py-0.5 font-medium text-secondary-foreground">
                      {p.session_count} sessions{p.discount_percent > 0 ? ` · save ${p.discount_percent}%` : ""}
                    </span>
                  ))}
              </p>
            ) : null}
          </div>
          <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
            <div className="text-right">
              <PriceDisplay
                price={
                  service.online
                    ? service.price
                    : {
                        amount_cents: service.price.amount_cents + service.in_person_extra.amount_cents,
                        currency: service.price.currency,
                      }
                }
                className="text-lg"
              />
              {!paymentsEnabled && service.price.amount_cents > 0 ? (
                <p className="text-xs text-muted-foreground">Online payment coming soon</p>
              ) : null}
            </div>
            <Link
              href={`/mentors/${encodeURIComponent(mentorSlug)}?service=${encodeURIComponent(service.id)}#book`}
              scroll={false}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              aria-label={`Choose ${service.title}`}
            >
              Choose
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}
