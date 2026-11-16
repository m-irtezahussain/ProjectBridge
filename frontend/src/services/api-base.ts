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
