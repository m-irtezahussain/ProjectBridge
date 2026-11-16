import type { ProjectItem, ProjectStatus } from "@/components/projects/project-data";
import { publicApiBaseUrl } from "./api-base";

export type ProjectPayload = Readonly<{
  name: string;
  description: string | null;
  status: ProjectStatus;
}>;

type ApiErrorBody = Readonly<{
  detail?: string | Array<{ msg?: string }>;
}>;

export class ProjectsApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ProjectsApiError";
  }
}

function errorMessage(body: ApiErrorBody, status: number): string {
  const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
  if (detail) return detail;
  if (status === 401) return "Your session has expired. Sign in again to continue.";
  if (status === 403) return "Register a business before managing projects.";
  if (status === 404) return "That project could not be found.";
  return "We could not complete the project request. Please try again.";
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

async function request<T>(
  path: string,
  init: RequestInit = {},
  allowRefresh = true,
): Promise<T> {
  let response: Response;
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  try {
    response = await fetch(`${publicApiBaseUrl()}${path}`, {
      ...init,
      credentials: "include",
      headers,
      signal: init.signal ?? AbortSignal.timeout(10_000),
    });
  } catch {
    throw new ProjectsApiError(
      "The projects API could not be reached. Check your connection and try again.",
    );
  }

  if (response.status === 401 && allowRefresh && await refreshSession()) {
    return request<T>(path, init, false);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new ProjectsApiError(errorMessage(body, response.status), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function listProjects(): Promise<ProjectItem[]> {
  return request<ProjectItem[]>("/api/v1/projects");
}

export function getProject(projectId: number): Promise<ProjectItem> {
  return request<ProjectItem>(`/api/v1/projects/${projectId}`);
}

export function createProject(payload: ProjectPayload): Promise<ProjectItem> {
  return request<ProjectItem>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProject(
  projectId: number,
  payload: ProjectPayload,
): Promise<ProjectItem> {
  return request<ProjectItem>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteProject(projectId: number): Promise<void> {
  return request<void>(`/api/v1/projects/${projectId}`, { method: "DELETE" });
}
