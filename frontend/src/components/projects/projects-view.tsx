"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ProjectCard } from "@/components/projects/project-card";
import {
  filterProjects,
  type ProjectFilter,
  type ProjectItem,
} from "@/components/projects/project-data";
import { ProjectModal, type ProjectInput } from "@/components/projects/project-modal";
import { Icon } from "@/components/ui/icon";
import {
  createProject,
  deleteProject as deleteProjectRequest,
  getProject,
  listProjects,
  ProjectsApiError,
  updateProject,
} from "@/services/projects-api";

const filters: readonly ProjectFilter[] = [
  "All",
  "Active",
  "Planning",
  "At risk",
  "Completed",
];

function messageFor(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "We could not complete that request. Please try again.";
}

export function ProjectsView() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [filter, setFilter] = useState<ProjectFilter>("All");
  const [query, setQuery] = useState("");
  const [editor, setEditor] = useState<{ project?: ProjectItem } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectItem | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pageError, setPageError] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");

  const visibleProjects = useMemo(
    () => filterProjects(projects, query, filter),
    [projects, query, filter],
  );

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setPageError("");
    try {
      setProjects(await listProjects());
    } catch (error) {
      if (error instanceof ProjectsApiError && error.status === 401) {
        router.push("/login");
        return;
      }
      setPageError(messageFor(error));
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    let active = true;
    async function initialLoad() {
      try {
        const loadedProjects = await listProjects();
        if (active) setProjects(loadedProjects);
      } catch (error) {
        if (!active) return;
        if (error instanceof ProjectsApiError && error.status === 401) {
          router.push("/login");
          return;
        }
        setPageError(messageFor(error));
      } finally {
        if (active) setLoading(false);
      }
    }
    void initialLoad();
    return () => { active = false; };
  }, [router]);

  function showNotice(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2600);
  }

  async function openEditor(project: ProjectItem) {
    setPageError("");
    try {
      setEditor({ project: await getProject(project.id) });
      setFormError("");
    } catch (error) {
      setPageError(messageFor(error));
    }
  }

  async function saveProject(input: ProjectInput) {
    setSaving(true);
    setFormError("");
    try {
      if (editor?.project) {
        const updated = await updateProject(editor.project.id, input);
        setProjects((current) => current.map((project) => (
          project.id === updated.id ? updated : project
        )));
        showNotice(`${updated.name} was updated.`);
      } else {
        const created = await createProject(input);
        setProjects((current) => [created, ...current]);
        showNotice(`${created.name} was created.`);
      }
      setEditor(null);
    } catch (error) {
      setFormError(messageFor(error));
    } finally {
      setSaving(false);
    }
  }

  async function deleteProject() {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setDeletingId(target.id);
    setPageError("");
    try {
      await deleteProjectRequest(target.id);
      setDeleteTarget(null);
      window.setTimeout(() => {
        setProjects((current) => current.filter((project) => project.id !== target.id));
        setDeletingId(null);
        showNotice(`${target.name} was dismissed.`);
      }, 180);
    } catch (error) {
      setDeletingId(null);
      setPageError(messageFor(error));
    }
  }

  return (
    <main className="projects-page" id="main-content">
      <section className="projects-heading dashboard-enter">
        <div><span className="eyebrow">Portfolio</span><h1>Projects</h1><p>Keep every initiative, source document, and team handoff moving in one place.</p></div>
        <button className="projects-create" type="button" onClick={() => { setEditor({}); setFormError(""); }}><span>+</span> Create new project</button>
      </section>
      <section className="projects-summary" aria-label="Project summary">
        <article><span>Total projects</span><strong>{projects.length.toString().padStart(2, "0")}</strong><small>Across this workspace</small></article>
        <article><span>Active now</span><strong>{projects.filter((project) => project.status === "Active").length.toString().padStart(2, "0")}</strong><small>Work currently moving</small></article>
        <article><span>Completed</span><strong>{projects.filter((project) => project.status === "Completed").length.toString().padStart(2, "0")}</strong><small>Finished projects</small></article>
        <article><span>Needs attention</span><strong>{projects.filter((project) => project.status === "At risk").length.toString().padStart(2, "0")}</strong><small>Projects currently at risk</small></article>
      </section>
      <section className="projects-toolbar">
        <label><Icon name="search" /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search projects…" aria-label="Search projects" /></label>
        <div className="projects-filters" aria-label="Filter projects">{filters.map((item) => <button className={filter === item ? "active" : ""} type="button" key={item} onClick={() => setFilter(item)}>{item}<span>{item === "All" ? projects.length : projects.filter((project) => project.status === item).length}</span></button>)}</div>
        <small>{visibleProjects.length} project{visibleProjects.length === 1 ? "" : "s"}</small>
      </section>
      {pageError && <section className="projects-error" role="alert"><Icon name="document" /><div><strong>Projects could not be updated</strong><p>{pageError}</p></div><button type="button" onClick={() => void loadProjects()}>Try again</button></section>}
      {loading ? (
        <section className="projects-grid projects-grid--loading" aria-label="Loading projects"><i /><i /><i /><i /></section>
      ) : visibleProjects.length > 0 ? (
        <section className="projects-grid" aria-live="polite">{visibleProjects.map((project, index) => <ProjectCard project={project} index={index} deleting={deletingId === project.id} onEdit={(selected) => void openEditor(selected)} onDelete={setDeleteTarget} key={project.id} />)}</section>
      ) : (
        <section className="projects-empty"><Icon name="search" /><h2>{projects.length === 0 ? "No projects yet" : "No projects found"}</h2><p>{projects.length === 0 ? "Create your first project to get the workspace moving." : "Try a different search or status filter."}</p>{projects.length > 0 && <button type="button" onClick={() => { setQuery(""); setFilter("All"); }}>Clear filters</button>}</section>
      )}
      {editor && <ProjectModal key={editor.project?.id ?? "new"} project={editor.project} onClose={() => setEditor(null)} onSave={saveProject} error={formError} saving={saving} />}
      {deleteTarget && <div className="project-dialog-layer"><button className="project-dialog-backdrop" type="button" aria-label="Cancel project deletion" onClick={() => setDeleteTarget(null)} /><section className="project-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-project-title"><span className="project-delete-dialog__icon"><Icon name="trash" /></span><small>Dismiss project</small><h2 id="delete-project-title">Dismiss {deleteTarget.name}?</h2><p>The project will be removed from active views while remaining available in the database for audit and recovery.</p><footer><button type="button" onClick={() => setDeleteTarget(null)} disabled={deletingId !== null}>Keep project</button><button className="danger" type="button" onClick={() => void deleteProject()} disabled={deletingId !== null}>{deletingId !== null ? "Dismissing…" : "Dismiss project"}</button></footer></section></div>}
      {notice && <div className="projects-toast" role="status"><Icon name="check" />{notice}</div>}
    </main>
  );
}
