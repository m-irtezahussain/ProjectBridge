import { describe, expect, it } from "vitest";

import {
  candidateDecisionPayload,
  canRetryIngestion,
  ingestionProgress,
  initialCandidateDecisions,
  shouldPollIngestion,
} from "../src/components/documents/ingestion-data";
import type { IngestionRun, TaskCandidate } from "../src/services/ingestion-api";

const run: IngestionRun = {
  id: 3,
  document_id: 2,
  project_id: 1,
  requested_by_user_id: 1,
  initiated_via: "rest",
  status: "processing",
  ocr_status: "completed",
  extraction_status: "running",
  task_status: "pending",
  indexing_status: "pending",
  attempts: 1,
  max_attempts: 5,
  last_error_stage: null,
  last_error_code: null,
  last_error_message: null,
  next_attempt_at: "2026-11-27T10:00:00Z",
  completed_at: null,
  version: 2,
};

const candidate = (id: number, status: TaskCandidate["status"]): TaskCandidate => ({
  id,
  title: `Task ${id}`,
  description: null,
  source_excerpt: "TASK: untrusted source text",
  source_text_id: 4,
  page_number: 1,
  source_line_start: 2,
  source_line_end: 2,
  extractor: "marker",
  extractor_version: "1",
  extracted_via: "worker",
  confidence: .9,
  status,
  created_task_id: status === "created" ? id + 100 : null,
  failure_message: null,
});

describe("ingestion view data", () => {
  it("calculates durable stage progress and polling states", () => {
    expect(ingestionProgress(run)).toBe(38);
    expect(shouldPollIngestion("processing")).toBe(true);
    expect(shouldPollIngestion("awaiting_confirmation")).toBe(false);
  });

  it("allows checkpoint retry only while attempts remain", () => {
    expect(canRetryIngestion({ ...run, status: "partial_failure" })).toBe(true);
    expect(canRetryIngestion({ ...run, status: "failed", attempts: 5 })).toBe(false);
  });

  it("requires one explicit decision per extracted candidate", () => {
    const candidates = [candidate(1, "pending"), candidate(2, "rejected"), candidate(3, "created")];
    const initial = initialCandidateDecisions(candidates);
    expect(initial).toEqual({ 2: "rejected", 3: "approved" });
    expect(candidateDecisionPayload(candidates, initial).complete).toBe(false);
    expect(candidateDecisionPayload(candidates, { ...initial, 1: "approved" })).toEqual({
      approved: [1, 3],
      rejected: [2],
      complete: true,
    });
  });
});
