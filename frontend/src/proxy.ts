import { type NextRequest, NextResponse } from "next/server";

import type { SessionStatus } from "@/types/auth";

const internalApiUrl =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function proxy(request: NextRequest) {
  let session: SessionStatus | null = null;
  try {
    const response = await fetch(`${internalApiUrl}/api/v1/auth/session`, {
      cache: "no-store",
      headers: { Cookie: request.headers.get("cookie") ?? "" },
    });
    if (response.ok) {
      session = (await response.json()) as SessionStatus;
    }
  } catch {
    session = null;
  }

  const isBusinessRegistration = request.nextUrl.pathname === "/business/register";
  if (!session?.authenticated) {
    const refreshUrl = new URL("/api/v1/auth/refresh", request.url);
    refreshUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(refreshUrl);
  }
  if (isBusinessRegistration && session.has_business) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  if (!isBusinessRegistration && !session.has_business) {
    return NextResponse.redirect(new URL("/business/register", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/business/register", "/dashboard/:path*", "/projects/:path*"],
};
