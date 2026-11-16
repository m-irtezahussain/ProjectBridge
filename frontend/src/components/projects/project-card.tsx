import type { CSSProperties } from "react";

import { Icon } from "@/components/ui/icon";
import type { ProjectItem } from "@/components/projects/project-data";

type ProjectCardProps = Readonly<{
  project: ProjectItem;
  index: number;
  deleting: boolean;
  onEdit: (project: ProjectItem) => void;
  onDelete: (project: ProjectItem) => void;
}>;

export function ProjectCard({ project, index, deleting, onEdit, onDelete }: ProjectCardProps) {
  const statusClass = project.status.toLowerCase().replace(" ", "-");
  return (
    <article className={`projects-card projects-card--${project.accent}${deleting ? " is-deleting" : ""}`} style={{ "--i": index } as CSSProperties}>
      <header>
        <span className={`projects-status projects-status--${statusClass}`}><i />{project.status}</span>
        <div className="projects-card__actions">
          <button type="button" aria-label={`Edit ${project.name}`} title="Edit project" onClick={() => onEdit(project)}><Icon name="edit" /></button>
          <button className="danger" type="button" aria-label={`Delete ${project.name}`} title="Delete project" onClick={() => onDelete(project)}><Icon name="trash" /></button>
        </div>
      </header>
      <div className="projects-card__title"><i /><div><h2>{project.name}</h2><small>Updated {project.updated}</small></div></div>
      <p>{project.description}</p>
      <div className="projects-card__progress"><span><i style={{ width: `${project.progress}%` }} /></span><b>{project.progress}%</b></div>
      <div className="projects-card__facts">
        <span><small>Tasks</small><strong>{project.tasksDone}<i>/ {project.tasksTotal}</i></strong></span>
        <span><small>Due date</small><strong>{project.dueLabel}</strong></span>
        <span><small>Sources</small><strong>{project.documents}<i> docs</i></strong></span>
      </div>
      <footer>
        <div className="projects-card__members">{project.members.map((member) => <span key={member}>{member}</span>)}<button type="button" aria-label={`Add member to ${project.name}`}>+</button></div>
        <button className="projects-card__open" type="button">Open project <Icon name="arrow" /></button>
      </footer>
    </article>
  );
}
