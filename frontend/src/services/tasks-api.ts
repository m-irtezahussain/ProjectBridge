import type {
  ProjectTask,
  TaskPriority,
  TaskStatus,
} from "@/components/project-workspace/task-data";
import { publicApiBaseUrl } from "./api-base";

export type TaskPayload = Readonly<{
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
}>;

export type TaskUpdatePayload = Partial<TaskPayload>;

type ApiErrorBody = Readonly<{
  detail?: string | Array<{ msg?: string }>;
}>;

export class TasksApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "TasksApiError";
  }
}

function errorMessage(body: ApiErrorBody, status: number): string {
  const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
  if (detail) return detail;
  if (status === 401) return "Your session has expired. Sign in again to continue.";
  if (status === 403) return "Register a business before managing tasks.";
  if (status === 404) return "That task or project could not be found.";
  return "We could not complete the task request. Please try again.";
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
    throw new TasksApiError(
      "The tasks API could not be reached. Check your connection and try again.",
    );
  }

  if (response.status === 401 && allowRefresh && await refreshSession()) {
    return request<T>(path, init, false);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new TasksApiError(errorMessage(body, response.status), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function taskPath(projectId: number, taskId?: number): string {
  const base = `/api/v1/projects/${projectId}/tasks`;
  return taskId === undefined ? base : `${base}/${taskId}`;
}

export function listTasks(projectId: number): Promise<ProjectTask[]> {
  return request<ProjectTask[]>(taskPath(projectId));
}

export function getTask(projectId: number, taskId: number): Promise<ProjectTask> {
  return request<ProjectTask>(taskPath(projectId, taskId));
}

export function createTask(projectId: number, payload: TaskPayload): Promise<ProjectTask> {
  return request<ProjectTask>(taskPath(projectId), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTask(
  projectId: number,
  taskId: number,
  payload: TaskUpdatePayload,
): Promise<ProjectTask> {
  return request<ProjectTask>(taskPath(projectId, taskId), {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTask(projectId: number, taskId: number): Promise<void> {
  return request<void>(taskPath(projectId, taskId), { method: "DELETE" });
}
