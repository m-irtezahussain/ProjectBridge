import type { CSSProperties } from "react";

import { Icon } from "@/components/ui/icon";
import { projectSummaries } from "@/data/dashboard";

export function ProjectHealth() {
  return (
    <section className="dashboard-card project-health dashboard-enter" id="projects" style={{ "--i": 5 } as CSSProperties}>
      <header className="dashboard-card__header">
        <div><span>Portfolio</span><h2>Project health</h2></div>
        <a href="#projects">View all <Icon name="arrow" /></a>
      </header>
      <div className="project-table" role="table" aria-label="Project health">
        <div className="project-table__head" role="row"><span>Project</span><span>Progress</span><span>Due date</span><span>Status</span><span>Team</span></div>
        {projectSummaries.map((project, index) => (
          <article className="project-row" role="row" key={project.name}>
            <div><i className={`project-dot project-dot--${index + 1}`} /><span><strong>{project.name}</strong><small>{project.client}</small></span></div>
            <div className="project-progress"><span><i style={{ width: `${project.progress}%` }} /></span><b>{project.progress}%</b></div>
            <time>{project.due}</time>
            <em className={`project-status project-status--${project.status.toLowerCase().replace(" ", "-")}`}>{project.status}</em>
            <div className="project-avatars">{project.members.map((member) => <span key={member}>{member}</span>)}</div>
          </article>
        ))}
      </div>
    </section>
  );
}
