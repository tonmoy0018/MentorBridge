/**
 * Typed data models shared by the UI, the live API client and the mock data layer.
 * Mirrors docs/API_SPECIFICATION.md. Once the Django API exists these are replaced by
 * types generated from its OpenAPI schema (`pnpm gen:api`).
 */

import type { components } from "./generated";

export type Role = "student" | "mentor" | "admin";

/** ISO 3166-1 alpha-2 codes accepted by the backend. */
export type CountryCode = components["schemas"]["CountryEnum"];

export interface Money {
  /** Integer minor units (e.g. cents). Never use floats for money. */
  amount_cents: number;
  /** ISO 4217 code, e.g. "USD". */
  currency: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/* ---------- Accounts ---------- */

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
  timezone: string;
  email_verified: boolean;
  /** Trusted from the backend: role=admin AND staff. Gates the admin dashboard. */
  is_admin: boolean;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: Exclude<Role, "admin">;
  timezone: string;
}

export interface UpdateAccountInput {
  first_name: string;
  last_name: string;
  timezone: string;
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export interface PasswordResetConfirmInput {
  uid: string;
  token: string;
  new_password: string;
}

/* ---------- Taxonomy ---------- */

export interface TaxonomyItem {
  id: number;
  name: string;
  slug: string;
}

export interface Language {
  code: string;
  name: string;
}

export interface Country {
  code: string;
  name: string;
}

export interface Taxonomy {
  industries: TaxonomyItem[];
  professions: TaxonomyItem[];
  skills: TaxonomyItem[];
  languages: Language[];
  countries: Country[];
}

/** An industry with the number of approved mentors in it (for category cards). */
export interface IndustryWithCount extends TaxonomyItem {
  mentor_count: number;
}

/* ---------- Mentors (public) ---------- */

export interface MentorSummary {
  id: string;
  slug: string;
  display_name: string;
  headline: string;
  avatar_url: string | null;
  current_title: string;
  current_company: string;
  profession: TaxonomyItem | null;
  industries: TaxonomyItem[];
  skills: TaxonomyItem[];
  /** ISO 3166-1 alpha-2. */
  country: string | null;
  city: string;
  /** ISO 639-1 codes. */
  languages: string[];
  years_experience: number;
  /** True only when the backend reports verification_status = approved. */
  is_verified: boolean;
  /** Decimal string, e.g. "4.80"; null when there are no reviews. */
  rating_avg: string | null;
  rating_count: number;
  starting_price: Money | null;
  /** Earliest bookable slot (UTC ISO), null if nothing open in the booking horizon. */
  next_available_at: string | null;
}

export type ExperienceKind = "work" | "education";

export interface MentorExperience {
  id: string;
  kind: ExperienceKind;
  title: string;
  organization: string;
  /** YYYY-MM-DD */
  start_date: string;
  end_date: string | null;
  description: string;
}

export interface MentorService {
  id: string;
  title: string;
  description: string;
  duration_minutes: number;
  price: Money;
  is_active: boolean;
}

export interface MentorProfile extends MentorSummary {
  bio: string;
  timezone: string;
  experiences: MentorExperience[];
  /** Active services only. */
  services: MentorService[];
}

export interface Review {
  id: string;
  rating: number;
  comment: string;
  created_at: string;
  reviewer_display_name: string;
  service_title: string;
}

export interface AvailabilityResponse {
  mentor_timezone: string;
  service_id: string;
  duration_minutes: number;
  /** Bookable start times, UTC ISO 8601. */
  slots: string[];
}

export type MentorSort = "relevance" | "price_asc" | "price_desc" | "rating";

export interface MentorSearchParams {
  q?: string;
  industry?: string;
  skill?: string;
  country?: string;
  language?: string;
  /** Whole currency units (UI), converted to cents by the live client. */
  price_min?: number;
  price_max?: number;
  /** Only mentors with an open slot within this many days. */
  available_within?: number;
  sort?: MentorSort;
  page?: number;
  page_size?: number;
}

/* ---------- Bookings ---------- */

export type BookingStatus =
  | "pending_payment"
  | "requested"
  | "confirmed"
  | "completed"
  | "declined"
  | "cancelled"
  | "expired";

export interface BookingParty {
  id: string;
  display_name: string;
  avatar_url: string | null;
}

/** How a cancellation affects payment ("" = not applicable, e.g. a free session). */
export type RefundOutcome = "" | "not_charged" | "full_refund" | "no_refund";

export interface Booking {
  id: string;
  status: BookingStatus;
  start_at: string;
  end_at: string;
  service_title: string;
  duration_minutes: number;
  price: Money;
  student_note: string;
  /** Only present once the booking is confirmed. */
  meeting_url: string | null;
  mentor: BookingParty & { slug: string; headline: string };
  student: BookingParty;
  hold_expires_at: string | null;
  respond_by: string | null;
  confirmed_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string;
  refund_outcome: RefundOutcome;
  has_review: boolean;
  created_at: string;
}

export type BookingScope = "upcoming" | "past" | "all";

export interface BookingListParams {
  scope?: BookingScope;
  status?: BookingStatus[];
}

export interface CreateBookingInput {
  service_id: string;
  start_at: string;
  student_note: string;
}

export interface ReviewInput {
  rating: number;
  comment: string;
}

/* ---------- Student ---------- */

export type GoalStatus = "not_started" | "in_progress" | "achieved" | "archived";

export interface CareerGoal {
  id: string;
  title: string;
  description: string;
  status: GoalStatus;
  /** YYYY-MM-DD */
  target_date: string | null;
  achieved_at: string | null;
  created_at: string;
}

export interface GoalInput {
  title: string;
  description: string;
  status: GoalStatus;
  target_date: string | null;
}

/* ---------- Mentor self-service ---------- */

export type VerificationStatus = "draft" | "pending" | "approved" | "rejected" | "suspended";

export interface MentorOwnProfile {
  id: string;
  slug: string;
  headline: string;
  bio: string;
  current_title: string;
  current_company: string;
  profession_id: number | null;
  industry_ids: number[];
  skill_ids: number[];
  language_codes: string[];
  country: string | null;
  city: string;
  timezone: string;
  years_experience: number;
  linkedin_url: string;
  meeting_url: string;
  avatar_url: string | null;
  email_verified: boolean;
  verification_status: VerificationStatus;
  /** Admin's reason, present when verification_status = rejected. */
  verification_decision_reason: string | null;
  is_accepting_bookings: boolean;
  auto_accept: boolean;
  min_notice_hours: number;
  booking_horizon_days: number;
  buffer_minutes: number;
  experiences: MentorExperience[];
  rating_avg: string | null;
  rating_count: number;
  /** Platform commission on this mentor's sessions, in basis points (1500 = 15%). Set by admins. */
  commission_bps: number;
}

export type MentorProfileInput = Omit<
  MentorOwnProfile,
  | "id"
  | "slug"
  | "verification_status"
  | "verification_decision_reason"
  | "experiences"
  | "rating_avg"
  | "rating_count"
  | "avatar_url"
  | "email_verified"
  | "country"
  | "commission_bps"
> & { country: CountryCode | "" };

export type ExperienceInput = Omit<MentorExperience, "id">;

/** Session lengths the backend accepts. */
export const SERVICE_DURATIONS = [15, 30, 45, 60, 90, 120, 180] as const;
export type ServiceDuration = (typeof SERVICE_DURATIONS)[number];

export interface ServiceInput {
  title: string;
  description: string;
  duration_minutes: ServiceDuration;
  price_cents: number;
  is_active: boolean;
}

export interface AvailabilityRule {
  /** 0 = Monday … 6 = Sunday */
  weekday: number;
  /** "HH:MM" in the mentor's timezone */
  start_time: string;
  end_time: string;
}

export interface EarningsSummary {
  pending: Money;
  available: Money;
  paid_out: Money;
  lifetime: Money;
}

export type LedgerKind = "earning" | "refund_reversal" | "payout" | "adjustment";

export interface LedgerEntry {
  id: string;
  kind: LedgerKind;
  amount: Money;
  description: string;
  booking_id: string | null;
  created_at: string;
  available_at: string | null;
}

export type PayoutStatus = "pending" | "paid" | "failed" | "cancelled";

export interface Payout {
  id: string;
  amount: Money;
  status: PayoutStatus;
  method: string;
  external_reference: string;
  created_at: string;
  paid_at: string | null;
}

/* ---------- Admin ---------- */

/** Money for one mode (live or test) over a period. */
export interface FinanceTotals {
  gross_booking_value: Money;
  platform_commission: Money;
  refunds: Money;
  net_platform_revenue: Money;
  provider_fees: Money;
  captured_payments: number;
}

export interface AdminStats {
  users: Record<Role, number>;
  mentors_by_status: Record<VerificationStatus, number>;
  bookings_by_status: Record<BookingStatus, number>;
  /** All-time live (real-money) totals. Test-mode payments are never counted here. */
  gross_booking_value: Money;
  /** Net platform revenue: commission minus commission reversed by refunds. */
  platform_fees: Money;
  refunds: Money;
  period: {
    from: string;
    to: string;
    new_users: number;
    bookings_created: number;
    sessions_completed: number;
    live: FinanceTotals;
    /** Sandbox payments: shown separately and never treated as revenue. */
    test: FinanceTotals;
  };
}

export interface AdminStatsParams {
  /** YYYY-MM-DD (UTC), inclusive. Defaults to the last 30 days. */
  from?: string;
  to?: string;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  date_joined: string;
  last_login: string | null;
}

export interface AdminUserParams {
  q?: string;
  role?: Role;
  page?: number;
}

export type VerificationRequestStatus = "pending" | "approved" | "rejected" | "withdrawn";

export interface VerificationRequest {
  id: string;
  status: VerificationRequestStatus;
  evidence_note: string;
  submitted_at: string;
  reviewed_at: string | null;
  decision_reason: string | null;
  mentor: {
    id: string;
    slug: string;
    display_name: string;
    headline: string;
    current_title: string;
    current_company: string;
    linkedin_url: string;
    years_experience: number;
    country: string | null;
  };
}

export type PaymentStatus = "created" | "authorized" | "captured" | "failed" | "cancelled";
export type RefundStatus = "none" | "pending" | "partial" | "full" | "failed";
export type DisputeStatus = "none" | "open" | "won" | "lost";

/** Written only from provider data (verified webhooks / API responses); read-only here. */
export interface PaymentRecord {
  id: string;
  booking_id: string;
  student_display_name: string;
  mentor_display_name: string;
  amount: Money;
  commission_bps: number;
  platform_fee: Money;
  mentor_share: Money;
  provider_fee: Money | null;
  refunded: Money;
  refundable: Money;
  status: PaymentStatus;
  refund_status: RefundStatus;
  dispute_status: DisputeStatus;
  provider: string;
  provider_reference: string | null;
  /** False for provider test/sandbox payments, which are never revenue. */
  livemode: boolean;
  failure_code: string;
  created_at: string;
  captured_at: string | null;
}

export type RefundRecordStatus = "pending" | "succeeded" | "failed";
export type RefundReason = "student_cancellation" | "mentor_cancellation" | "admin" | "dispute_lost";

export interface RefundRecord {
  id: string;
  payment_id: string;
  booking_id: string;
  amount: Money;
  commission_reversed: Money;
  mentor_share_reversed: Money;
  reason: RefundReason;
  status: RefundRecordStatus;
  provider_reference: string | null;
  failure_code: string;
  note: string;
  initiated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface RefundInput {
  /** Minor units. Omit to refund everything still refundable. */
  amount_cents?: number;
  note: string;
}

/** The provider's hosted checkout for a held booking. */
export interface Checkout {
  payment_id: string;
  checkout_url: string;
  expires_at: string;
  livemode: boolean;
}

export interface AdminCancelInput {
  reason: string;
  /** Refund a captured payment in full. */
  refund: boolean;
}

export type ReviewStatus = "published" | "hidden";

export interface AdminReview {
  id: string;
  rating: number;
  comment: string;
  status: ReviewStatus;
  hidden_reason: string;
  reviewer_name: string;
  mentor_name: string;
  mentor_slug: string;
  booking_id: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  target_type: string;
  target_id: string;
  metadata: unknown;
  actor_name: string;
  created_at: string;
}

export type NotificationStatus = "queued" | "sent" | "failed" | "skipped";

/** Email delivery record. Deliberately carries no address or content. */
export interface AdminNotification {
  id: string;
  template: string;
  status: NotificationStatus;
  attempts: number;
  last_error: string;
  recipient_name: string;
  sent_at: string | null;
  created_at: string;
}

export type ReportStatus = "open" | "in_review" | "actioned" | "dismissed";
export type ReportReason = "spam" | "inappropriate" | "misleading" | "harassment" | "no_show" | "other";

export interface ContentReport {
  id: string;
  target_type: "review" | "mentor_profile" | "user" | "booking";
  target_id: string;
  target_label: string;
  reason: ReportReason;
  details: string;
  status: ReportStatus;
  reporter_display_name: string;
  created_at: string;
  resolution_note: string;
  resolved_at: string | null;
}

export interface ResolveReportInput {
  resolution: "actioned" | "dismissed";
  note: string;
  /** Hide the reported review (review reports only). */
  hide_review: boolean;
}

/** Public marketplace settings from GET /config/. */
export interface PublicConfig {
  payments_enabled: boolean;
  /** True only with live provider keys. False means sandbox: no real money moves. */
  payments_livemode: boolean;
  currency: string;
  booking_hold_minutes: number;
  mentor_response_hours: number;
  free_cancellation_hours: number;
  require_verified_email: boolean;
}
