import type { DisplayStatus, ServiceStatus } from "@/types/status";

const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function apiBaseUrl(): string {
  return typeof window === "undefined"
    ? process.env.INTERNAL_API_URL ?? publicApiUrl
    : publicApiUrl;
}

export async function getServiceStatus(): Promise<DisplayStatus> {
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/health/live`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Status request failed with ${response.status}`);
    }
    return (await response.json()) as ServiceStatus;
  } catch {
    return {
      service: "projectbridge",
      status: "unavailable",
      version: "unknown",
    };
  }
}

export function formatStatusLabel(status: DisplayStatus["status"]): string {
  return status === "ok" ? "Backend connected" : "Backend unavailable";
}

