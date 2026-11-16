"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { Icon } from "@/components/ui/icon";
import type { ProjectItem, ProjectStatus } from "@/components/projects/project-data";

export type ProjectInput = Readonly<{
  name: string;
  description: string | null;
  status: ProjectStatus;
}>;

type ProjectModalProps = Readonly<{
  project?: ProjectItem;
  onClose: () => void;
  onSave: (input: ProjectInput) => Promise<void>;
  error?: string;
  saving: boolean;
}>;

const STATUS_OPTIONS: readonly { value: ProjectStatus; description: string }[] = [
  { value: "Planning", description: "Scope, timeline, and discovery" },
  { value: "Active", description: "Work is currently moving" },
  { value: "At risk", description: "Blockers or deadline at risk" },
  { value: "Completed", description: "Work is done and delivered" },
];

export function ProjectModal({ project, onClose, onSave, error, saving }: ProjectModalProps) {
  const [status, setStatus] = useState<ProjectStatus>(project?.status ?? "Planning");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(() =>
    STATUS_OPTIONS.findIndex((opt) => opt.value === (project?.status ?? "Planning")),
  );
  const selectRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: MouseEvent | TouchEvent) {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
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
    if (saving) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const currentIndex = STATUS_OPTIONS.findIndex((opt) => opt.value === status);
        setHighlightedIndex(currentIndex >= 0 ? currentIndex : 0);
      } else {
        setHighlightedIndex((prev) => (prev + 1) % STATUS_OPTIONS.length);
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        const currentIndex = STATUS_OPTIONS.findIndex((opt) => opt.value === status);
        setHighlightedIndex(currentIndex >= 0 ? currentIndex : STATUS_OPTIONS.length - 1);
      } else {
        setHighlightedIndex((prev) => (prev - 1 + STATUS_OPTIONS.length) % STATUS_OPTIONS.length);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isOpen) {
        if (highlightedIndex >= 0 && highlightedIndex < STATUS_OPTIONS.length) {
          setStatus(STATUS_OPTIONS[highlightedIndex].value);
        }
        setIsOpen(false);
      } else {
        setIsOpen(true);
        const currentIndex = STATUS_OPTIONS.findIndex((opt) => opt.value === status);
        setHighlightedIndex(currentIndex >= 0 ? currentIndex : 0);
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

  function handleSelectOption(newStatus: ProjectStatus) {
    setStatus(newStatus);
    setIsOpen(false);
    triggerRef.current?.focus();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const description = String(form.get("description")).trim();
    await onSave({
      name: String(form.get("name")),
      description: description || null,
      status: (String(form.get("status")) as ProjectStatus) || status,
    });
  }

  const currentStatusClass = status.toLowerCase().replace(" ", "-");

  return (
    <div className="project-dialog-layer">
      <button className="project-dialog-backdrop" type="button" aria-label="Close project dialog" onClick={onClose} />
      <section className="project-dialog" role="dialog" aria-modal="true" aria-labelledby="project-dialog-title">
        <header><span>{project ? "Edit workspace project" : "Create project"}</span><button type="button" aria-label="Close" onClick={onClose}>×</button></header>
        <div className="project-dialog__intro"><small>Project details</small><h2 id="project-dialog-title">{project ? `Update ${project.name}` : "Start something meaningful."}</h2><p>Set the project foundation now. Tasks, documents, and team access can be connected afterward.</p></div>
        <form onSubmit={handleSubmit}>
          <label><span>Project name</span><input name="name" defaultValue={project?.name} placeholder="e.g. Customer portal launch" minLength={2} maxLength={120} required autoFocus /></label>
          <label><span>Description <small>Optional</small></span><textarea name="description" defaultValue={project?.description ?? ""} placeholder="What outcome should this project create?" maxLength={2000} /></label>

          <div className="project-dialog__field">
            <span className="project-dialog__field-label" id="project-status-label">Status</span>
            <div className="project-select" ref={selectRef}>
              <button
                ref={triggerRef}
                id="project-status-trigger"
                type="button"
                className={`project-select-trigger${isOpen ? " is-open" : ""}`}
                onClick={() => {
                  if (!isOpen) {
                    const currentIndex = STATUS_OPTIONS.findIndex((opt) => opt.value === status);
                    setHighlightedIndex(currentIndex >= 0 ? currentIndex : 0);
                  }
                  setIsOpen((prev) => !prev);
                }}
                onKeyDown={handleKeyDown}
                disabled={saving}
                aria-haspopup="listbox"
                aria-expanded={isOpen}
                aria-labelledby="project-status-label project-status-trigger"
              >
                <span className={`projects-status projects-status--${currentStatusClass}`}>
                  <i />
                  {status}
                </span>
                <Icon name="chevron" className={`project-select-chevron${isOpen ? " is-open" : ""}`} />
              </button>
              <input type="hidden" name="status" value={status} />

              {isOpen && (
                <ul
                  id="project-status-list"
                  role="listbox"
                  aria-label="Project status"
                  className="project-select-menu"
                >
                  {STATUS_OPTIONS.map((option, index) => {
                    const isSelected = option.value === status;
                    const isHighlighted = index === highlightedIndex;
                    const optionClass = option.value.toLowerCase().replace(" ", "-");
                    return (
                      <li
                        key={option.value}
                        id={`project-status-option-${optionClass}`}
                        role="option"
                        aria-selected={isSelected}
                        className={`project-select-option${isSelected ? " is-selected" : ""}${isHighlighted ? " is-highlighted" : ""}`}
                        onClick={() => handleSelectOption(option.value)}
                        onMouseEnter={() => setHighlightedIndex(index)}
                      >
                        <div className="project-select-option__info">
                          <span className={`projects-status projects-status--${optionClass}`}>
                            <i />
                            {option.value}
                          </span>
                          <small className="project-select-option__desc">{option.description}</small>
                        </div>
                        {isSelected && <Icon name="check" className="project-select-option__check" />}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>

          {error && <p className="project-dialog__error" role="alert">{error}</p>}
          <footer><button className="project-dialog__cancel" type="button" onClick={onClose} disabled={saving}>Cancel</button><button className="project-dialog__save" type="submit" disabled={saving}>{saving ? "Saving…" : project ? "Save changes" : "Create project"}<span>→</span></button></footer>
        </form>
      </section>
    </div>
  );
}
