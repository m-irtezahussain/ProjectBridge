"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/ui/icon";
import { ProjectCard } from "@/components/projects/project-card";
import {
  filterProjects,
  initialProjects,
  type ProjectFilter,
  type ProjectItem,
} from "@/components/projects/project-data";
import { ProjectModal, type ProjectInput } from "@/components/projects/project-modal";

const filters: readonly ProjectFilter[] = ["All", "Active", "Planning", "At risk", "Completed"];

function dueLabel(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
  });
}

export function ProjectsView() {
  const [projects, setProjects] = useState<ProjectItem[]>([...initialProjects]);
  const [filter, setFilter] = useState<ProjectFilter>("All");
  const [query, setQuery] = useState("");
  const [editor, setEditor] = useState<{ project?: ProjectItem } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectItem | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const visibleProjects = useMemo(
    () => filterProjects(projects, query, filter),
    [projects, query, filter],
  );
  const averageProgress = projects.length === 0
    ? 0
    : Math.round(
      projects.reduce((total, project) => total + project.progress, 0) / projects.length,
    );

  function showNotice(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2600);
  }

  function saveProject(input: ProjectInput) {
    if (editor?.project) {
      setProjects((current) => current.map((project) => project.id === editor.project?.id ? {
        ...project,
        ...input,
        dueLabel: dueLabel(input.dueDate),
        updated: "just now",
      } : project));
      showNotice(`${input.name} was updated.`);
    } else {
      const accentOptions: ProjectItem["accent"][] = ["lime", "violet", "amber", "blue"];
      setProjects((current) => [{
        id: `project-${Date.now()}`,
        ...input,
        dueLabel: dueLabel(input.dueDate),
        progress: input.status === "Completed" ? 100 : 0,
        tasksDone: 0,
        tasksTotal: 0,
        documents: 0,
        members: ["YOU"],
        updated: "just now",
        accent: accentOptions[current.length % accentOptions.length],
      }, ...current]);
      showNotice(`${input.name} was created.`);
    }
    setEditor(null);
  }

  function deleteProject() {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setDeletingId(target.id);
    setDeleteTarget(null);
    window.setTimeout(() => {
      setProjects((current) => current.filter((project) => project.id !== target.id));
      setDeletingId(null);
      showNotice(`${target.name} was removed from this demo.`);
    }, 180);
  }

  return (
    <main className="projects-page" id="main-content">
      <section className="projects-heading dashboard-enter">
        <div><span className="eyebrow">Portfolio</span><h1>Projects</h1><p>Keep every initiative, source document, and team handoff moving in one place.</p></div>
        <button className="projects-create" type="button" onClick={() => setEditor({})}><span>+</span> Create new project</button>
      </section>
      <section className="projects-summary" aria-label="Project summary">
        <article><span>Total projects</span><strong>{projects.length.toString().padStart(2, "0")}</strong><small>Across this workspace</small></article>
        <article><span>Active now</span><strong>{projects.filter((project) => project.status === "Active").length.toString().padStart(2, "0")}</strong><small>Work currently moving</small></article>
        <article><span>Average progress</span><strong>{averageProgress}%</strong><small>Across all projects</small></article>
        <article><span>Needs attention</span><strong>{projects.filter((project) => project.status === "At risk").length.toString().padStart(2, "0")}</strong><small>Projects currently at risk</small></article>
      </section>
      <section className="projects-toolbar">
        <label><Icon name="search" /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search projects…" aria-label="Search projects" /></label>
        <div className="projects-filters" aria-label="Filter projects">{filters.map((item) => <button className={filter === item ? "active" : ""} type="button" key={item} onClick={() => setFilter(item)}>{item}<span>{item === "All" ? projects.length : projects.filter((project) => project.status === item).length}</span></button>)}</div>
        <small>{visibleProjects.length} project{visibleProjects.length === 1 ? "" : "s"}</small>
      </section>
      {visibleProjects.length > 0 ? (
        <section className="projects-grid" aria-live="polite">{visibleProjects.map((project, index) => <ProjectCard project={project} index={index} deleting={deletingId === project.id} onEdit={(selected) => setEditor({ project: selected })} onDelete={setDeleteTarget} key={project.id} />)}</section>
      ) : (
        <section className="projects-empty"><Icon name="search" /><h2>No projects found</h2><p>Try a different search or status filter.</p><button type="button" onClick={() => { setQuery(""); setFilter("All"); }}>Clear filters</button></section>
      )}
      {editor && <ProjectModal key={editor.project?.id ?? "new"} project={editor.project} onClose={() => setEditor(null)} onSave={saveProject} />}
      {deleteTarget && <div className="project-dialog-layer"><button className="project-dialog-backdrop" type="button" aria-label="Cancel project deletion" onClick={() => setDeleteTarget(null)} /><section className="project-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-project-title"><span className="project-delete-dialog__icon"><Icon name="trash" /></span><small>Delete project</small><h2 id="delete-project-title">Remove {deleteTarget.name}?</h2><p>This demo removes the project from the current browser state. Connected tasks and documents will not be changed.</p><footer><button type="button" onClick={() => setDeleteTarget(null)}>Keep project</button><button className="danger" type="button" onClick={deleteProject}>Delete project</button></footer></section></div>}
      {notice && <div className="projects-toast" role="status"><Icon name="check" />{notice}</div>}
    </main>
  );
}
