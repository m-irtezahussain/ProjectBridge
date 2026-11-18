const configuredPublicApiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const localHostnames = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);

export function resolvePublicApiUrl(
  configuredUrl: string,
  browserHostname?: string,
): string {
  const url = new URL(configuredUrl);
  if (
    browserHostname !== undefined &&
    localHostnames.has(url.hostname) &&
    localHostnames.has(browserHostname)
  ) {
    url.hostname = browserHostname;
  }
  return url.origin;
}

export function publicApiBaseUrl(): string {
  const browserHostname =
    typeof window === "undefined" ? undefined : window.location.hostname;
  return resolvePublicApiUrl(configuredPublicApiUrl, browserHostname);
}

export function safeOAuthReturnUrl(candidate: string | null): string | null {
  if (candidate === null) return null;
  try {
    const target = new URL(candidate);
    const api = new URL(publicApiBaseUrl());
    const bothLoopback =
      localHostnames.has(target.hostname) && localHostnames.has(api.hostname);
    const matchingOrigin =
      target.origin === api.origin ||
      (bothLoopback && target.protocol === api.protocol && target.port === api.port);
    return matchingOrigin && target.pathname === "/oauth/authorize"
      ? target.href
      : null;
  } catch {
    return null;
  }
}
