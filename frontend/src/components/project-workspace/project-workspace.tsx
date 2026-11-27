"use client";

import type { CSSProperties, DragEvent, FormEvent, KeyboardEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { flushSync } from "react-dom";

import { Icon } from "@/components/ui/icon";
import {
  calendarCells,
  moveTask,
  taskColumns,
  taskPriorityLabel,
  taskStatusClass,
  tasksForStatus,
  type ProjectTask,
  type TaskPriority,
  type TaskStatus,
  type TaskView,
} from "@/components/project-workspace/task-data";
import type { ProjectItem } from "@/components/projects/project-data";
import { getProject } from "@/services/projects-api";
import {
  createTask as createTaskRequest,
  deleteTask as deleteTaskRequest,
  listTasksPage,
  updateTask as updateTaskRequest,
  type TaskPayload,
  type TaskListOptions,
} from "@/services/tasks-api";

const views: readonly Readonly<{ id: TaskView; label: string; icon: "kanban" | "list" | "calendar" }>[] = [
  { id: "kanban", label: "Kanban", icon: "kanban" },
  { id: "list", label: "List", icon: "list" },
  { id: "calendar", label: "Calendar", icon: "calendar" },
];
const priorities: readonly TaskPriority[] = ["low", "medium", "high", "urgent"];
const taskPriorities = new Set<TaskPriority>(priorities);
const TASK_PAGE_SIZE = 50;
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

const TASK_STATUS_DESCRIPTIONS: Record<TaskStatus, string> = {
  todo: "Ready to be picked up",
  "in process": "Actively being worked on",
  "in review": "Awaiting review or testing",
  done: "Completed and verified",
};

const TASK_PRIORITY_DESCRIPTIONS: Record<TaskPriority, string> = {
  low: "Low impact or nice-to-have",
  medium: "Standard timeline and scope",
  high: "Important for milestone",
  urgent: "Critical blocker or deadline",
};

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void) => unknown;
};

function positiveOffset(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function TaskStatusDropdown({
  status,
  onStatusChange,
  variant = "card",
  direction = "down",
  label = "Change status",
}: Readonly<{
  status: TaskStatus;
  onStatusChange: (status: TaskStatus) => void;
  variant?: "card" | "list";
  direction?: "down" | "up";
  label?: string;
}>) {
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(() =>
    taskColumns.findIndex((col) => col.id === status),
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: MouseEvent | TouchEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [isOpen]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = taskColumns.findIndex((col) => col.id === status);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      } else {
        setHighlightedIndex((prev) => (prev + 1) % taskColumns.length);
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = taskColumns.findIndex((col) => col.id === status);
        setHighlightedIndex(idx >= 0 ? idx : taskColumns.length - 1);
      } else {
        setHighlightedIndex((prev) => (prev - 1 + taskColumns.length) % taskColumns.length);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isOpen) {
        if (highlightedIndex >= 0 && highlightedIndex < taskColumns.length) {
          onStatusChange(taskColumns[highlightedIndex].id);
        }
        setIsOpen(false);
      } else {
        setIsOpen(true);
        const idx = taskColumns.findIndex((col) => col.id === status);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      }
    } else if (event.key === "Escape") {
      if (isOpen) {
        event.preventDefault();
        event.stopPropagation();
        setIsOpen(false);
      }
    } else if (event.key === "Tab") {
      if (isOpen) {
        setIsOpen(false);
      }
    }
  }

  function handleSelect(newStatus: TaskStatus) {
    onStatusChange(newStatus);
    setIsOpen(false);
    triggerRef.current?.focus();
  }

  const currentColumn = taskColumns.find((col) => col.id === status) ?? taskColumns[0];
  const isCard = variant === "card";

  return (
    <div
      ref={containerRef}
      className={isCard ? "task-card-status-dropdown" : "task-list-status-cell"}
      draggable={false}
      onDragStart={(e) => e.stopPropagation()}
    >
      <button
        ref={triggerRef}
        type="button"
        className={isCard ? `task-card-status-trigger${isOpen ? " is-open" : ""}` : `task-list-status-trigger${isOpen ? " is-open" : ""}`}
        onClick={() => {
          if (!isOpen) {
            const idx = taskColumns.findIndex((col) => col.id === status);
            setHighlightedIndex(idx >= 0 ? idx : 0);
          }
          setIsOpen((prev) => !prev);
        }}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={label}
      >
        <span className={`task-status-pill task-status-pill--${taskStatusClass(status)}`}>
          <i />
          {currentColumn.label}
        </span>
        <Icon name="chevron" />
      </button>

      {isOpen && (
        <ul
          role="listbox"
          aria-label={label}
          className={`task-status-menu${direction === "up" ? " task-status-menu--up" : ""}`}
        >
          {taskColumns.map((col, idx) => {
            const isSelected = col.id === status;
            const isHighlighted = idx === highlightedIndex;
            return (
              <li
                key={col.id}
                role="option"
                aria-selected={isSelected}
                className={`task-status-menu__option${isSelected ? " is-selected" : ""}${isHighlighted ? " is-highlighted" : ""}`}
                onClick={() => handleSelect(col.id)}
                onMouseEnter={() => setHighlightedIndex(idx)}
              >
                <span className={`task-status-pill task-status-pill--${taskStatusClass(col.id)}`}>
                  <i />
                  {col.label}
                </span>
                {isSelected && <Icon name="check" className="task-status-menu__check" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function TaskPriorityFilter({
  priority,
  onPriorityChange,
}: Readonly<{
  priority: TaskPriority | "All";
  onPriorityChange: (priority: TaskPriority | "All") => void;
}>) {
  const [isOpen, setIsOpen] = useState(false);
  const options = useMemo(() => ["All", ...priorities] as const, []);
  const [highlightedIndex, setHighlightedIndex] = useState(() =>
    options.findIndex((item) => item === priority),
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: MouseEvent | TouchEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [isOpen]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = options.findIndex((opt) => opt === priority);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      } else {
        setHighlightedIndex((prev) => (prev + 1) % options.length);
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = options.findIndex((opt) => opt === priority);
        setHighlightedIndex(idx >= 0 ? idx : options.length - 1);
      } else {
        setHighlightedIndex((prev) => (prev - 1 + options.length) % options.length);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isOpen) {
        if (highlightedIndex >= 0 && highlightedIndex < options.length) {
          onPriorityChange(options[highlightedIndex]);
        }
        setIsOpen(false);
      } else {
        setIsOpen(true);
        const idx = options.findIndex((opt) => opt === priority);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      }
    } else if (event.key === "Escape") {
      if (isOpen) {
        event.preventDefault();
        event.stopPropagation();
        setIsOpen(false);
      }
    } else if (event.key === "Tab") {
      if (isOpen) {
        setIsOpen(false);
      }
    }
  }

  function handleSelect(val: TaskPriority | "All") {
    onPriorityChange(val);
    setIsOpen(false);
    triggerRef.current?.focus();
  }

  return (
    <div ref={containerRef} className={`workspace-priority${isOpen ? " is-open" : ""}`}>
      <span className="workspace-priority__label">Priority</span>
      <button
        ref={triggerRef}
        type="button"
        className={`workspace-priority-trigger${isOpen ? " is-open" : ""}`}
        onClick={() => {
          if (!isOpen) {
            const idx = options.findIndex((opt) => opt === priority);
            setHighlightedIndex(idx >= 0 ? idx : 0);
          }
          setIsOpen((prev) => !prev);
        }}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label="Filter tasks by priority"
      >
        {priority === "All" ? (
          <span className="workspace-priority-value">All</span>
        ) : (
          <em className={`task-priority task-priority--${priority}`}>{taskPriorityLabel(priority)}</em>
        )}
        <Icon name="chevron" className="workspace-priority-chevron" />
      </button>

      {isOpen && (
        <ul role="listbox" aria-label="Filter tasks by priority" className="workspace-priority-menu">
          {options.map((item, idx) => {
            const isSelected = item === priority;
            const isHighlighted = idx === highlightedIndex;
            return (
              <li
                key={item}
                role="option"
                aria-selected={isSelected}
                className={`workspace-priority-menu__option${isSelected ? " is-selected" : ""}${isHighlighted ? " is-highlighted" : ""}`}
                onClick={() => handleSelect(item)}
                onMouseEnter={() => setHighlightedIndex(idx)}
              >
                {item === "All" ? (
                  <span className="workspace-priority-menu__all-label">All priorities</span>
                ) : (
                  <em className={`task-priority task-priority--${item}`}>{taskPriorityLabel(item)}</em>
                )}
                {isSelected && <Icon name="check" className="workspace-priority-menu__check" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function TaskDialogStatusSelect({
  status,
  onChange,
}: Readonly<{
  status: TaskStatus;
  onChange: (status: TaskStatus) => void;
}>) {
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(() =>
    taskColumns.findIndex((col) => col.id === status),
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: MouseEvent | TouchEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [isOpen]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = taskColumns.findIndex((col) => col.id === status);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      } else {
        setHighlightedIndex((prev) => (prev + 1) % taskColumns.length);
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = taskColumns.findIndex((col) => col.id === status);
        setHighlightedIndex(idx >= 0 ? idx : taskColumns.length - 1);
      } else {
        setHighlightedIndex((prev) => (prev - 1 + taskColumns.length) % taskColumns.length);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isOpen) {
        if (highlightedIndex >= 0 && highlightedIndex < taskColumns.length) {
          onChange(taskColumns[highlightedIndex].id);
        }
        setIsOpen(false);
      } else {
        setIsOpen(true);
        const idx = taskColumns.findIndex((col) => col.id === status);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      }
    } else if (event.key === "Escape") {
      if (isOpen) {
        event.preventDefault();
        event.stopPropagation();
        setIsOpen(false);
      }
    } else if (event.key === "Tab") {
      if (isOpen) {
        setIsOpen(false);
      }
    }
  }

  function handleSelect(val: TaskStatus) {
    onChange(val);
    setIsOpen(false);
    triggerRef.current?.focus();
  }

  const currentColumn = taskColumns.find((col) => col.id === status) ?? taskColumns[0];

  return (
    <div className="project-dialog__field">
      <span className="project-dialog__field-label" id="task-status-field-label">Status</span>
      <div className="project-select" ref={containerRef}>
        <button
          ref={triggerRef}
          id="task-dialog-status-trigger"
          type="button"
          className={`project-select-trigger${isOpen ? " is-open" : ""}`}
          onClick={() => {
            if (!isOpen) {
              const idx = taskColumns.findIndex((col) => col.id === status);
              setHighlightedIndex(idx >= 0 ? idx : 0);
            }
            setIsOpen((prev) => !prev);
          }}
          onKeyDown={handleKeyDown}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-labelledby="task-status-field-label task-dialog-status-trigger"
        >
          <span className={`task-status-pill task-status-pill--${taskStatusClass(status)}`}>
            <i />
            {currentColumn.label}
          </span>
          <Icon name="chevron" className={`project-select-chevron${isOpen ? " is-open" : ""}`} />
        </button>
        <input type="hidden" name="status" value={status} />

        {isOpen && (
          <ul
            role="listbox"
            aria-label="Task status"
            className="project-select-menu"
          >
            {taskColumns.map((col, idx) => {
              const isSelected = col.id === status;
              const isHighlighted = idx === highlightedIndex;
              return (
                <li
                  key={col.id}
                  role="option"
                  aria-selected={isSelected}
                  className={`project-select-option${isSelected ? " is-selected" : ""}${isHighlighted ? " is-highlighted" : ""}`}
                  onClick={() => handleSelect(col.id)}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                >
                  <div className="project-select-option__info">
                    <span className={`task-status-pill task-status-pill--${taskStatusClass(col.id)}`}>
                      <i />
                      {col.label}
                    </span>
                    <small className="project-select-option__desc">{TASK_STATUS_DESCRIPTIONS[col.id]}</small>
                  </div>
                  {isSelected && <Icon name="check" className="project-select-option__check" />}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function TaskDialogPrioritySelect({
  priority,
  onChange,
}: Readonly<{
  priority: TaskPriority;
  onChange: (priority: TaskPriority) => void;
}>) {
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(() =>
    priorities.findIndex((item) => item === priority),
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: MouseEvent | TouchEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [isOpen]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = priorities.findIndex((item) => item === priority);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      } else {
        setHighlightedIndex((prev) => (prev + 1) % priorities.length);
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const idx = priorities.findIndex((item) => item === priority);
        setHighlightedIndex(idx >= 0 ? idx : priorities.length - 1);
      } else {
        setHighlightedIndex((prev) => (prev - 1 + priorities.length) % priorities.length);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isOpen) {
        if (highlightedIndex >= 0 && highlightedIndex < priorities.length) {
          onChange(priorities[highlightedIndex]);
        }
        setIsOpen(false);
      } else {
        setIsOpen(true);
        const idx = priorities.findIndex((item) => item === priority);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      }
    } else if (event.key === "Escape") {
      if (isOpen) {
        event.preventDefault();
        event.stopPropagation();
        setIsOpen(false);
      }
    } else if (event.key === "Tab") {
      if (isOpen) {
        setIsOpen(false);
      }
    }
  }

  function handleSelect(val: TaskPriority) {
    onChange(val);
    setIsOpen(false);
    triggerRef.current?.focus();
  }

  return (
    <div className="project-dialog__field">
      <span className="project-dialog__field-label" id="task-priority-field-label">Priority</span>
      <div className="project-select" ref={containerRef}>
        <button
          ref={triggerRef}
          id="task-dialog-priority-trigger"
          type="button"
          className={`project-select-trigger${isOpen ? " is-open" : ""}`}
          onClick={() => {
            if (!isOpen) {
              const idx = priorities.findIndex((item) => item === priority);
              setHighlightedIndex(idx >= 0 ? idx : 0);
            }
            setIsOpen((prev) => !prev);
          }}
          onKeyDown={handleKeyDown}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-labelledby="task-priority-field-label task-dialog-priority-trigger"
        >
          <em className={`task-priority task-priority--${priority}`}>{taskPriorityLabel(priority)}</em>
          <Icon name="chevron" className={`project-select-chevron${isOpen ? " is-open" : ""}`} />
        </button>
        <input type="hidden" name="priority" value={priority} />

        {isOpen && (
          <ul
            role="listbox"
            aria-label="Task priority"
            className="project-select-menu"
          >
            {priorities.map((item, idx) => {
              const isSelected = item === priority;
              const isHighlighted = idx === highlightedIndex;
              return (
                <li
                  key={item}
                  role="option"
                  aria-selected={isSelected}
                  className={`project-select-option${isSelected ? " is-selected" : ""}${isHighlighted ? " is-highlighted" : ""}`}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                >
                  <div className="project-select-option__info">
                    <em className={`task-priority task-priority--${item}`}>{taskPriorityLabel(item)}</em>
                    <small className="project-select-option__desc">{TASK_PRIORITY_DESCRIPTIONS[item]}</small>
                  </div>
                  {isSelected && <Icon name="check" className="project-select-option__check" />}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function TaskCard({
  task,
  index,
  dragging,
  onDragStart,
  onDragEnd,
  onStatusChange,
  onEdit,
  onDelete,
}: Readonly<{
  task: ProjectTask;
  index: number;
  dragging: boolean;
  onDragStart: (event: DragEvent<HTMLElement>, taskId: number) => void;
  onDragEnd: () => void;
  onStatusChange: (taskId: number, status: TaskStatus) => void;
  onEdit: (task: ProjectTask) => void;
  onDelete: (task: ProjectTask) => void;
}>) {
  return (
    <article
      className={`task-card${dragging ? " is-dragging" : ""}`}
      draggable
      onDragStart={(event) => onDragStart(event, task.id)}
      onDragEnd={onDragEnd}
      style={{ "--task-i": index, viewTransitionName: `project-task-${task.id}` } as CSSProperties}
    >
      <div className="task-card__meta">
        <span className={`task-priority task-priority--${task.priority}`}>{taskPriorityLabel(task.priority)}</span>
        <span className="task-card__actions">
          <button type="button" aria-label={`Edit ${task.title}`} onClick={() => onEdit(task)}><Icon name="edit" /></button>
          <button type="button" aria-label={`Delete ${task.title}`} onClick={() => onDelete(task)}><Icon name="trash" /></button>
        </span>
      </div>
      <h3>{task.title}</h3>
      <p>{task.description ?? "No description provided."}</p>
      <div className="task-card__status">
        <span>Move to</span>
        <TaskStatusDropdown
          status={task.status}
          onStatusChange={(newStatus) => onStatusChange(task.id, newStatus)}
          variant="card"
          label={`Move ${task.title}`}
        />
      </div>
      <footer>
        <span className="task-source">Created via {task.created_by.toUpperCase()}</span>
        <small>#{task.id}</small>
      </footer>
    </article>
  );
}

export function ProjectWorkspace({ projectId }: Readonly<{ projectId: number }>) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requestedView = searchParams.get("view");
  const view: TaskView = requestedView === "list" || requestedView === "calendar" ? requestedView : "kanban";
  const query = searchParams.get("q") ?? "";
  const requestedPriority = searchParams.get("priority");
  const priority: TaskPriority | "All" = requestedPriority && taskPriorities.has(requestedPriority as TaskPriority)
    ? requestedPriority as TaskPriority
    : "All";
  const requestedSort = searchParams.get("sort");
  const sortBy = requestedSort === "title" || requestedSort === "status" || requestedSort === "priority"
    ? requestedSort
    : "id";
  const sortOrder = searchParams.get("order") === "asc" ? "asc" : "desc";
  const offset = positiveOffset(searchParams.get("offset"));
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [projectError, setProjectError] = useState("");
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [tasksTotal, setTasksTotal] = useState(0);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksError, setTasksError] = useState("");
  const [reloadVersion, setReloadVersion] = useState(0);
  const [queryInput, setQueryInput] = useState(query);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<TaskStatus | null>(null);
  const [calendarDate, setCalendarDate] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<ProjectTask | null>(null);
  const [taskToDelete, setTaskToDelete] = useState<ProjectTask | null>(null);
  const [dialogStatus, setDialogStatus] = useState<TaskStatus>("todo");
  const [dialogPriority, setDialogPriority] = useState<TaskPriority>("medium");
  const [savingTask, setSavingTask] = useState(false);
  const [taskDialogError, setTaskDialogError] = useState("");
  const [notice, setNotice] = useState("");
  const mutationQueues = useRef(new Map<number, Promise<void>>());
  const noticeTimer = useRef<number | undefined>(undefined);

  const replaceParams = useCallback((changes: Readonly<Record<string, string | null>>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === "") params.delete(key);
      else params.set(key, value);
    }
    const next = params.toString();
    router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  useEffect(() => {
    let active = true;
    async function loadWorkspace() {
      setTasksLoading(true);
      setTasksError("");
      const options: TaskListOptions = {
        limit: TASK_PAGE_SIZE,
        offset,
        priority: priority === "All" ? undefined : priority,
        query: query || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      const [projectResult, tasksResult] = await Promise.allSettled([
        getProject(projectId),
        listTasksPage(projectId, options),
      ]);
      if (!active) return;
      if (projectResult.status === "fulfilled") setProject(projectResult.value);
      else setProjectError(projectResult.reason instanceof Error ? projectResult.reason.message : "Project could not be loaded.");
      if (tasksResult.status === "fulfilled") {
        setTasks([...tasksResult.value.items]);
        setTasksTotal(tasksResult.value.total);
        if (offset > 0 && tasksResult.value.items.length === 0 && tasksResult.value.total > 0) {
          const lastOffset = Math.floor((tasksResult.value.total - 1) / TASK_PAGE_SIZE) * TASK_PAGE_SIZE;
          replaceParams({ offset: String(lastOffset) });
        }
      }
      else setTasksError(tasksResult.reason instanceof Error ? tasksResult.reason.message : "Tasks could not be loaded.");
      setTasksLoading(false);
    }
    void loadWorkspace();
    return () => { active = false; };
  }, [offset, priority, projectId, query, reloadVersion, replaceParams, sortBy, sortOrder]);

  useEffect(() => {
    const timer = window.setTimeout(() => setQueryInput(query), 0);
    return () => window.clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const normalized = queryInput.trim();
      if (normalized !== query) replaceParams({ q: normalized || null, offset: null });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query, queryInput, replaceParams]);

  useEffect(() => () => {
    if (noticeTimer.current !== undefined) window.clearTimeout(noticeTimer.current);
  }, []);

  const visibleTasks = tasks;

  function announce(message: string) {
    setNotice(message);
    if (noticeTimer.current !== undefined) window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(""), 2400);
  }

  function transitionUpdate(update: () => void) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const startViewTransition = (document as ViewTransitionDocument).startViewTransition;
    if (!reduceMotion && startViewTransition) {
      startViewTransition.call(document, () => flushSync(update));
    }
    else update();
  }

  function queueMutation(taskId: number, mutation: () => Promise<void>) {
    const previous = mutationQueues.current.get(taskId) ?? Promise.resolve();
    const next = previous.catch(() => undefined).then(mutation).finally(() => {
      if (mutationQueues.current.get(taskId) === next) {
        mutationQueues.current.delete(taskId);
      }
    });
    mutationQueues.current.set(taskId, next);
  }

  function changeTaskStatus(taskId: number, status: TaskStatus) {
    const task = tasks.find((item) => item.id === taskId);
    if (!task || task.status === status) return;
    const previousStatus = task.status;
    transitionUpdate(() => setTasks((current) => moveTask(current, taskId, status)));
    queueMutation(taskId, async () => {
      try {
        const updated = await updateTaskRequest(projectId, taskId, { status });
        setTasks((current) => current.map((item) => (
          item.id === taskId && item.status === status ? updated : item
        )));
        announce(`${task.title} moved to ${taskColumns.find((column) => column.id === status)?.label}.`);
      } catch (error) {
        transitionUpdate(() => setTasks((current) => current.map((item) => (
          item.id === taskId && item.status === status
            ? { ...item, status: previousStatus }
            : item
        ))));
        announce(error instanceof Error ? error.message : "Task status could not be updated.");
      }
    });
  }

  function handleDragStart(event: DragEvent<HTMLElement>, taskId: number) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(taskId));
    setDraggingId(taskId);
  }

  function handleDrop(event: DragEvent<HTMLElement>, status: TaskStatus) {
    event.preventDefault();
    const transferredId = Number(event.dataTransfer.getData("text/plain"));
    const taskId = Number.isInteger(transferredId) && transferredId > 0 ? transferredId : draggingId;
    if (taskId !== null) changeTaskStatus(taskId, status);
    setDraggingId(null);
    setDragOverStatus(null);
  }

  function openCreateTask() {
    setEditingTask(null);
    setDialogStatus("todo");
    setDialogPriority("medium");
    setTaskDialogError("");
    setTaskDialogOpen(true);
  }

  function openEditTask(task: ProjectTask) {
    setEditingTask(task);
    setDialogStatus(task.status);
    setDialogPriority(task.priority);
    setTaskDialogError("");
    setTaskDialogOpen(true);
  }

  async function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title")).trim();
    const description = String(form.get("description")).trim();
    const payload: TaskPayload = {
      title,
      description: description || null,
      status: dialogStatus,
      priority: dialogPriority,
    };
    setSavingTask(true);
    setTaskDialogError("");
    try {
      const saved = editingTask
        ? await updateTaskRequest(projectId, editingTask.id, payload)
        : await createTaskRequest(projectId, payload);
      transitionUpdate(() => setTasks((current) => editingTask
        ? current.map((task) => task.id === saved.id ? saved : task)
        : [saved, ...current]));
      setReloadVersion((value) => value + 1);
      setTaskDialogOpen(false);
      setEditingTask(null);
      announce(editingTask ? `${title} was updated.` : `${title} was added.`);
    } catch (error) {
      setTaskDialogError(error instanceof Error ? error.message : "Task could not be saved.");
    } finally {
      setSavingTask(false);
    }
  }

  async function confirmDeleteTask() {
    if (!taskToDelete) return;
    const task = taskToDelete;
    const originalIndex = tasks.findIndex((item) => item.id === task.id);
    setTaskToDelete(null);
    transitionUpdate(() => setTasks((current) => current.filter((item) => item.id !== task.id)));
    try {
      await deleteTaskRequest(projectId, task.id);
      setTasksTotal((current) => Math.max(0, current - 1));
      setReloadVersion((value) => value + 1);
      announce(`${task.title} was deleted.`);
    } catch (error) {
      transitionUpdate(() => setTasks((current) => {
        if (current.some((item) => item.id === task.id)) return current;
        const restored = [...current];
        restored.splice(Math.max(0, originalIndex), 0, task);
        return restored;
      }));
      announce(error instanceof Error ? error.message : "Task could not be deleted.");
    }
  }

  const year = calendarDate.getFullYear();
  const month = calendarDate.getMonth();
  const monthLabel = calendarDate.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const today = new Date();

  if (projectError) {
    return <main className="project-workspace"><section className="workspace-failure" role="alert"><Icon name="layers" /><h1>Project unavailable</h1><p>{projectError}</p><Link href="/projects">Return to projects</Link></section></main>;
  }

  return (
    <main className="project-workspace" id="main-content">
      <header className="workspace-heading">
        <div><Link href="/projects">Projects</Link><span>/</span><small>{project ? `#${project.id}` : "Loading…"}</small><h1>{project?.name ?? "Project workspace"}</h1><p>{project?.description ?? "Coordinate every task and handoff from one focused workspace."}</p></div>
        <button
          className="workspace-new-task"
          type="button"
          onClick={openCreateTask}
        >
          <span>+</span> New task
        </button>
      </header>
      <section className="workspace-insights" aria-label="Task summary">
        <article><span>Matching tasks</span><strong>{tasksTotal.toString().padStart(2, "0")}</strong></article>
        <article><span>In process</span><strong>{tasksForStatus(tasks, "in process").length.toString().padStart(2, "0")}</strong></article>
        <article><span>In review</span><strong>{tasksForStatus(tasks, "in review").length.toString().padStart(2, "0")}</strong></article>
        <article><span>Completed</span><strong>{tasksForStatus(tasks, "done").length.toString().padStart(2, "0")}</strong></article>
      </section>
      <section className="workspace-toolbar">
        <div className="workspace-views" role="group" aria-label="Task view">
          {views.map((item) => (
            <button
              className={view === item.id ? "active" : ""}
              type="button"
              aria-pressed={view === item.id}
              onClick={() => replaceParams({ view: item.id === "kanban" ? null : item.id })}
              key={item.id}
            >
              <Icon name={item.icon} />
              {item.label}
            </button>
          ))}
        </div>
        <label className="workspace-search">
          <Icon name="search" />
          <input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="Search tasks…" aria-label="Search tasks" />
        </label>
        <TaskPriorityFilter
          priority={priority}
          onPriorityChange={(value) => replaceParams({ priority: value === "All" ? null : value, offset: null })}
        />
        <label className="discovery-sort discovery-sort--tasks"><span>Sort</span><select aria-label="Sort tasks" value={`${sortBy}:${sortOrder}`} onChange={(event) => { const [sort, order] = event.target.value.split(":"); replaceParams({ sort, order, offset: null }); }}><option value="id:desc">Newest first</option><option value="id:asc">Oldest first</option><option value="title:asc">Title A–Z</option><option value="title:desc">Title Z–A</option><option value="priority:desc">Priority</option><option value="status:asc">Status</option></select></label>
      </section>

      {tasksError && (
        <div className="projects-error" role="alert">
          <Icon name="layers" />
          <div><strong>Tasks could not be loaded</strong><p>{tasksError}</p></div>
          <button type="button" onClick={() => {
            setTasksLoading(true);
            setTasksError("");
            setReloadVersion((value) => value + 1);
          }}>Try again</button>
        </div>
      )}

      <section className="workspace-view" key={view}>
        {view === "kanban" && (
          <div className="kanban-board">
            {taskColumns.map((column) => {
              const columnTasks = tasksForStatus(visibleTasks, column.id);
              return (
                <section
                  className={`kanban-column kanban-column--${column.tone}${dragOverStatus === column.id ? " is-over" : ""}`}
                  key={column.id}
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                    setDragOverStatus((current) => (current === column.id ? current : column.id));
                  }}
                  onDragLeave={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragOverStatus(null);
                  }}
                  onDrop={(event) => handleDrop(event, column.id)}
                >
                  <header>
                    <span>
                      <i />
                      {column.label}
                    </span>
                    <b>{columnTasks.length}</b>
                  </header>
                  <div className="kanban-column__tasks">
                    {columnTasks.map((task, index) => (
                      <TaskCard
                        task={task}
                        index={index}
                        dragging={draggingId === task.id}
                        onDragStart={handleDragStart}
                        onDragEnd={() => {
                          setDraggingId(null);
                          setDragOverStatus(null);
                        }}
                        onStatusChange={changeTaskStatus}
                        onEdit={openEditTask}
                        onDelete={setTaskToDelete}
                        key={task.id}
                      />
                    ))}
                    {columnTasks.length === 0 && <div className="kanban-empty">Drop a task here</div>}
                  </div>
                </section>
              );
            })}
          </div>
        )}

        {view === "list" && (
          <div className="task-list">
            <div className="task-list__head">
              <span>Task</span>
              <span>Priority</span>
              <span>Source</span>
              <span>Status</span>
              <span>Actions</span>
            </div>
            {visibleTasks.map((task, index) => {
              const isNearBottom = index >= visibleTasks.length - 2 && visibleTasks.length > 2;
              return (
                <article style={{ "--task-i": index } as CSSProperties} key={task.id}>
                  <div>
                    <i className={`task-list__dot task-list__dot--${taskStatusClass(task.status)}`} />
                    <span>
                      <strong>{task.title}</strong>
                      <small>{task.description ?? "No description"}</small>
                    </span>
                  </div>
                  <em className={`task-priority task-priority--${task.priority}`}>{taskPriorityLabel(task.priority)}</em>
                  <span className="task-list__source">{task.created_by.toUpperCase()}</span>
                  <div className="task-list-status-cell">
                    <TaskStatusDropdown
                      status={task.status}
                      onStatusChange={(newStatus) => changeTaskStatus(task.id, newStatus)}
                      variant="list"
                      direction={isNearBottom ? "up" : "down"}
                      label={`Status for ${task.title}`}
                    />
                  </div>
                  <span className="task-list__actions">
                    <button type="button" aria-label={`Edit ${task.title}`} onClick={() => openEditTask(task)}><Icon name="edit" /></button>
                    <button type="button" aria-label={`Delete ${task.title}`} onClick={() => setTaskToDelete(task)}><Icon name="trash" /></button>
                  </span>
                </article>
              );
            })}
          </div>
        )}

        {view === "calendar" && (
          <div className="task-calendar">
            <section className="task-calendar__unscheduled">
              <header><span>Unscheduled tasks</span><small>Due dates are not part of the task record yet.</small></header>
              <div>
                {visibleTasks.map((task) => (
                  <button className={`calendar-task calendar-task--${taskStatusClass(task.status)}`} type="button" onClick={() => openEditTask(task)} key={task.id}>
                    <i />{task.title}
                  </button>
                ))}
              </div>
            </section>
            <header>
              <button type="button" aria-label="Previous month" onClick={() => setCalendarDate(new Date(year, month - 1, 1))}>‹</button>
              <h2>{monthLabel}</h2>
              <button type="button" aria-label="Next month" onClick={() => setCalendarDate(new Date(year, month + 1, 1))}>›</button>
            </header>
            <div className="task-calendar__weekdays">
              {weekdays.map((day) => <span key={day}>{day}</span>)}
            </div>
            <div className="task-calendar__grid">
              {calendarCells(year, month).map((day, index) => {
                const isToday = day === today.getDate() && year === today.getFullYear() && month === today.getMonth();
                return (
                  <article className={`${day === null ? "is-empty" : ""}${isToday ? " is-today" : ""}`} key={`${day ?? "empty"}-${index}`}>
                    <span>{day}</span>
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {!tasksLoading && tasks.length > 0 && (
        <nav className="discovery-pagination" aria-label="Task pages">
          <button type="button" disabled={offset === 0} onClick={() => replaceParams({ offset: String(Math.max(0, offset - TASK_PAGE_SIZE)) })}>Previous</button>
          <span>Page {Math.floor(offset / TASK_PAGE_SIZE) + 1} of {Math.max(1, Math.ceil(tasksTotal / TASK_PAGE_SIZE))} · {offset + 1}–{Math.min(offset + tasks.length, tasksTotal)} of {tasksTotal}</span>
          <button type="button" disabled={offset + tasks.length >= tasksTotal} onClick={() => replaceParams({ offset: String(offset + TASK_PAGE_SIZE) })}>Next</button>
        </nav>
      )}

      {!tasksLoading && visibleTasks.length === 0 && (
        <section className="workspace-no-tasks">
          <Icon name="search" />
          <h2>{tasksTotal === 0 && !query && priority === "All" ? "No tasks yet" : "No matching tasks"}</h2>
          <p>{tasksTotal === 0 && !query && priority === "All" ? "Create the first task for this project." : "Clear the search or choose another priority."}</p>
          <button type="button" onClick={tasksTotal === 0 && !query && priority === "All" ? openCreateTask : () => { setQueryInput(""); replaceParams({ q: null, priority: null, offset: null }); }}>{tasksTotal === 0 && !query && priority === "All" ? "Create task" : "Reset filters"}</button>
        </section>
      )}

      {tasksLoading && (
        <section className="workspace-no-tasks" aria-label="Loading tasks">
          <Icon name="layers" /><h2>Loading tasks…</h2><p>Syncing this project with the API.</p>
        </section>
      )}

      {taskDialogOpen && (
        <div className="project-dialog-layer">
          <button className="project-dialog-backdrop" type="button" aria-label="Close task dialog" onClick={() => setTaskDialogOpen(false)} />
          <section className="project-dialog task-dialog" role="dialog" aria-modal="true" aria-labelledby="task-dialog-title">
            <header>
              <span>{editingTask ? "Edit task" : "Create task"}</span>
              <button type="button" aria-label="Close" onClick={() => setTaskDialogOpen(false)}>×</button>
            </header>
            <div className="project-dialog__intro">
              <small>Project task</small>
              <h2 id="task-dialog-title">{editingTask ? "Refine the next move." : "Add the next move."}</h2>
              <p>Changes are stored securely in this project&apos;s tenant-scoped task workspace.</p>
            </div>
            <form onSubmit={submitTask}>
              <label>
                <span>Task name</span>
                <input name="title" defaultValue={editingTask?.title ?? ""} minLength={2} maxLength={200} required autoFocus />
              </label>
              <label>
                <span>Description <small>Optional</small></span>
                <textarea name="description" defaultValue={editingTask?.description ?? ""} maxLength={2000} />
              </label>
              <div className="project-dialog__row">
                <TaskDialogStatusSelect
                  status={dialogStatus}
                  onChange={setDialogStatus}
                />
                <TaskDialogPrioritySelect
                  priority={dialogPriority}
                  onChange={setDialogPriority}
                />
              </div>
              {taskDialogError && <p className="project-dialog__error" role="alert">{taskDialogError}</p>}
              <footer>
                <button className="project-dialog__cancel" type="button" onClick={() => setTaskDialogOpen(false)} disabled={savingTask}>Cancel</button>
                <button className="project-dialog__save" type="submit" disabled={savingTask}>{savingTask ? "Saving…" : editingTask ? "Save changes" : "Add task"} <span>→</span></button>
              </footer>
            </form>
          </section>
        </div>
      )}

      {taskToDelete && (
        <div className="project-dialog-layer">
          <button className="project-dialog-backdrop" type="button" aria-label="Close delete task dialog" onClick={() => setTaskToDelete(null)} />
          <section className="project-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-task-title">
            <div className="project-delete-dialog__icon"><Icon name="trash" /></div>
            <small>Delete task</small>
            <h2 id="delete-task-title">Delete {taskToDelete.title}?</h2>
            <p>The task will be softly deleted and removed from every project view.</p>
            <footer>
              <button type="button" onClick={() => setTaskToDelete(null)}>Cancel</button>
              <button className="danger" type="button" onClick={() => void confirmDeleteTask()}>Delete task</button>
            </footer>
          </section>
        </div>
      )}

      {notice && <div className="projects-toast" role="status"><Icon name="check" />{notice}</div>}
    </main>
  );
}
