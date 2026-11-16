import { describe, expect, it } from "vitest";

import {
  dashboardMetrics,
  projectSummaries,
  taskBreakdown,
} from "../src/data/dashboard";

describe("dashboard demo data", () => {
  it("keeps every project progress value within a valid percentage", () => {
    expect(projectSummaries.every(({ progress }) => progress >= 0 && progress <= 100)).toBe(true);
  });

  it("keeps the task breakdown aligned with the displayed total", () => {
    expect(taskBreakdown.reduce((total, item) => total + item.value, 0)).toBe(42);
  });

  it("provides the four headline workspace metrics", () => {
    expect(dashboardMetrics).toHaveLength(4);
  });
});
