import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createTask,
  deleteTask,
  getTask,
  listTasks,
  updateTask,
} from "../src/services/tasks-api";

const task = {
  id: 5,
  title: "Prepare release",
  description: null,
  status: "todo" as const,
  priority: "high" as const,
  project_id: 3,
  is_deleted: false,
  created_by: "api" as const,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("tasks API service", () => {
  it("uses all nested task CRUD endpoints with cookies", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json([task]))
      .mockResolvedValueOnce(Response.json(task))
      .mockResolvedValueOnce(Response.json(task, { status: 201 }))
      .mockResolvedValueOnce(Response.json({ ...task, status: "in review" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listTasks(3)).resolves.toEqual([task]);
    await expect(getTask(3, 5)).resolves.toEqual(task);
    await expect(createTask(3, {
      title: task.title,
      description: task.description,
      status: task.status,
      priority: task.priority,
    })).resolves.toEqual(task);
    await expect(updateTask(3, 5, { status: "in review" })).resolves.toMatchObject({ status: "in review" });
    await expect(deleteTask(3, 5)).resolves.toBeUndefined();

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "http://localhost:8000/api/v1/projects/3/tasks",
      "http://localhost:8000/api/v1/projects/3/tasks/5",
      "http://localhost:8000/api/v1/projects/3/tasks",
      "http://localhost:8000/api/v1/projects/3/tasks/5",
      "http://localhost:8000/api/v1/projects/3/tasks/5",
    ]);
    expect(fetchMock.mock.calls.every(([, init]) => init.credentials === "include")).toBe(true);
    expect(fetchMock.mock.calls.map(([, init]) => init.method ?? "GET")).toEqual([
      "GET", "GET", "POST", "PATCH", "DELETE",
    ]);
  });

  it("surfaces backend task validation errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(
      { detail: [{ msg: "Invalid task status" }] },
      { status: 422 },
    )));

    await expect(createTask(3, {
      title: "A",
      description: null,
      status: "todo",
      priority: "medium",
    })).rejects.toThrow("Invalid task status");
  });
});
