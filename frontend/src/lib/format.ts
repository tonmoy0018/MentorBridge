import type { Money } from "@/lib/api/types";

const LOCALE = "en-US";

export function formatMoney(money: Money, options: { showFree?: boolean } = {}): string {
  if (money.amount_cents === 0 && options.showFree !== false) return "Free";
  const whole = money.amount_cents % 100 === 0;
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: money.currency,
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(money.amount_cents / 100);
}

export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const h = `${hours} hr`;
  return rest ? `${h} ${rest} min` : h;
}

function safeTimeZone(timeZone: string | undefined): string | undefined {
  if (!timeZone) return undefined;
  try {
    new Intl.DateTimeFormat(LOCALE, { timeZone });
    return timeZone;
  } catch {
    return undefined;
  }
}

/** e.g. "Tue, Nov 3, 2026" */
export function formatDate(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: safeTimeZone(timeZone),
  }).format(new Date(iso));
}

/** e.g. "Nov 3, 2026" — for YYYY-MM-DD values (interpreted as calendar dates, not instants). */
export function formatCalendarDate(ymd: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${ymd}T00:00:00Z`));
}

/** e.g. "Mar 2021" */
export function formatMonthYear(ymd: string): string {
  return new Intl.DateTimeFormat(LOCALE, { month: "short", year: "numeric", timeZone: "UTC" }).format(
    new Date(`${ymd}T00:00:00Z`),
  );
}

/** e.g. "2:30 PM" */
export function formatTime(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    hour: "numeric",
    minute: "2-digit",
    timeZone: safeTimeZone(timeZone),
  }).format(new Date(iso));
}

/** e.g. "Tue, Nov 3 · 2:30 PM" */
export function formatDateTime(iso: string, timeZone?: string): string {
  const day = new Intl.DateTimeFormat(LOCALE, {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: safeTimeZone(timeZone),
  }).format(new Date(iso));
  return `${day} · ${formatTime(iso, timeZone)}`;
}

/** Short timezone label such as "GMT" or "PST" for the given zone at the given instant. */
export function timeZoneLabel(timeZone: string | undefined, at: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat(LOCALE, {
    timeZone: safeTimeZone(timeZone),
    timeZoneName: "short",
  }).formatToParts(at);
  return parts.find((p) => p.type === "timeZoneName")?.value ?? "";
}

const regionNames = new Intl.DisplayNames([LOCALE], { type: "region" });
const languageNames = new Intl.DisplayNames([LOCALE], { type: "language" });

export function countryName(code: string | null | undefined): string {
  if (!code) return "";
  try {
    return regionNames.of(code.toUpperCase()) ?? code;
  } catch {
    return code;
  }
}

export function languageName(code: string): string {
  try {
    return languageNames.of(code) ?? code;
  } catch {
    return code;
  }
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

/** The browser's IANA time zone, falling back to UTC. */
export function detectTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}
