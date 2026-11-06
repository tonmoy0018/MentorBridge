import { Clock } from "lucide-react";
import Link from "next/link";
import type { MentorService } from "@/lib/api/types";
import { formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { PriceDisplay } from "./price-display";

/** Public list of a mentor's services. "Choose" preselects the service in the booking panel. */
export function ServiceList({
  services,
  mentorSlug,
  paymentsEnabled,
}: {
  services: MentorService[];
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
            <p className="mt-2 flex items-center gap-1.5 text-sm text-muted-foreground">
              <Clock className="size-4" aria-hidden="true" />
              {formatDuration(service.duration_minutes)}
            </p>
          </div>
          <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
            <div className="text-right">
              <PriceDisplay price={service.price} className="text-lg" />
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
