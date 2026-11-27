import type { ProjectItem, ProjectStatus } from "@/components/projects/project-data";
import { ApiError, apiRequest, type OffsetPage, type PageOptions, queryString, type SortOrder } from "./api-client";

export type ProjectPayload = Readonly<{
  name: string;
  description: string | null;
  status: ProjectStatus;
}>;

export type ProjectRecord = ProjectItem & Readonly<{ version: number }>;

export { ApiError as ProjectsApiError };

export type ProjectListOptions = PageOptions & Readonly<{
  status?: ProjectStatus;
  query?: string;
  sort_by?: "id" | "name" | "status";
  sort_order?: SortOrder;
}>;

type ProjectPageResponse = Omit<OffsetPage<ProjectRecord>, "items"> & Readonly<{ projects: readonly ProjectRecord[] }>;

export async function listProjects(): Promise<ProjectRecord[]> {
  const page = await listProjectsPage({ limit: 100 });
  return [...page.items];
}

export async function listProjectsPage(options: ProjectListOptions = {}): Promise<OffsetPage<ProjectRecord>> {
  const page = await apiRequest<ProjectPageResponse>(`/api/v1/projects${queryString(options)}`);
  return { ...page, items: page.projects };
}

export function getProject(projectId: number): Promise<ProjectRecord> {
  return apiRequest<ProjectRecord>(`/api/v1/projects/${projectId}`);
}

export function createProject(payload: ProjectPayload): Promise<ProjectRecord> {
  return apiRequest<ProjectRecord>("/api/v1/projects", {
    method: "POST",
    json: payload,
  });
}

export function updateProject(
  projectId: number,
  payload: ProjectPayload,
): Promise<ProjectRecord> {
  return apiRequest<ProjectRecord>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    json: payload,
  });
}

export function deleteProject(projectId: number): Promise<void> {
  return apiRequest<void>(`/api/v1/projects/${projectId}`, { method: "DELETE" });
}

export function updateProjectVersioned(projectId: number, payload: Partial<ProjectPayload>, expectedVersion: number, idempotencyKey: string): Promise<Readonly<{ project: ProjectRecord; replayed: boolean }>> {
  return apiRequest(`/api/v1/projects/${projectId}`, { method: "PATCH", json: { ...payload, expected_version: expectedVersion, idempotency_key: idempotencyKey } });
}

export function archiveProject(projectId: number, expectedVersion: number, idempotencyKey: string): Promise<Readonly<{ project_id: number; archived: boolean; replayed: boolean }>> {
  return apiRequest(`/api/v1/projects/${projectId}`, { method: "DELETE", json: { expected_version: expectedVersion, idempotency_key: idempotencyKey } });
}
