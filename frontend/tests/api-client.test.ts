import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest, ApiError, queryString, VersionConflictError } from "../src/services/api-client";

afterEach(() => vi.unstubAllGlobals());

describe("shared API client", () => {
  it("preserves structured validation issues", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      detail: [{ loc: ["body", "title"], msg: "Title is required", type: "missing" }],
    }, { status: 422 })));

    const error = await apiRequest("/api/v1/example").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, message: "Title is required" });
    expect((error as ApiError).issues).toHaveLength(1);
  });

  it("exposes version conflicts and the current server version", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      error: { code: "conflict", message: "Task has changed", retryable: false, current_version: 7 },
    }, { status: 409 })));

    const error = await apiRequest("/api/v1/example").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(VersionConflictError);
    expect(error).toMatchObject({ status: 409, currentVersion: 7 });
  });

  it("serializes only defined query values and dates", () => {
    expect(queryString({
      limit: 25,
      query: "release plan",
      status: undefined,
      occurred_from: new Date("2026-11-27T10:00:00.000Z"),
    })).toBe("?limit=25&query=release+plan&occurred_from=2026-11-27T10%3A00%3A00.000Z");
  });
});
