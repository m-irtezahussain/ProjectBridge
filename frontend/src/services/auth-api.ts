import type { NavigationResponse } from "@/types/auth";

const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ApiErrorBody = Readonly<{ detail?: string | Array<{ msg?: string }> }>;

async function request(
  path: string,
  payload?: Record<string, string>,
  allowRefresh = true,
): Promise<NavigationResponse> {
  const response = await fetch(`${publicApiUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (response.status === 401 && allowRefresh) {
    const refreshResponse = await fetch(`${publicApiUrl}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refreshResponse.ok) {
      return request(path, payload, false);
    }
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const detail = Array.isArray(body.detail)
      ? body.detail[0]?.msg
      : body.detail;
    throw new Error(detail ?? "We could not complete that request. Please try again.");
  }
  return (await response.json()) as NavigationResponse;
}

export function signup(input: {
  full_name: string;
  email: string;
  password: string;
}): Promise<NavigationResponse> {
  return request("/api/v1/auth/signup", input, false);
}

export function login(input: {
  email: string;
  password: string;
}): Promise<NavigationResponse> {
  return request("/api/v1/auth/login", input, false);
}

export function registerBusiness(name: string): Promise<NavigationResponse> {
  return request("/api/v1/businesses/register", { name });
}

export function logout(): Promise<NavigationResponse> {
  return request("/api/v1/auth/logout");
}
