import { describe, expect, it } from "vitest";

import {
  indexStatusLabel,
  paginateResults,
  resultRelevance,
  resultSourceHref,
  resultSourceLabel,
  shouldPollIndex,
} from "../src/components/knowledge/knowledge-data";
import type { KnowledgeSearchResult } from "../src/services/search-api";

const result = (id: number): KnowledgeSearchResult => ({
  excerpt: `Untrusted excerpt ${id}`,
  distance: .2,
  source_type: "document",
  project_id: 3,
  document_id: id,
  task_id: null,
  chunk_id: id * 10,
  source_text_id: 4,
  ingestion_run_id: 5,
  untrusted_content: true,
});

describe("knowledge search view data", () => {
  it("converts vector distance into bounded relevance", () => {
    expect(resultRelevance(.2)).toBe(80);
    expect(resultRelevance(-1)).toBe(100);
    expect(resultRelevance(2)).toBe(0);
  });

  it("links results to traceable source pages", () => {
    expect(resultSourceLabel(result(8))).toBe("Document #8");
    expect(resultSourceHref(result(8))).toBe("/documents/8");
    expect(resultSourceHref({ ...result(8), document_id: null, task_id: 12 })).toBe("/projects/3");
  });

  it("paginates the bounded semantic result set", () => {
    const results = Array.from({ length: 14 }, (_, index) => result(index + 1));
    expect(paginateResults(results, 2).map((item) => item.document_id)).toEqual([7, 8, 9, 10, 11, 12]);
    expect(paginateResults(results, 3)).toHaveLength(2);
  });

  it("labels and polls only active indexing jobs", () => {
    expect(indexStatusLabel("retry_scheduled")).toBe("Retry scheduled");
    expect(shouldPollIndex("processing")).toBe(true);
    expect(shouldPollIndex("completed")).toBe(false);
    expect(shouldPollIndex("failed")).toBe(false);
  });
});
