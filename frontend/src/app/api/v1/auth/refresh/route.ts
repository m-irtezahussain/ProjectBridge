import { type NextRequest, NextResponse } from "next/server";

import type { NavigationResponse } from "@/types/auth";

const internalApiUrl =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

const allowedDestinations = new Set(["/dashboard", "/business/register"]);

export async function GET(request: NextRequest) {
  const requestedNext = request.nextUrl.searchParams.get("next") ?? "/dashboard";
  const safeNext = allowedDestinations.has(requestedNext)
    ? requestedNext
    : "/dashboard";

  try {
    const backendResponse = await fetch(`${internalApiUrl}/api/v1/auth/refresh`, {
      method: "POST",
      cache: "no-store",
      headers: { Cookie: request.headers.get("cookie") ?? "" },
    });
    const body = backendResponse.ok
      ? ((await backendResponse.json()) as NavigationResponse)
      : null;
    const destination = body?.next && allowedDestinations.has(body.next)
      ? body.next
      : backendResponse.ok
        ? safeNext
        : "/login";
    const response = NextResponse.redirect(new URL(destination, request.url));
    for (const cookie of backendResponse.headers.getSetCookie()) {
      response.headers.append("set-cookie", cookie);
    }
    return response;
  } catch {
    return NextResponse.redirect(new URL("/login", request.url));
  }
}
