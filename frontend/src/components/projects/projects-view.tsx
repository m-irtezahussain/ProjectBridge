"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ProjectCard } from "@/components/projects/project-card";
import type { ProjectFilter, ProjectItem, ProjectStatus } from "@/components/projects/project-data";
import { ProjectModal, type ProjectInput } from "@/components/projects/project-modal";
import { Icon } from "@/components/ui/icon";
import {
  createProject,
  deleteProject as deleteProjectRequest,
  getProject,
  listProjectsPage,
  ProjectsApiError,
  updateProject,
  type ProjectListOptions,
} from "@/services/projects-api";

const PAGE_SIZE = 24;
const filters: readonly ProjectFilter[] = ["All", "Active", "Planning", "At risk", "Completed"];
const statuses = new Set<ProjectStatus>(["Active", "Planning", "At risk", "Completed"]);

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : "We could not complete that request. Please try again.";
}

function positiveOffset(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}

export function ProjectsView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlStatus = searchParams.get("status");
  const filter: ProjectFilter = urlStatus && statuses.has(urlStatus as ProjectStatus)
    ? urlStatus as ProjectStatus
    : "All";
  const query = searchParams.get("q") ?? "";
  const requestedSort = searchParams.get("sort");
  const sortBy = requestedSort === "name" || requestedSort === "status" ? requestedSort : "id";
  const sortOrder = searchParams.get("order") === "asc" ? "asc" : "desc";
  const offset = positiveOffset(searchParams.get("offset"));

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [total, setTotal] = useState(0);
  const [queryInput, setQueryInput] = useState(query);
  const [editor, setEditor] = useState<{ project?: ProjectItem } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectItem | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pageError, setPageError] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
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

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setPageError("");
    const options: ProjectListOptions = {
      limit: PAGE_SIZE,
      offset,
      status: filter === "All" ? undefined : filter,
      query: query || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    };
    try {
      const page = await listProjectsPage(options);
      setProjects([...page.items]);
      setTotal(page.total);
      if (offset > 0 && page.items.length === 0 && page.total > 0) {
        const lastOffset = Math.floor((page.total - 1) / PAGE_SIZE) * PAGE_SIZE;
        replaceParams({ offset: String(lastOffset) });
      }
    } catch (error) {
      if (error instanceof ProjectsApiError && error.status === 401) {
        router.push("/login");
        return;
      }
      setPageError(messageFor(error));
    } finally {
      setLoading(false);
    }
  }, [filter, offset, query, replaceParams, router, sortBy, sortOrder]);

  useEffect(() => {
    const timer = window.setTimeout(() => setQueryInput(query), 0);
    return () => window.clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const timer = window.setTimeout(() => { void loadProjects(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadProjects]);
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

  function showNotice(message: string) {
    setNotice(message);
    if (noticeTimer.current !== undefined) window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(""), 2600);
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
      const wasEditing = Boolean(editor?.project);
      const saved = editor?.project
        ? await updateProject(editor.project.id, input)
        : await createProject(input);
      setEditor(null);
      showNotice(`${saved.name} was ${wasEditing ? "updated" : "created"}.`);
      await loadProjects();
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
      setDeletingId(null);
      showNotice(`${target.name} was dismissed.`);
      await loadProjects();
    } catch (error) {
      setDeletingId(null);
      setPageError(messageFor(error));
    }
  }

  const firstResult = total === 0 ? 0 : offset + 1;
  const lastResult = Math.min(offset + projects.length, total);

  return (
    <main className="projects-page" id="main-content">
      <section className="projects-heading dashboard-enter">
        <div><span className="eyebrow">Portfolio</span><h1>Projects</h1><p>Keep every initiative, source document, and team handoff moving in one place.</p></div>
        <button className="projects-create" type="button" onClick={() => { setEditor({}); setFormError(""); }}><span>+</span> Create new project</button>
      </section>
      <section className="projects-summary" aria-label="Project summary">
        <article><span>Matching projects</span><strong>{total.toString().padStart(2, "0")}</strong><small>Across this workspace</small></article>
        <article><span>Active now</span><strong>{projects.filter((project) => project.status === "Active").length.toString().padStart(2, "0")}</strong><small>On this page</small></article>
        <article><span>Completed</span><strong>{projects.filter((project) => project.status === "Completed").length.toString().padStart(2, "0")}</strong><small>On this page</small></article>
        <article><span>Needs attention</span><strong>{projects.filter((project) => project.status === "At risk").length.toString().padStart(2, "0")}</strong><small>On this page</small></article>
      </section>
      <section className="projects-toolbar">
        <label><Icon name="search" /><input type="search" value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="Search projects…" aria-label="Search projects" /></label>
        <div className="projects-filters" aria-label="Filter projects">{filters.map((item) => <button className={filter === item ? "active" : ""} type="button" key={item} onClick={() => replaceParams({ status: item === "All" ? null : item, offset: null })}>{item}</button>)}</div>
        <label className="discovery-sort"><span>Sort</span><select aria-label="Sort projects" value={`${sortBy}:${sortOrder}`} onChange={(event) => { const [sort, order] = event.target.value.split(":"); replaceParams({ sort, order, offset: null }); }}><option value="id:desc">Newest first</option><option value="id:asc">Oldest first</option><option value="name:asc">Name A–Z</option><option value="name:desc">Name Z–A</option><option value="status:asc">Status</option></select></label>
        <small>{firstResult}–{lastResult} of {total}</small>
      </section>
      {pageError && <section className="projects-error" role="alert"><Icon name="document" /><div><strong>Projects could not be updated</strong><p>{pageError}</p></div><button type="button" onClick={() => void loadProjects()}>Try again</button></section>}
      {loading ? (
        <section className="projects-grid projects-grid--loading" aria-label="Loading projects"><i /><i /><i /><i /></section>
      ) : projects.length > 0 ? (
        <><section className="projects-grid" aria-live="polite">{projects.map((project, index) => <ProjectCard project={project} index={index} deleting={deletingId === project.id} onEdit={(selected) => void openEditor(selected)} onDelete={setDeleteTarget} key={project.id} />)}</section><nav className="discovery-pagination" aria-label="Projects pages"><button type="button" disabled={offset === 0} onClick={() => replaceParams({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}>Previous</button><span>Page {Math.floor(offset / PAGE_SIZE) + 1} of {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span><button type="button" disabled={offset + projects.length >= total} onClick={() => replaceParams({ offset: String(offset + PAGE_SIZE) })}>Next</button></nav></>
      ) : (
        <section className="projects-empty"><Icon name="search" /><h2>{total === 0 && !query && filter === "All" ? "No projects yet" : "No projects found"}</h2><p>{total === 0 && !query && filter === "All" ? "Create your first project to get the workspace moving." : "Try a different search or status filter."}</p>{(query || filter !== "All") && <button type="button" onClick={() => { setQueryInput(""); replaceParams({ q: null, status: null, offset: null }); }}>Clear filters</button>}</section>
      )}
      {editor && <ProjectModal key={editor.project?.id ?? "new"} project={editor.project} onClose={() => setEditor(null)} onSave={saveProject} error={formError} saving={saving} />}
      {deleteTarget && <div className="project-dialog-layer"><button className="project-dialog-backdrop" type="button" aria-label="Cancel project deletion" onClick={() => setDeleteTarget(null)} /><section className="project-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-project-title"><span className="project-delete-dialog__icon"><Icon name="trash" /></span><small>Dismiss project</small><h2 id="delete-project-title">Dismiss {deleteTarget.name}?</h2><p>The project will be removed from active views while remaining available in the database for audit and recovery.</p><footer><button type="button" onClick={() => setDeleteTarget(null)} disabled={deletingId !== null}>Keep project</button><button className="danger" type="button" onClick={() => void deleteProject()} disabled={deletingId !== null}>{deletingId !== null ? "Dismissing…" : "Dismiss project"}</button></footer></section></div>}
      {notice && <div className="projects-toast" role="status"><Icon name="check" />{notice}</div>}
    </main>
  );
}
