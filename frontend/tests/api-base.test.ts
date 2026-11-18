import { describe, expect, it } from "vitest";

import {
  resolvePublicApiUrl,
  safeOAuthReturnUrl,
} from "../src/services/api-base";

describe("public API URL resolution", () => {
  it("aligns localhost API requests with a 127.0.0.1 frontend", () => {
    expect(resolvePublicApiUrl("http://localhost:8000", "127.0.0.1")).toBe(
      "http://127.0.0.1:8000",
    );
  });

  it("aligns 127.0.0.1 API requests with a localhost frontend", () => {
    expect(resolvePublicApiUrl("http://127.0.0.1:8000", "localhost")).toBe(
      "http://localhost:8000",
    );
  });

  it("does not rewrite a configured non-local API hostname", () => {
    expect(resolvePublicApiUrl("https://api.projectbridge.test", "localhost")).toBe(
      "https://api.projectbridge.test",
    );
  });

  it("keeps API cookies aligned when the frontend uses 0.0.0.0", () => {
    expect(resolvePublicApiUrl("http://localhost:8000", "0.0.0.0")).toBe(
      "http://0.0.0.0:8000",
    );
  });
});

describe("OAuth return URL validation", () => {
  it("accepts only the OAuth authorization endpoint on the configured API", () => {
    expect(
      safeOAuthReturnUrl(
        "http://localhost:8000/oauth/authorize?client_id=test&state=state",
      ),
    ).toContain("http://localhost:8000/oauth/authorize?");
    expect(safeOAuthReturnUrl("https://attacker.example/oauth/authorize")).toBeNull();
    expect(safeOAuthReturnUrl("http://localhost:8000/api/v1/projects")).toBeNull();
  });
});
