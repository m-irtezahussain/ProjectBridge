import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createProject,
  deleteProject,
  getProject,
  listProjects,
  updateProject,
} from "../src/services/projects-api";

const project = {
  id: 8,
  name: "Client Portal",
  description: "Customer workspace",
  business_id: 3,
  status: "Active" as const,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("projects API service", () => {
  it("uses all project CRUD endpoints with cookies", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json([project]))
      .mockResolvedValueOnce(Response.json(project))
      .mockResolvedValueOnce(Response.json(project, { status: 201 }))
      .mockResolvedValueOnce(Response.json({ ...project, status: "Completed" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listProjects()).resolves.toEqual([project]);
    await expect(getProject(8)).resolves.toEqual(project);
    await expect(createProject({ name: project.name, description: project.description, status: project.status })).resolves.toEqual(project);
    await expect(updateProject(8, { name: project.name, description: null, status: "Completed" })).resolves.toMatchObject({ status: "Completed" });
    await expect(deleteProject(8)).resolves.toBeUndefined();

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "http://localhost:8000/api/v1/projects",
      "http://localhost:8000/api/v1/projects/8",
      "http://localhost:8000/api/v1/projects",
      "http://localhost:8000/api/v1/projects/8",
      "http://localhost:8000/api/v1/projects/8",
    ]);
    expect(fetchMock.mock.calls.every(([, init]) => init.credentials === "include")).toBe(true);
    expect(fetchMock.mock.calls.map(([, init]) => init.method ?? "GET")).toEqual([
      "GET", "GET", "POST", "PATCH", "DELETE",
    ]);
  });

  it("surfaces backend validation errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(
      { detail: [{ msg: "Invalid project status" }] },
      { status: 422 },
    )));

    await expect(createProject({ name: "A", description: null, status: "Planning" }))
      .rejects.toThrow("Invalid project status");
  });
});
