export type TaskStatus = "todo" | "in process" | "in review" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";
export type TaskSource = "api" | "rest" | "mcp" | "worker";
export type TaskView = "kanban" | "list" | "calendar";

export type ProjectTask = Readonly<{
  id: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  project_id: number;
  is_deleted: boolean;
  created_by: TaskSource;
}>;

export const taskColumns: readonly Readonly<{
  id: TaskStatus;
  label: string;
  tone: "muted" | "blue" | "violet" | "lime";
}>[] = [
  { id: "todo", label: "To do", tone: "muted" },
  { id: "in process", label: "In process", tone: "blue" },
  { id: "in review", label: "In review", tone: "violet" },
  { id: "done", label: "Done", tone: "lime" },
];

export function taskStatusClass(status: TaskStatus): string {
  if (status === "in process") return "in-progress";
  if (status === "in review") return "review";
  return status;
}

export function taskPriorityLabel(priority: TaskPriority): string {
  return priority[0].toUpperCase() + priority.slice(1);
}

export function tasksForStatus(
  tasks: readonly ProjectTask[],
  status: TaskStatus,
): ProjectTask[] {
  return tasks.filter((task) => task.status === status);
}

export function moveTask(
  tasks: readonly ProjectTask[],
  taskId: number,
  status: TaskStatus,
): ProjectTask[] {
  return tasks.map((task) => task.id === taskId ? { ...task, status } : task);
}

export function calendarCells(year: number, month: number): Array<number | null> {
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: Array<number | null> = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}
