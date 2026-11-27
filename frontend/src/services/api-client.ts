import { publicApiBaseUrl } from "./api-base";

export type ApiErrorCode =
  | "validation_error"
  | "authentication_error"
  | "authorization_error"
  | "not_found"
  | "conflict"
  | "service_unavailable"
  | (string & {});

export type ApiValidationIssue = Readonly<{
  loc?: readonly (string | number)[];
  msg: string;
  type?: string;
}>;

export type StructuredApiError = Readonly<{
  code?: ApiErrorCode;
  message?: string;
  retryable?: boolean;
  current_version?: number;
  issues?: readonly ApiValidationIssue[];
}>;

type ApiErrorBody = Readonly<{
  detail?: string | readonly ApiValidationIssue[] | StructuredApiError;
  error?: StructuredApiError;
}> & StructuredApiError;

export type OffsetPage<T> = Readonly<{
  items: readonly T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}>;

export type PageOptions = Readonly<{ limit?: number; offset?: number }>;
export type SortOrder = "asc" | "desc";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly code?: ApiErrorCode,
    readonly retryable = false,
    readonly issues: readonly ApiValidationIssue[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class VersionConflictError extends ApiError {
  constructor(message: string, status: number, readonly currentVersion?: number) {
    super(message, status, "conflict", false);
    this.name = "VersionConflictError";
  }
}

type ApiRequestInit = Omit<RequestInit, "body"> & Readonly<{
  body?: BodyInit | null;
  json?: unknown;
  timeoutMs?: number;
}>;

function structuredDetail(body: ApiErrorBody): StructuredApiError {
  if (body.error) return body.error;
  if (typeof body.detail === "object" && !Array.isArray(body.detail)) {
    return body.detail as StructuredApiError;
  }
  return body;
}

function fallbackMessage(status: number): string {
  if (status === 401) return "Your session has expired. Sign in again to continue.";
  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 404) return "The requested resource could not be found.";
  if (status === 409) return "This item changed since you loaded it. Refresh and try again.";
  if (status === 422) return "Some submitted values are invalid.";
  return "We could not complete the request. Please try again.";
}

async function refreshSession(): Promise<boolean> {
  try {
    const response = await fetch(`${publicApiBaseUrl()}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      signal: AbortSignal.timeout(10_000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function throwResponseError(response: Response): Promise<never> {
  const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
  const detail = structuredDetail(body);
  const issues = Array.isArray(body.detail) ? body.detail : (detail.issues ?? []);
  const message = detail.message
    ?? (typeof body.detail === "string" ? body.detail : issues[0]?.msg)
    ?? fallbackMessage(response.status);
  const code = detail.code ?? (response.status === 409 ? "conflict" : undefined);
  if (response.status === 409 || code === "conflict") {
    throw new VersionConflictError(message, response.status, detail.current_version);
  }
  throw new ApiError(message, response.status, code, detail.retryable ?? false, issues);
}

async function request<T>(path: string, init: ApiRequestInit, allowRefresh: boolean): Promise<T> {
  const { json, timeoutMs = 10_000, ...requestInit } = init;
  const headers = new Headers(requestInit.headers);
  const body = json === undefined ? requestInit.body : JSON.stringify(json);
  if (json !== undefined) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${publicApiBaseUrl()}${path}`, {
      ...requestInit,
      body,
      credentials: "include",
      headers,
      signal: requestInit.signal ?? AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new ApiError("The API could not be reached. Check your connection and try again.");
  }

  if (response.status === 401 && allowRefresh && await refreshSession()) {
    return request<T>(path, init, false);
  }
  if (!response.ok) await throwResponseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function apiRequest<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  return request<T>(path, init, true);
}

export function queryString(values: Readonly<Record<string, unknown>>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, value instanceof Date ? value.toISOString() : String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}
