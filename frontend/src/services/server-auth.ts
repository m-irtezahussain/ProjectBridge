import "server-only";

import { cookies } from "next/headers";

import type { SessionStatus } from "@/types/auth";

const internalApiUrl =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function getSessionStatus(): Promise<SessionStatus> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map(({ name, value }) => `${name}=${value}`)
    .join("; ");
  try {
    const response = await fetch(`${internalApiUrl}/api/v1/auth/session`, {
      cache: "no-store",
      headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
    });
    if (!response.ok) {
      throw new Error("Session request failed");
    }
    return (await response.json()) as SessionStatus;
  } catch {
    return {
      authenticated: false,
      has_business: false,
      full_name: null,
      email: null,
      next: "/login",
    };
  }
}
