import type { DocumentStatus, DocumentSummary } from "@/services/documents-api";

export const MAX_DOCUMENT_BYTES = 25 * 1024 * 1024;
export const ACCEPTED_DOCUMENT_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
] as const;

export type DocumentFilter = "all" | DocumentStatus;

export function documentStatusLabel(status: DocumentStatus): string {
  return {
    pending: "Waiting for upload",
    validating: "Validating",
    available: "Available",
    duplicate: "Duplicate",
    failed: "Failed",
    archived: "Archived",
  }[status];
}

export function documentStatusProgress(status: DocumentStatus): number {
  return { pending: 22, validating: 68, available: 100, duplicate: 100, failed: 100, archived: 100 }[status];
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDocumentDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function validateDocumentFile(file: File): string | null {
  if (!ACCEPTED_DOCUMENT_TYPES.includes(file.type as typeof ACCEPTED_DOCUMENT_TYPES[number])) {
    return "Choose a PDF, PNG, or JPEG file.";
  }
  if (file.size < 1) return "The selected file is empty.";
  if (file.size > MAX_DOCUMENT_BYTES) return "Files must be 25 MB or smaller.";
  return null;
}

export function filterDocuments(
  documents: readonly DocumentSummary[],
  query: string,
  filter: DocumentFilter,
  projectId: number | "all",
): DocumentSummary[] {
  const normalized = query.trim().toLowerCase();
  return documents.filter((document) => (
    (filter === "all" || document.status === filter)
    && (projectId === "all" || document.project_id === projectId)
    && (normalized === ""
      || document.original_filename.toLowerCase().includes(normalized)
      || document.content_sha256?.toLowerCase().includes(normalized) === true)
  ));
}
