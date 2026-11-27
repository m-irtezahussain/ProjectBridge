import { ApiError, apiRequest } from "./api-client";
import type { ActionOrigin } from "./documents-api";

export type IngestionStatus = "queued" | "processing" | "awaiting_confirmation" | "retry_scheduled" | "completed" | "partial_failure" | "failed";
export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type CandidateStatus = "pending" | "approved" | "rejected" | "created" | "failed";

export type IngestionRun = Readonly<{
  id: number;
  document_id: number;
  project_id: number;
  requested_by_user_id: number;
  initiated_via: ActionOrigin;
  status: IngestionStatus;
  ocr_status: StageStatus;
  extraction_status: StageStatus;
  task_status: StageStatus;
  indexing_status: StageStatus;
  attempts: number;
  max_attempts: number;
  last_error_stage: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  next_attempt_at: string;
  completed_at: string | null;
  version: number;
}>;

export type TaskCandidate = Readonly<{
  id: number;
  title: string;
  description: string | null;
  source_excerpt: string;
  source_text_id: number;
  page_number: number | null;
  source_line_start: number | null;
  source_line_end: number | null;
  extractor: string;
  extractor_version: string;
  extracted_via: ActionOrigin;
  confidence: number | null;
  status: CandidateStatus;
  created_task_id: number | null;
  failure_message: string | null;
}>;

export function startDocumentIngestion(payload: Readonly<{ document_id: number; project_id: number; idempotency_key: string }>): Promise<IngestionRun> {
  return apiRequest("/api/v1/ingestions", { method: "POST", json: payload });
}

export function getDocumentIngestion(ingestionRunId: number): Promise<IngestionRun> {
  return apiRequest(`/api/v1/ingestions/${ingestionRunId}`);
}

export async function getDocumentIngestionForDocument(documentId: number): Promise<IngestionRun | null> {
  try {
    return await apiRequest(`/api/v1/documents/${documentId}/ingestion`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function listTaskCandidates(ingestionRunId: number): Promise<Readonly<{ ingestion: IngestionRun; candidates: readonly TaskCandidate[] }>> {
  return apiRequest(`/api/v1/ingestions/${ingestionRunId}/candidates`);
}

export function confirmTaskCandidates(ingestionRunId: number, payload: Readonly<{
  approved_candidate_ids: readonly number[];
  rejected_candidate_ids: readonly number[];
  expected_version: number;
  idempotency_key: string;
}>): Promise<IngestionRun> {
  return apiRequest(`/api/v1/ingestions/${ingestionRunId}/candidates/confirm`, { method: "POST", json: payload });
}

export function retryDocumentIngestion(ingestionRunId: number, expectedVersion: number, idempotencyKey: string): Promise<IngestionRun> {
  return apiRequest(`/api/v1/ingestions/${ingestionRunId}/retry`, { method: "POST", json: { expected_version: expectedVersion, idempotency_key: idempotencyKey } });
}
