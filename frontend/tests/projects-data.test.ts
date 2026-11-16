import { describe, expect, it } from "vitest";

import {
  filterProjects,
  type ProjectItem,
} from "../src/components/projects/project-data";

const projects: readonly ProjectItem[] = [
  { id: 1, name: "Atlas Research", description: "Searchable research library", business_id: 7, status: "Active" },
  { id: 2, name: "Security Review", description: null, business_id: 7, status: "At risk" },
];

describe("projects API data filtering", () => {

  it("filters projects by status", () => {
    expect(filterProjects(projects, "", "At risk")).toEqual(
      projects.filter(({ status }) => status === "At risk"),
    );
  });

  it("searches project names and descriptions without case sensitivity", () => {
    expect(filterProjects(projects, "SEARCHABLE RESEARCH", "All").map(({ id }) => id)).toEqual([1]);
  });

  it("handles projects without descriptions", () => {
    expect(filterProjects(projects, "missing", "All")).toEqual([]);
  });
});
