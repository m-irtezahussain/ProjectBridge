import { apiRequest, type OffsetPage, type PageOptions, queryString } from "./api-client";

export type DocumentStatus = "pending" | "validating" | "available" | "duplicate" | "failed" | "archived";
export type ActionOrigin = "rest" | "mcp" | "worker";
export type SupportedDocumentMime = "application/pdf" | "image/jpeg" | "image/png";

export type DocumentSummary = Readonly<{
  id: number;
  project_id: number | null;
  created_via: ActionOrigin;
  original_filename: string;
  status: DocumentStatus;
  declared_mime_type: string;
  detected_mime_type: string | null;
  declared_size: number;
  size_bytes: number | null;
  content_sha256: string | null;
  duplicate_of_document_id: number | null;
  failure_code: string | null;
  failure_message: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}>;

export type UploadTarget = Readonly<{
  method: "POST";
  url: string;
  fields: Readonly<Record<string, string>>;
  expires_in: number;
}>;

export type InitiateDocumentUploadPayload = Readonly<{
  filename: string;
  mime_type: SupportedDocumentMime;
  size_bytes: number;
  project_id?: number | null;
}>;

export type InitiateDocumentUploadResult = Readonly<{
  document: DocumentSummary;
  upload: UploadTarget;
}>;

export type DocumentListOptions = PageOptions & Readonly<{
  project_id?: number;
  status?: DocumentStatus;
}>;

type DocumentPageResponse = Omit<OffsetPage<DocumentSummary>, "items"> & Readonly<{
  documents: readonly DocumentSummary[];
}>;

export function initiateDocumentUpload(payload: InitiateDocumentUploadPayload): Promise<InitiateDocumentUploadResult> {
  return apiRequest("/api/v1/documents/uploads", { method: "POST", json: payload });
}

export async function uploadDocumentFile(upload: UploadTarget, file: File): Promise<void> {
  const form = new FormData();
  for (const [key, value] of Object.entries(upload.fields)) form.set(key, value);
  form.set("file", file, file.name);
  const response = await fetch(upload.url, { method: upload.method, body: form });
  if (!response.ok) throw new Error("The file could not be uploaded to secure storage.");
}

export function finalizeDocumentUpload(documentId: number): Promise<Readonly<{
  document: DocumentSummary;
  replayed: boolean;
}>> {
  return apiRequest(`/api/v1/documents/${documentId}/finalize`, { method: "POST" });
}

export async function listDocuments(options: DocumentListOptions = {}): Promise<OffsetPage<DocumentSummary>> {
  const page = await apiRequest<DocumentPageResponse>(`/api/v1/documents${queryString(options)}`);
  return { ...page, items: page.documents };
}

export function getDocument(documentId: number): Promise<DocumentSummary> {
  return apiRequest(`/api/v1/documents/${documentId}`);
}

export function getDocumentDownloadUrl(documentId: number): Promise<Readonly<{
  document_id: number;
  url: string;
  expires_in: number;
}>> {
  return apiRequest(`/api/v1/documents/${documentId}/download-url`);
}

export function archiveDocument(documentId: number, expectedVersion: number, idempotencyKey: string): Promise<Readonly<{
  document_id: number;
  archived: boolean;
  replayed: boolean;
}>> {
  return apiRequest(`/api/v1/documents/${documentId}`, {
    method: "DELETE",
    json: { expected_version: expectedVersion, idempotency_key: idempotencyKey },
  });
}
