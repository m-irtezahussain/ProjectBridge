import type { CSSProperties } from "react";
import Link from "next/link";

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
  const accents = ["lime", "violet", "amber", "blue"] as const;
  const accent = accents[project.id % accents.length];
  return (
    <article className={`projects-card projects-card--${accent}${deleting ? " is-deleting" : ""}`} style={{ "--i": index } as CSSProperties}>
      <header>
        <span className={`projects-status projects-status--${statusClass}`}><i />{project.status}</span>
        <div className="projects-card__actions">
          <button type="button" aria-label={`Edit ${project.name}`} title="Edit project" onClick={() => onEdit(project)}><Icon name="edit" /></button>
          <button className="danger" type="button" aria-label={`Dismiss ${project.name}`} title="Dismiss project" onClick={() => onDelete(project)}><Icon name="trash" /></button>
        </div>
      </header>
      <div className="projects-card__title"><i /><div><h2>{project.name}</h2><small>Project #{project.id}</small></div></div>
      <p>{project.description ?? "No description has been added yet."}</p>
      <div className="projects-card__facts">
        <span><small>Status</small><strong>{project.status}</strong></span>
        <span><small>Workspace</small><strong>#{project.business_id}</strong></span>
        <span><small>Tasks</small><strong>—</strong></span>
      </div>
      <footer>
        <small className="projects-card__source">Synced with API</small>
        <Link className="projects-card__open" href={`/projects/${project.id}`}>Open project <Icon name="arrow" /></Link>
      </footer>
    </article>
  );
}
