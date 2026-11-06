/**
 * Compile-time contract check between the hand-written UI types (types.ts) and the types
 * generated from the backend's OpenAPI schema (generated.ts, via `pnpm gen:api`).
 *
 * - Responses: what the backend returns must be assignable to what the UI reads, so the UI
 *   can't depend on a field the API doesn't provide.
 * - Requests: what the UI sends must be assignable to what the API accepts.
 *
 * `pnpm typecheck` fails if either side drifts. This file has no runtime code.
 */
import type { components } from "./generated";
import type * as T from "./types";

type S = components["schemas"];
type Assert<Ok extends true> = Ok;
type Fits<Source, Target> = [Source] extends [Target] ? true : false;

/* Responses: backend → UI */
export type _CurrentUser = Assert<Fits<S["CurrentUser"], T.CurrentUser>>;
export type _MentorSummary = Assert<Fits<S["MentorSummary"], T.MentorSummary>>;
export type _MentorProfile = Assert<Fits<S["MentorPublicProfile"], T.MentorProfile>>;
export type _MentorPage = Assert<Fits<S["PaginatedMentorSummaryList"], T.Paginated<T.MentorSummary>>>;
export type _Review = Assert<Fits<S["Review"], T.Review>>;
export type _Availability = Assert<Fits<S["AvailabilityResponse"], T.AvailabilityResponse>>;
export type _Booking = Assert<Fits<S["Booking"], T.Booking>>;
export type _BookingDetail = Assert<Fits<S["BookingDetail"], T.Booking>>;
export type _BookingPage = Assert<Fits<S["PaginatedBookingList"], T.Paginated<T.Booking>>>;
export type _Goal = Assert<Fits<S["CareerGoal"], T.CareerGoal>>;
export type _OwnProfile = Assert<Fits<S["MentorOwnProfile"], T.MentorOwnProfile>>;
export type _Experience = Assert<Fits<S["Experience"], T.MentorExperience>>;
export type _Service = Assert<Fits<S["Service"], T.MentorService>>;
export type _Rule = Assert<Fits<S["AvailabilityRule"], T.AvailabilityRule>>;
export type _Earnings = Assert<Fits<S["EarningsSummary"], T.EarningsSummary>>;
export type _Ledger = Assert<Fits<S["LedgerEntry"], T.LedgerEntry>>;
export type _Payout = Assert<Fits<S["Payout"], T.Payout>>;
export type _Category = Assert<Fits<S["Category"], T.TaxonomyItem>>;
export type _Language = Assert<Fits<S["Language"], T.Language>>;
export type _Country = Assert<Fits<S["Country"], T.Country>>;
export type _AdminStats = Assert<Fits<S["AdminStats"], T.AdminStats>>;
export type _AdminUser = Assert<Fits<S["AdminUser"], T.AdminUser>>;
export type _Verification = Assert<Fits<S["VerificationRequest"], T.VerificationRequest>>;
export type _Payment = Assert<Fits<S["AdminPayment"], T.PaymentRecord>>;
export type _Refund = Assert<Fits<S["Refund"], T.RefundRecord>>;
export type _Checkout = Assert<Fits<S["Checkout"], T.Checkout>>;
export type _AdminReview = Assert<Fits<S["AdminReview"], T.AdminReview>>;
export type _AuditLog = Assert<Fits<S["AuditLogEntry"], T.AuditLogEntry>>;
export type _Notification = Assert<Fits<S["AdminNotification"], T.AdminNotification>>;
export type _Report = Assert<Fits<S["AdminReport"], T.ContentReport>>;
export type _Config = Assert<Fits<S["PublicConfig"], T.PublicConfig>>;

/* Requests: UI → backend */
export type _RegisterIn = Assert<Fits<T.RegisterInput, S["RegisterRequest"]>>;
export type _LoginIn = Assert<Fits<T.LoginInput, S["LoginRequest"]>>;
export type _AccountIn = Assert<Fits<T.UpdateAccountInput, S["PatchedUpdateMeRequest"]>>;
export type _PasswordIn = Assert<Fits<T.ChangePasswordInput, S["PasswordChangeRequest"]>>;
export type _ResetIn = Assert<Fits<T.PasswordResetConfirmInput, S["PasswordResetConfirmRequest"]>>;
export type _BookingIn = Assert<Fits<T.CreateBookingInput, S["CreateBookingRequest"]>>;
export type _GoalIn = Assert<Fits<T.GoalInput, S["CareerGoalRequest"]>>;
export type _ProfileIn = Assert<Fits<Partial<T.MentorProfileInput>, S["PatchedMentorProfileUpdateRequest"]>>;
export type _ExperienceIn = Assert<Fits<T.ExperienceInput, S["ExperienceRequest"]>>;
export type _ServiceIn = Assert<Fits<T.ServiceInput, S["ServiceWriteRequest"]>>;
export type _RuleIn = Assert<Fits<T.AvailabilityRule, S["AvailabilityRuleRequest"]>>;
export type _ResolveIn = Assert<Fits<T.ResolveReportInput, S["ResolveReportRequest"]>>;
export type _ReviewIn = Assert<Fits<T.ReviewInput, S["CreateReviewRequest"]>>;
export type _RefundIn = Assert<Fits<T.RefundInput, S["AdminRefundRequestRequest"]>>;
export type _AdminCancelIn = Assert<Fits<T.AdminCancelInput, S["AdminCancelRequest"]>>;
