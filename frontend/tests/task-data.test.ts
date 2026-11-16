import { describe, expect, it } from "vitest";

import {
  calendarCells,
  moveTask,
  type ProjectTask,
  tasksForStatus,
} from "../src/components/project-workspace/task-data";

const tasks: readonly ProjectTask[] = [
  {
    id: 1,
    title: "Prepare release",
    description: null,
    status: "todo",
    priority: "high",
    project_id: 3,
    is_deleted: false,
    created_by: "api",
  },
  {
    id: 2,
    title: "Review release",
    description: "Confirm the checklist",
    status: "done",
    priority: "medium",
    project_id: 3,
    is_deleted: false,
    created_by: "mcp",
  },
];

describe("project task state helpers", () => {
  it("moves exactly one task without mutating the original collection", () => {
    const original = tasks;
    const moved = moveTask(original, 1, "done");

    expect(tasksForStatus(moved, "done")).toHaveLength(
      tasksForStatus(original, "done").length + 1,
    );
    expect(original.find(({ id }) => id === 1)?.status).toBe("todo");
    expect(moved.find(({ id }) => id === 1)?.status).toBe("done");
  });

  it("builds complete calendar weeks", () => {
    const cells = calendarCells(2026, 10);

    expect(cells).toHaveLength(35);
    expect(cells[0]).toBe(1);
    expect(cells.filter(Boolean)).toHaveLength(30);
  });
});
