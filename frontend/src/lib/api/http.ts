import { errorFromResponse, networkError } from "./errors";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type QueryValue = string | number | boolean | null | undefined | Array<string | number>;

export interface RequestOptions {
  method?: HttpMethod;
  query?: Record<string, QueryValue>;
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * A transport performs one HTTP request against the Django API and resolves with the
 * parsed JSON body (or undefined for 204). It throws ApiError on any failure.
 * Browser and server transports differ only in base URL and credential handling.
 */
export type Transport = <T>(path: string, options?: RequestOptions) => Promise<T>;

export function buildQueryString(query: Record<string, QueryValue> | undefined): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, String(item));
    } else {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

const UNSAFE_METHODS = new Set<HttpMethod>(["POST", "PUT", "PATCH", "DELETE"]);

export function isUnsafeMethod(method: HttpMethod): boolean {
  return UNSAFE_METHODS.has(method);
}

export interface TransportConfig {
  baseUrl: string;
  /** Extra headers per request (cookies on the server, CSRF token in the browser). */
  headers: (method: HttpMethod) => Promise<Record<string, string>> | Record<string, string>;
  /** Called before an unsafe request when no CSRF token is available yet. */
  ensureCsrf?: () => Promise<void>;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

export function createTransport(config: TransportConfig): Transport {
  const fetchImpl = config.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const timeoutMs = config.timeoutMs ?? 15_000;

  return async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? "GET";
    if (isUnsafeMethod(method) && config.ensureCsrf) {
      await config.ensureCsrf();
    }

    const headers: Record<string, string> = {
      Accept: "application/json",
      ...(await config.headers(method)),
    };
    let body: BodyInit | undefined;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }

    const timeout = AbortSignal.timeout(timeoutMs);
    const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;

    let response: Response;
    try {
      response = await fetchImpl(`${config.baseUrl}${path}${buildQueryString(options.query)}`, {
        method,
        headers,
        body,
        signal,
        credentials: "same-origin",
        cache: "no-store",
      });
    } catch (error) {
      // Caller-initiated aborts propagate unchanged so effects can ignore them.
      if (options.signal?.aborted) throw error;
      throw networkError();
    }

    const parsed = await parseBody(response);
    if (!response.ok) {
      throw errorFromResponse(response.status, parsed, response.headers.get("Retry-After"));
    }
    return parsed as T;
  };
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) {
    // Non-JSON (e.g. an HTML error page from a proxy). Don't surface it to users.
    return undefined;
  }
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}
