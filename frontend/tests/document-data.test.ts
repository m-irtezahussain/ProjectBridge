import { describe, expect, it } from "vitest";

import {
  documentStatusLabel,
  documentStatusProgress,
  filterDocuments,
  formatBytes,
  validateDocumentFile,
} from "../src/components/documents/document-data";
import type { DocumentSummary } from "../src/services/documents-api";

const base: DocumentSummary = {
  id: 1,
  project_id: 7,
  created_via: "rest",
  original_filename: "release-plan.pdf",
  status: "available",
  declared_mime_type: "application/pdf",
  detected_mime_type: "application/pdf",
  declared_size: 2048,
  size_bytes: 2048,
  content_sha256: "abc123",
  duplicate_of_document_id: null,
  failure_code: null,
  failure_message: null,
  created_at: "2026-11-27T10:00:00Z",
  updated_at: "2026-11-27T10:00:00Z",
  version: 1,
};

describe("document view data", () => {
  it("formats status, progress, and sizes", () => {
    expect(documentStatusLabel("duplicate")).toBe("Duplicate");
    expect(documentStatusProgress("validating")).toBe(68);
    expect(formatBytes(2 * 1024 * 1024)).toBe("2.0 MB");
  });

  it("filters by filename, status, and project", () => {
    const failed = { ...base, id: 2, project_id: 8, status: "failed" as const, original_filename: "scan.png", content_sha256: "def456" };
    expect(filterDocuments([base, failed], "release", "available", 7)).toEqual([base]);
    expect(filterDocuments([base, failed], "abc123", "all", "all")).toEqual([base]);
  });

  it("rejects empty, oversized, and unsupported files before upload", () => {
    expect(validateDocumentFile(new File([], "empty.pdf", { type: "application/pdf" }))).toContain("empty");
    expect(validateDocumentFile(new File([new Uint8Array(25 * 1024 * 1024 + 1)], "large.pdf", { type: "application/pdf" }))).toContain("25 MB");
    expect(validateDocumentFile(new File(["hello"], "notes.txt", { type: "text/plain" }))).toContain("PDF");
    expect(validateDocumentFile(new File(["hello"], "scan.png", { type: "image/png" }))).toBeNull();
  });
});
