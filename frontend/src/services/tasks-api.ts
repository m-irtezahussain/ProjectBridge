import type {
  ProjectTask,
  TaskPriority,
  TaskStatus,
} from "@/components/project-workspace/task-data";
import { ApiError, apiRequest, type OffsetPage, type PageOptions, queryString, type SortOrder } from "./api-client";

export type TaskPayload = Readonly<{
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_id?: number | null;
}>;

export type TaskUpdatePayload = Partial<TaskPayload>;

export type TaskRecord = ProjectTask & Readonly<{
  assignee_id: number | null;
  source_document_id: number | null;
  source_candidate_id: number | null;
  version: number;
}>;

export { ApiError as TasksApiError };

export type TaskListOptions = PageOptions & Readonly<{
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: number;
  query?: string;
  sort_by?: "id" | "title" | "status" | "priority";
  sort_order?: SortOrder;
}>;

type TaskPageResponse = Omit<OffsetPage<TaskRecord>, "items"> & Readonly<{ tasks: readonly TaskRecord[] }>;

function taskPath(projectId: number, taskId?: number): string {
  const base = `/api/v1/projects/${projectId}/tasks`;
  return taskId === undefined ? base : `${base}/${taskId}`;
}

export async function listTasks(projectId: number): Promise<TaskRecord[]> {
  const page = await listTasksPage(projectId, { limit: 100 });
  return [...page.items];
}

export async function listTasksPage(projectId: number, options: TaskListOptions = {}): Promise<OffsetPage<TaskRecord>> {
  const page = await apiRequest<TaskPageResponse>(`${taskPath(projectId)}${queryString(options)}`);
  return { ...page, items: page.tasks };
}

export function getTask(projectId: number, taskId: number): Promise<TaskRecord> {
  return apiRequest<TaskRecord>(taskPath(projectId, taskId));
}

export function createTask(projectId: number, payload: TaskPayload): Promise<TaskRecord> {
  return apiRequest<TaskRecord>(taskPath(projectId), {
    method: "POST",
    json: payload,
  });
}

export function updateTask(
  projectId: number,
  taskId: number,
  payload: TaskUpdatePayload,
): Promise<TaskRecord> {
  return apiRequest<TaskRecord>(taskPath(projectId, taskId), {
    method: "PATCH",
    json: payload,
  });
}

export function deleteTask(projectId: number, taskId: number): Promise<void> {
  return apiRequest<void>(taskPath(projectId, taskId), { method: "DELETE" });
}

export function updateTaskVersioned(projectId: number, taskId: number, payload: TaskUpdatePayload, expectedVersion: number, idempotencyKey: string): Promise<Readonly<{ task: TaskRecord; replayed: boolean }>> {
  return apiRequest(taskPath(projectId, taskId), { method: "PATCH", json: { ...payload, expected_version: expectedVersion, idempotency_key: idempotencyKey } });
}

export function assignTask(projectId: number, taskId: number, assigneeId: number | null, expectedVersion: number, idempotencyKey: string): Promise<Readonly<{ task: TaskRecord; replayed: boolean }>> {
  return apiRequest(`${taskPath(projectId, taskId)}/assignee`, { method: "PUT", json: { assignee_id: assigneeId, expected_version: expectedVersion, idempotency_key: idempotencyKey } });
}

export function archiveTask(projectId: number, taskId: number, expectedVersion: number, idempotencyKey: string): Promise<Readonly<{ task_id: number; archived: boolean; replayed: boolean }>> {
  return apiRequest(taskPath(projectId, taskId), { method: "DELETE", json: { expected_version: expectedVersion, idempotency_key: idempotencyKey } });
}
