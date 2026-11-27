import type { KnowledgeSearchResult, SearchIndexJobStatus } from "@/services/search-api";

export const KNOWLEDGE_PAGE_SIZE = 6;

export function resultRelevance(distance: number): number {
  return Math.round(Math.max(0, Math.min(1, 1 - distance)) * 100);
}

export function resultSourceLabel(result: KnowledgeSearchResult): string {
  if (result.task_id !== null) return `Task #${result.task_id}`;
  if (result.document_id !== null) return `Document #${result.document_id}`;
  return `Project #${result.project_id}`;
}

export function resultSourceHref(result: KnowledgeSearchResult): string {
  if (result.document_id !== null) return `/documents/${result.document_id}`;
  return `/projects/${result.project_id}`;
}

export function paginateResults(
  results: readonly KnowledgeSearchResult[],
  page: number,
  pageSize = KNOWLEDGE_PAGE_SIZE,
): KnowledgeSearchResult[] {
  const safePage = Math.max(1, page);
  return results.slice((safePage - 1) * pageSize, safePage * pageSize);
}

export function indexStatusLabel(status: SearchIndexJobStatus | "ready" | "stale"): string {
  return {
    ready: "Index ready",
    stale: "Update pending",
    queued: "Re-index queued",
    processing: "Re-indexing",
    retry_scheduled: "Retry scheduled",
    completed: "Index ready",
    failed: "Index failed",
  }[status];
}

export function shouldPollIndex(status: SearchIndexJobStatus): boolean {
  return status === "queued" || status === "processing" || status === "retry_scheduled";
}
