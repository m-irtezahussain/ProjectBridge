import { describe, expect, it } from "vitest";

import {
  filterProjects,
  initialProjects,
} from "../src/components/projects/project-data";

describe("projects demo data", () => {
  it("keeps project progress values within a valid percentage", () => {
    expect(initialProjects.every(({ progress }) => progress >= 0 && progress <= 100)).toBe(true);
  });

  it("filters projects by status", () => {
    expect(filterProjects(initialProjects, "", "At risk")).toEqual(
      initialProjects.filter(({ status }) => status === "At risk"),
    );
  });

  it("searches project names and descriptions without case sensitivity", () => {
    expect(filterProjects(initialProjects, "SEARCHABLE RESEARCH", "All").map(({ id }) => id)).toEqual([
      "atlas-research",
    ]);
  });
});
