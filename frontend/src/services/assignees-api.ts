import { apiRequest } from "./api-client";

export type Assignee = Readonly<{ user_id: number; full_name: string; email: string }>;

export async function listAssignees(): Promise<readonly Assignee[]> {
  const response = await apiRequest<Readonly<{ assignees: readonly Assignee[] }>>("/api/v1/assignees");
  return response.assignees;
}
