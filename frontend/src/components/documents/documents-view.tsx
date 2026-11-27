"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Icon } from "@/components/ui/icon";
import { ApiError } from "@/services/api-client";
import { listDocuments, type DocumentStatus, type DocumentSummary } from "@/services/documents-api";
import { listProjects, type ProjectRecord } from "@/services/projects-api";
import {
  documentStatusLabel,
  filterDocuments,
  formatBytes,
  formatDocumentDate,
  type DocumentFilter,
} from "./document-data";
import { UploadDialog } from "./upload-dialog";

const filters: readonly DocumentFilter[] = ["all", "available", "validating", "duplicate", "failed"];

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : "Documents could not be loaded.";
}

function statusCount(documents: readonly DocumentSummary[], status: DocumentStatus): number {
  return documents.filter((document) => document.status === status).length;
}

export function DocumentsView() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const [projectId, setProjectId] = useState<number | "all">("all");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const projectNames = useMemo(
    () => new Map(projects.map((project) => [project.id, project.name])),
    [projects],
  );
  const visibleDocuments = useMemo(
    () => filterDocuments(documents, query, filter, projectId),
    [documents, filter, projectId, query],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [documentPage, projectList] = await Promise.all([
        listDocuments({ limit: 50 }),
        listProjects(),
      ]);
      setDocuments([...documentPage.items]);
      setTotal(documentPage.total);
      setHasMore(documentPage.has_more);
      setProjects(projectList);
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 401) {
        router.push("/login");
        return;
      }
      setError(messageFor(loadError));
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  function uploaded(document: DocumentSummary) {
    setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)]);
    setTotal((current) => current + 1);
    setUploadOpen(false);
    setNotice(`${document.original_filename} was preserved and queued for validation.`);
    window.setTimeout(() => setNotice(""), 3200);
  }

  async function loadMoreDocuments() {
    setLoadingMore(true);
    setError("");
    try {
      const page = await listDocuments({ limit: 50, offset: documents.length });
      setDocuments((current) => [...current, ...page.items.filter(
        (item) => !current.some((existing) => existing.id === item.id),
      )]);
      setTotal(page.total);
      setHasMore(page.has_more);
    } catch (loadError) {
      setError(messageFor(loadError));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <main className="documents-page" id="main-content">
      <section className="documents-heading dashboard-enter">
        <div><span className="eyebrow">Source library</span><h1>Documents</h1><p>Preserve original files, follow validation, and trace every extracted task back to its source.</p></div>
        <button className="documents-upload" type="button" onClick={() => setUploadOpen(true)}><span>+</span> Upload document</button>
      </section>

      <section className="documents-summary" aria-label="Document summary">
        <article><span>Total sources</span><strong>{total.toString().padStart(2, "0")}</strong><small>Immutable originals</small></article>
        <article><span>Available</span><strong>{statusCount(documents, "available").toString().padStart(2, "0")}</strong><small>Validated and downloadable</small></article>
        <article><span>Processing</span><strong>{(statusCount(documents, "pending") + statusCount(documents, "validating")).toString().padStart(2, "0")}</strong><small>Upload or validation in progress</small></article>
        <article><span>Needs attention</span><strong>{statusCount(documents, "failed").toString().padStart(2, "0")}</strong><small>Validation failures</small></article>
      </section>

      <section className="documents-toolbar">
        <label><Icon name="search" /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search filename or hash…" aria-label="Search documents" /></label>
        <select value={projectId} onChange={(event) => setProjectId(event.target.value === "all" ? "all" : Number(event.target.value))} aria-label="Filter documents by project"><option value="all">All projects</option>{projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}</select>
        <div className="documents-filters" aria-label="Filter documents by status">{filters.map((status) => <button className={filter === status ? "active" : ""} type="button" key={status} onClick={() => setFilter(status)}>{status === "all" ? "All" : documentStatusLabel(status)}</button>)}</div>
      </section>

      {error && <section className="documents-error" role="alert"><Icon name="document" /><div><strong>Documents are unavailable</strong><p>{error}</p></div><button type="button" onClick={() => void load()}>Try again</button></section>}

      {loading ? (
        <section className="documents-list documents-list--loading" aria-label="Loading documents"><i /><i /><i /><i /></section>
      ) : visibleDocuments.length > 0 ? (
        <><section className="documents-list" aria-live="polite">
          <header><span>Source</span><span>Project</span><span>Status</span><span>Size</span><span>Added</span><span /></header>
          {visibleDocuments.map((document) => (
            <article key={document.id}>
              <div className="document-source"><span><Icon name="document" /></span><div><strong>{document.original_filename}</strong><small>{document.detected_mime_type ?? document.declared_mime_type}</small></div></div>
              <span>{document.project_id ? projectNames.get(document.project_id) ?? `Project #${document.project_id}` : "Workspace"}</span>
              <span className={`document-status document-status--${document.status}`}><i />{documentStatusLabel(document.status)}</span>
              <span>{formatBytes(document.size_bytes ?? document.declared_size)}</span>
              <span>{formatDocumentDate(document.created_at)}</span>
              <Link href={`/documents/${document.id}`} aria-label={`Open ${document.original_filename}`}><Icon name="chevron" /></Link>
            </article>
          ))}
        </section>{hasMore && <button className="documents-load-more" type="button" onClick={() => void loadMoreDocuments()} disabled={loadingMore}>{loadingMore ? "Loading…" : `Load more · ${documents.length} of ${total}`}</button>}</>
      ) : (
        <section className="documents-empty"><Icon name="document" /><h2>{documents.length === 0 ? "No source documents yet" : "No documents found"}</h2><p>{documents.length === 0 ? "Upload a source file to start preserving project knowledge." : "Try another status, project, or search term."}</p>{documents.length === 0 ? <button type="button" onClick={() => setUploadOpen(true)}>Upload first document</button> : <button type="button" onClick={() => { setQuery(""); setFilter("all"); setProjectId("all"); }}>Clear filters</button>}</section>
      )}

      {uploadOpen && <UploadDialog projects={projects} onClose={() => setUploadOpen(false)} onUploaded={uploaded} />}
      {notice && <div className="projects-toast" role="status"><Icon name="check" />{notice}</div>}
    </main>
  );
}
