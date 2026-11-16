import type { NavigationResponse } from "@/types/auth";
import { publicApiBaseUrl } from "./api-base";

type ApiErrorBody = Readonly<{ detail?: string | Array<{ msg?: string }> }>;

async function request(
  path: string,
  payload?: Record<string, string>,
  allowRefresh = true,
): Promise<NavigationResponse> {
  let response: Response;
  try {
    response = await fetch(`${publicApiBaseUrl()}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "The API could not be reached. Check that the backend is running and reload the page.",
    );
  }
  if (response.status === 401 && allowRefresh) {
    let refreshResponse: Response;
    try {
      refreshResponse = await fetch(`${publicApiBaseUrl()}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      throw new Error(
        "The API could not be reached. Check that the backend is running and reload the page.",
      );
    }
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
