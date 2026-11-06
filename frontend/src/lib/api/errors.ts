/**
 * Normalized API errors. Every failure from the HTTP layer (or the mock layer) is an
 * ApiError so UI code can branch on `kind` instead of raw status codes.
 */
export type ApiErrorKind =
  | "validation" // 400
  | "unauthenticated" // 401 – no or expired session
  | "forbidden" // 403 – wrong role, CSRF failure
  | "not_found" // 404
  | "conflict" // 409 – e.g. slot_unavailable
  | "throttled" // 429
  | "server" // 5xx or unexpected response
  | "network"; // request never completed

export interface ApiErrorInit {
  kind: ApiErrorKind;
  status: number;
  code: string;
  message: string;
  fieldErrors?: Record<string, string[]>;
  retryAfterSeconds?: number;
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: Record<string, string[]>;
  readonly retryAfterSeconds?: number;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = "ApiError";
    this.kind = init.kind;
    this.status = init.status;
    this.code = init.code;
    this.fieldErrors = init.fieldErrors ?? {};
    this.retryAfterSeconds = init.retryAfterSeconds;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function kindForStatus(status: number): ApiErrorKind {
  if (status === 400 || status === 422) return "validation";
  if (status === 401) return "unauthenticated";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 429) return "throttled";
  return "server";
}

const DEFAULT_MESSAGES: Record<ApiErrorKind, string> = {
  validation: "Some of the information you entered needs attention.",
  unauthenticated: "Your session has ended. Please log in again.",
  forbidden: "You don't have permission to do that.",
  not_found: "We couldn't find what you were looking for.",
  conflict: "That action conflicts with recent changes. Please refresh and try again.",
  throttled: "Too many attempts. Please wait a moment and try again.",
  server: "Something went wrong on our side. Please try again shortly.",
  network: "We couldn't reach MentorBridge. Check your connection and try again.",
};

interface ErrorEnvelope {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: { fields?: unknown } | unknown;
  };
}

function toFieldErrors(value: unknown): Record<string, string[]> {
  if (!value || typeof value !== "object") return {};
  const result: Record<string, string[]> = {};
  for (const [field, messages] of Object.entries(value as Record<string, unknown>)) {
    if (Array.isArray(messages)) {
      result[field] = messages.filter((m): m is string => typeof m === "string");
    } else if (typeof messages === "string") {
      result[field] = [messages];
    }
  }
  return result;
}

/** Build an ApiError from an HTTP status and the (possibly non-JSON) response body. */
export function errorFromResponse(
  status: number,
  body: unknown,
  retryAfterHeader?: string | null,
): ApiError {
  const kind = kindForStatus(status);
  const envelope = (body && typeof body === "object" ? body : {}) as ErrorEnvelope;
  const details = envelope.error?.details;
  const fields =
    details && typeof details === "object" && "fields" in details
      ? toFieldErrors((details as { fields?: unknown }).fields)
      : {};
  const code = typeof envelope.error?.code === "string" ? envelope.error.code : kind;
  const message =
    typeof envelope.error?.message === "string" && envelope.error.message
      ? envelope.error.message
      : DEFAULT_MESSAGES[kind];
  const retryAfter = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : NaN;

  return new ApiError({
    kind,
    status,
    code,
    message,
    fieldErrors: fields,
    retryAfterSeconds: Number.isFinite(retryAfter) ? retryAfter : undefined,
  });
}

export function networkError(): ApiError {
  return new ApiError({
    kind: "network",
    status: 0,
    code: "network_error",
    message: DEFAULT_MESSAGES.network,
  });
}

/** A safe, human-readable message for any thrown value. Never exposes stack traces. */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return DEFAULT_MESSAGES.server;
}
