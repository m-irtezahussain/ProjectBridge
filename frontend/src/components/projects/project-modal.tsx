"use client";

import type { FormEvent } from "react";

import type { ProjectItem, ProjectStatus } from "@/components/projects/project-data";

export type ProjectInput = Readonly<{
  name: string;
  description: string;
  status: ProjectStatus;
  dueDate: string;
}>;

type ProjectModalProps = Readonly<{
  project?: ProjectItem;
  onClose: () => void;
  onSave: (input: ProjectInput) => void;
}>;

export function ProjectModal({ project, onClose, onSave }: ProjectModalProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSave({
      name: String(form.get("name")),
      description: String(form.get("description")),
      status: String(form.get("status")) as ProjectStatus,
      dueDate: String(form.get("dueDate")),
    });
  }

  return (
    <div className="project-dialog-layer">
      <button className="project-dialog-backdrop" type="button" aria-label="Close project dialog" onClick={onClose} />
      <section className="project-dialog" role="dialog" aria-modal="true" aria-labelledby="project-dialog-title">
        <header><span>{project ? "Edit workspace project" : "Create project"}</span><button type="button" aria-label="Close" onClick={onClose}>×</button></header>
        <div className="project-dialog__intro"><small>Project details</small><h2 id="project-dialog-title">{project ? `Update ${project.name}` : "Start something meaningful."}</h2><p>Set the project foundation now. Tasks, documents, and team access can be connected afterward.</p></div>
        <form onSubmit={handleSubmit}>
          <label><span>Project name</span><input name="name" defaultValue={project?.name} placeholder="e.g. Customer portal launch" minLength={2} maxLength={120} required autoFocus /></label>
          <label><span>Description</span><textarea name="description" defaultValue={project?.description} placeholder="What outcome should this project create?" minLength={10} maxLength={320} required /></label>
          <div className="project-dialog__row">
            <label><span>Status</span><select name="status" defaultValue={project?.status ?? "Planning"}><option>Planning</option><option>Active</option><option>At risk</option><option>Completed</option></select></label>
            <label><span>Due date</span><input name="dueDate" type="date" defaultValue={project?.dueDate ?? "2026-12-18"} required /></label>
          </div>
          <footer><button className="project-dialog__cancel" type="button" onClick={onClose}>Cancel</button><button className="project-dialog__save" type="submit">{project ? "Save changes" : "Create project"}<span>→</span></button></footer>
        </form>
      </section>
    </div>
  );
}
