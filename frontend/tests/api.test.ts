import { describe, expect, it } from "vitest";

import { formatStatusLabel } from "../src/services/api";

describe("formatStatusLabel", () => {
  it("uses a clear label for a healthy backend", () => {
    expect(formatStatusLabel("ok")).toBe("Backend connected");
  });

  it("uses a clear label when the backend cannot be reached", () => {
    expect(formatStatusLabel("unavailable")).toBe("Backend unavailable");
  });
});

