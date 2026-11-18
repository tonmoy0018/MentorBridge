import type { MentorPackage, MentorService, Money, SessionFormat } from "@/lib/api/types";

export const FORMAT_LABEL: Record<SessionFormat, string> = {
  online: "Online",
  in_person: "In person",
};

/** The formats a service is offered in, online first. */
export function serviceFormats(service: MentorService): SessionFormat[] {
  return [...(service.online ? (["online"] as const) : []), ...(service.in_person ? (["in_person"] as const) : [])];
}

/** What one session of `service` costs in `format` (in person adds the extra). */
export function sessionPrice(service: MentorService, format: SessionFormat): Money {
  const extra = format === "in_person" ? service.in_person_extra.amount_cents : 0;
  return { amount_cents: service.price.amount_cents + extra, currency: service.price.currency };
}

/** What a multi-session option costs in `format` (null if the service isn't offered so). */
export function packagePrice(pkg: MentorPackage, format: SessionFormat): Money | null {
  return pkg.prices[format];
}

/** How much a multi-session option saves compared with booking its sessions one by one. */
export function packageSaving(pkg: MentorPackage, format: SessionFormat): Money | null {
  const price = pkg.prices[format];
  const regular = pkg.regular_prices[format];
  if (!price || !regular) return null;
  const saving = regular.amount_cents - price.amount_cents;
  return saving > 0 ? { amount_cents: saving, currency: price.currency } : null;
}

/** Price per session in a multi-session option, rounded down to the cent. */
export function perSessionPrice(pkg: MentorPackage, format: SessionFormat): Money | null {
  const price = pkg.prices[format];
  return price ? { amount_cents: Math.floor(price.amount_cents / pkg.session_count), currency: price.currency } : null;
}
