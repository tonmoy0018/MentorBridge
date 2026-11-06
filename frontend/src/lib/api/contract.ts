import type {
  AdminCancelInput,
  AdminNotification,
  AdminReview,
  AdminStats,
  AdminStatsParams,
  AuditLogEntry,
  AdminUser,
  AdminUserParams,
  AvailabilityResponse,
  AvailabilityRule,
  Booking,
  BookingListParams,
  BookingStatus,
  CareerGoal,
  ChangePasswordInput,
  Checkout,
  ContentReport,
  CreateBookingInput,
  CurrentUser,
  EarningsSummary,
  ExperienceInput,
  GoalInput,
  IndustryWithCount,
  LedgerEntry,
  LoginInput,
  MentorExperience,
  MentorOwnProfile,
  MentorProfile,
  MentorProfileInput,
  MentorSearchParams,
  MentorService,
  MentorSummary,
  Paginated,
  PasswordResetConfirmInput,
  PaymentRecord,
  PaymentStatus,
  Payout,
  PublicConfig,
  RefundInput,
  RefundRecord,
  RegisterInput,
  ReportStatus,
  ResolveReportInput,
  Review,
  ReviewStatus,
  ReviewInput,
  ServiceInput,
  Taxonomy,
  UpdateAccountInput,
  VerificationRequest,
  VerificationRequestStatus,
} from "./types";

/** Authentication: session cookie + CSRF against Django (docs/API_SPECIFICATION.md §2, §4). */
export interface AuthApi {
  login(input: LoginInput): Promise<CurrentUser>;
  register(input: RegisterInput): Promise<CurrentUser>;
  logout(): Promise<void>;
  me(): Promise<CurrentUser>;
  changePassword(input: ChangePasswordInput): Promise<void>;
  requestPasswordReset(email: string): Promise<void>;
  confirmPasswordReset(input: PasswordResetConfirmInput): Promise<void>;
  verifyEmail(input: { uid: string; token: string }): Promise<void>;
  resendVerificationEmail(): Promise<void>;
}

/** Everything else (implemented by the Django client in live.ts). */
export interface DataApi {
  config: {
    get(): Promise<PublicConfig>;
  };
  account: {
    update(input: UpdateAccountInput): Promise<CurrentUser>;
  };
  taxonomy: {
    get(): Promise<Taxonomy>;
    industriesWithCounts(): Promise<IndustryWithCount[]>;
  };
  mentors: {
    search(params: MentorSearchParams): Promise<Paginated<MentorSummary>>;
    get(id: string): Promise<MentorProfile>;
    reviews(id: string, page?: number): Promise<Paginated<Review>>;
    availability(
      id: string,
      params: { service: string; from: string; to: string },
    ): Promise<AvailabilityResponse>;
  };
  bookings: {
    list(params?: BookingListParams): Promise<Paginated<Booking>>;
    /** Every booking matching `params`, following pagination (bounded). */
    listAll(params?: BookingListParams): Promise<Booking[]>;
    get(id: string): Promise<Booking>;
    create(input: CreateBookingInput): Promise<Booking>;
    cancel(id: string, reason: string): Promise<Booking>;
    accept(id: string): Promise<Booking>;
    decline(id: string, reason: string): Promise<Booking>;
    complete(id: string): Promise<Booking>;
    review(id: string, input: ReviewInput): Promise<Review>;
    /** Start (or resume) the provider checkout for a booking awaiting payment. */
    checkout(id: string): Promise<Checkout>;
  };
  student: {
    savedMentors(page?: number): Promise<Paginated<MentorSummary>>;
    /** Whether the student has saved this mentor (checks every page of saved mentors). */
    isSaved(mentorIdOrSlug: string): Promise<boolean>;
    saveMentor(mentorId: string): Promise<void>;
    unsaveMentor(mentorId: string): Promise<void>;
    goals(): Promise<CareerGoal[]>;
    createGoal(input: GoalInput): Promise<CareerGoal>;
    updateGoal(id: string, input: Partial<GoalInput>): Promise<CareerGoal>;
    deleteGoal(id: string): Promise<void>;
  };
  mentor: {
    profile(): Promise<MentorOwnProfile>;
    updateProfile(input: Partial<MentorProfileInput>): Promise<MentorOwnProfile>;
    createExperience(input: ExperienceInput): Promise<MentorExperience>;
    updateExperience(id: string, input: ExperienceInput): Promise<MentorExperience>;
    deleteExperience(id: string): Promise<void>;
    services(): Promise<MentorService[]>;
    createService(input: ServiceInput): Promise<MentorService>;
    updateService(id: string, input: Partial<ServiceInput>): Promise<MentorService>;
    availabilityRules(): Promise<AvailabilityRule[]>;
    replaceAvailabilityRules(rules: AvailabilityRule[]): Promise<AvailabilityRule[]>;
    submitVerification(evidenceNote: string): Promise<MentorOwnProfile>;
    earningsSummary(): Promise<EarningsSummary>;
    ledger(page?: number): Promise<Paginated<LedgerEntry>>;
    payouts(page?: number): Promise<Paginated<Payout>>;
  };
  admin: {
    stats(params?: AdminStatsParams): Promise<AdminStats>;
    users(params?: AdminUserParams): Promise<Paginated<AdminUser>>;
    suspendUser(id: string, reason: string): Promise<AdminUser>;
    reactivateUser(id: string): Promise<AdminUser>;
    verificationRequests(status: VerificationRequestStatus, page?: number): Promise<Paginated<VerificationRequest>>;
    approveVerification(id: string): Promise<VerificationRequest>;
    rejectVerification(id: string, reason: string): Promise<VerificationRequest>;
    bookings(params?: { status?: BookingStatus; page?: number }): Promise<Paginated<Booking>>;
    cancelBooking(id: string, input: AdminCancelInput): Promise<Booking>;
    payments(params?: { status?: PaymentStatus; livemode?: boolean; page?: number }): Promise<Paginated<PaymentRecord>>;
    refundPayment(id: string, input: RefundInput): Promise<RefundRecord>;
    refunds(page?: number): Promise<Paginated<RefundRecord>>;
    reviews(params?: { status?: ReviewStatus; page?: number }): Promise<Paginated<AdminReview>>;
    hideReview(id: string, reason: string): Promise<AdminReview>;
    publishReview(id: string): Promise<AdminReview>;
    auditLog(params?: { action?: string; page?: number }): Promise<Paginated<AuditLogEntry>>;
    notifications(params?: { status?: string; page?: number }): Promise<Paginated<AdminNotification>>;
    reports(status: ReportStatus | "resolved", page?: number): Promise<Paginated<ContentReport>>;
    resolveReport(id: string, input: ResolveReportInput): Promise<ContentReport>;
  };
}

export interface MentorBridgeApi extends DataApi {
  auth: AuthApi;
}
