import type { AuthApi, DataApi } from "./contract";
import type { Transport } from "./http";
import type { Booking, MentorSearchParams, MentorSort, Paginated } from "./types";

const ORDERING: Record<MentorSort, string | undefined> = {
  relevance: undefined,
  price_asc: "min_price_cents",
  price_desc: "-min_price_cents",
  rating: "-rating_avg",
};

/** Maps UI search params (whole currency units, friendly sort keys) to API query params. */
export function toMentorQuery(params: MentorSearchParams) {
  return {
    q: params.q,
    industry: params.industry,
    skill: params.skill,
    country: params.country,
    language: params.language,
    price_min: params.price_min !== undefined ? Math.round(params.price_min * 100) : undefined,
    price_max: params.price_max !== undefined ? Math.round(params.price_max * 100) : undefined,
    available_within_days: params.available_within,
    ordering: params.sort ? ORDERING[params.sort] : undefined,
    page: params.page,
    page_size: params.page_size,
  };
}

const id = (value: string) => encodeURIComponent(value);

export function createLiveAuthApi(request: Transport): AuthApi {
  return {
    login: (input) => request("/auth/login/", { method: "POST", body: input }),
    register: (input) => request("/auth/register/", { method: "POST", body: input }),
    logout: () => request("/auth/logout/", { method: "POST" }),
    me: () => request("/auth/me/"),
    changePassword: (input) => request("/auth/password/change/", { method: "POST", body: input }),
    requestPasswordReset: (email) =>
      request("/auth/password/reset/", { method: "POST", body: { email } }),
    confirmPasswordReset: (input) =>
      request("/auth/password/reset/confirm/", { method: "POST", body: input }),
    verifyEmail: (input) => request("/auth/email/verify/", { method: "POST", body: input }),
    resendVerificationEmail: () => request("/auth/email/verify/resend/", { method: "POST" }),
  };
}

export function createLiveDataApi(request: Transport): DataApi {
  const action = (bookingId: string, verb: string, body?: unknown) =>
    request<Booking>(`/bookings/${id(bookingId)}/${verb}/`, { method: "POST", body });

  return {
    config: {
      get: () => request("/config/"),
    },
    account: {
      update: (input) => request("/auth/me/", { method: "PATCH", body: input }),
    },
    taxonomy: {
      get: async () => {
        const [industries, professions, skills, languages, countries] = await Promise.all([
          request<DataTaxonomy["industries"]>("/categories/"),
          request<DataTaxonomy["professions"]>("/taxonomy/professions/"),
          request<DataTaxonomy["skills"]>("/taxonomy/skills/"),
          request<DataTaxonomy["languages"]>("/taxonomy/languages/"),
          request<DataTaxonomy["countries"]>("/taxonomy/countries/"),
        ]);
        return { industries, professions, skills, languages, countries };
      },
      industriesWithCounts: () =>
        request("/categories/", { query: { with_counts: true } }),
    },
    mentors: {
      search: (params) => request("/mentors/", { query: toMentorQuery(params) }),
      get: (mentorId) => request(`/mentors/${id(mentorId)}/`),
      reviews: (mentorId, page = 1) =>
        request(`/mentors/${id(mentorId)}/reviews/`, { query: { page } }),
      availability: (mentorId, params) =>
        request(`/mentors/${id(mentorId)}/availability/`, { query: params }),
    },
    bookings: {
      list: (params = {}) =>
        request("/bookings/", { query: { scope: params.scope, status: params.status } }),
      get: (bookingId) => request(`/bookings/${id(bookingId)}/`),
      create: (input) => request("/bookings/", { method: "POST", body: input }),
      cancel: (bookingId, reason) => action(bookingId, "cancel", { reason }),
      accept: (bookingId) => action(bookingId, "accept"),
      decline: (bookingId, reason) => action(bookingId, "decline", { reason }),
      complete: (bookingId) => action(bookingId, "complete"),
      review: (bookingId, input) =>
        request(`/bookings/${id(bookingId)}/review/`, { method: "POST", body: input }),
      checkout: (bookingId) => request(`/bookings/${id(bookingId)}/checkout/`, { method: "POST" }),
    },
    student: {
      savedMentors: () => request("/me/student/saved-mentors/"),
      saveMentor: (mentorId) =>
        request(`/me/student/saved-mentors/${id(mentorId)}/`, { method: "PUT" }),
      unsaveMentor: (mentorId) =>
        request(`/me/student/saved-mentors/${id(mentorId)}/`, { method: "DELETE" }),
      goals: async () =>
        (await request<Paginated<DataGoal>>("/me/student/goals/", { query: { page_size: 50 } }))
          .results,
      createGoal: (input) => request("/me/student/goals/", { method: "POST", body: input }),
      updateGoal: (goalId, input) =>
        request(`/me/student/goals/${id(goalId)}/`, { method: "PATCH", body: input }),
      deleteGoal: (goalId) => request(`/me/student/goals/${id(goalId)}/`, { method: "DELETE" }),
    },
    mentor: {
      profile: () => request("/me/mentor/profile/"),
      updateProfile: (input) => request("/me/mentor/profile/", { method: "PATCH", body: input }),
      createExperience: (input) =>
        request("/me/mentor/experiences/", { method: "POST", body: input }),
      updateExperience: (expId, input) =>
        request(`/me/mentor/experiences/${id(expId)}/`, { method: "PATCH", body: input }),
      deleteExperience: (expId) =>
        request(`/me/mentor/experiences/${id(expId)}/`, { method: "DELETE" }),
      services: async () =>
        (await request<Paginated<DataService>>("/me/mentor/services/", { query: { page_size: 50 } }))
          .results,
      createService: (input) => request("/me/mentor/services/", { method: "POST", body: input }),
      updateService: (serviceId, input) =>
        request(`/me/mentor/services/${id(serviceId)}/`, { method: "PATCH", body: input }),
      availabilityRules: () => request("/me/mentor/availability/rules/"),
      replaceAvailabilityRules: (rules) =>
        request("/me/mentor/availability/rules/", { method: "PUT", body: rules }),
      submitVerification: (evidenceNote) =>
        request("/me/mentor/verification/", {
          method: "POST",
          body: { evidence_note: evidenceNote },
        }),
      earningsSummary: () => request("/me/mentor/earnings/summary/"),
      ledger: () => request("/me/mentor/earnings/ledger/"),
      payouts: () => request("/me/mentor/payouts/"),
    },
    admin: {
      stats: (params = {}) => request("/admin/stats/", { query: { ...params } }),
      users: (params = {}) => request("/admin/users/", { query: { ...params } }),
      suspendUser: (userId, reason) =>
        request(`/admin/users/${id(userId)}/suspend/`, { method: "POST", body: { reason } }),
      reactivateUser: (userId) =>
        request(`/admin/users/${id(userId)}/reactivate/`, { method: "POST" }),
      verificationRequests: (status) =>
        request("/admin/verification-requests/", { query: { status } }),
      approveVerification: (requestId) =>
        request(`/admin/verification-requests/${id(requestId)}/approve/`, { method: "POST" }),
      rejectVerification: (requestId, reason) =>
        request(`/admin/verification-requests/${id(requestId)}/reject/`, {
          method: "POST",
          body: { reason },
        }),
      bookings: (params = {}) => request("/admin/bookings/", { query: { ...params } }),
      cancelBooking: (bookingId, input) =>
        request(`/admin/bookings/${id(bookingId)}/cancel/`, { method: "POST", body: input }),
      payments: (params = {}) => request("/admin/payments/", { query: { ...params } }),
      refundPayment: (paymentId, input) =>
        request(`/admin/payments/${id(paymentId)}/refund/`, { method: "POST", body: input }),
      refunds: () => request("/admin/refunds/"),
      reviews: (params = {}) => request("/admin/reviews/", { query: { ...params } }),
      hideReview: (reviewId, reason) =>
        request(`/admin/reviews/${id(reviewId)}/hide/`, { method: "POST", body: { reason } }),
      publishReview: (reviewId) =>
        request(`/admin/reviews/${id(reviewId)}/publish/`, { method: "POST", body: {} }),
      auditLog: (params = {}) => request("/admin/audit-log/", { query: { ...params } }),
      notifications: (params = {}) => request("/admin/notifications/", { query: { ...params } }),
      reports: (status) => request("/admin/reports/", { query: { status } }),
      resolveReport: (reportId, input) =>
        request(`/admin/reports/${id(reportId)}/resolve/`, { method: "POST", body: input }),
    },
  };
}

type DataTaxonomy = Awaited<ReturnType<DataApi["taxonomy"]["get"]>>;
type DataGoal = Awaited<ReturnType<DataApi["student"]["goals"]>>[number];
type DataService = Awaited<ReturnType<DataApi["mentor"]["services"]>>[number];
