import { apiRequest } from "./api-client";

export type KnowledgeSearchResult = Readonly<{
  excerpt: string;
  distance: number;
  source_type: string;
  project_id: number;
  document_id: number | null;
  task_id: number | null;
  chunk_id: number | null;
  source_text_id: number | null;
  ingestion_run_id: number | null;
  untrusted_content: true;
}>;

export type SearchIndexJobStatus = "queued" | "processing" | "retry_scheduled" | "completed" | "failed";

export type SearchIndexJob = Readonly<{
  id: number;
  project_id: number;
  status: SearchIndexJobStatus;
  attempts: number;
  max_attempts: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}>;

export type ProjectIndexState = Readonly<{
  project_id: number;
  status: "ready" | "stale" | SearchIndexJobStatus;
  pending_jobs: number;
  last_indexed_at: string | null;
  last_error: string | null;
}>;

export function searchProjectKnowledge(payload: Readonly<{
  query: string;
  project_id?: number | null;
  document_id?: number | null;
  limit?: number;
}>): Promise<Readonly<{ results: readonly KnowledgeSearchResult[]; untrusted_content_notice: string }>> {
  return apiRequest("/api/v1/search", { method: "POST", json: payload });
}

export function reindexProjectKnowledge(projectId: number): Promise<Readonly<{ job_id: number; project_id: number; queued: boolean }>> {
  return apiRequest(`/api/v1/search/projects/${projectId}/reindex`, { method: "POST" });
}

export function getSearchIndexJob(jobId: number): Promise<SearchIndexJob> {
  return apiRequest(`/api/v1/search/jobs/${jobId}`);
}

export function getProjectIndexState(projectId: number): Promise<ProjectIndexState> {
  return apiRequest(`/api/v1/search/projects/${projectId}/index-state`);
}
