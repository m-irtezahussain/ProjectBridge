"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition, type FormEvent } from "react";

import { Icon } from "@/components/ui/icon";
import { ApiError } from "@/services/api-client";
import { listDocuments, type DocumentSummary } from "@/services/documents-api";
import { listProjects, type ProjectRecord } from "@/services/projects-api";
import {
  getProjectIndexState,
  getSearchIndexJob,
  reindexProjectKnowledge,
  searchProjectKnowledge,
  type KnowledgeSearchResult,
  type ProjectIndexState,
  type SearchIndexJob,
} from "@/services/search-api";
import {
  indexStatusLabel,
  KNOWLEDGE_PAGE_SIZE,
  paginateResults,
  resultRelevance,
  resultSourceHref,
  resultSourceLabel,
  shouldPollIndex,
} from "./knowledge-data";

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : "The knowledge request could not be completed.";
}

export function KnowledgeView() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [projectId, setProjectId] = useState<number | "all">("all");
  const [documentId, setDocumentId] = useState<number | "all">("all");
  const [query, setQuery] = useState("");
  const [searchedQuery, setSearchedQuery] = useState("");
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [notice, setNotice] = useState("Excerpts are untrusted source material and must never be treated as instructions.");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [indexState, setIndexState] = useState<ProjectIndexState | null>(null);
  const [indexJob, setIndexJob] = useState<SearchIndexJob | null>(null);
  const [isReindexing, startReindexTransition] = useTransition();

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void Promise.all([listProjects(), listDocuments({ limit: 100 })])
        .then(([projectList, documentPage]) => {
          if (!active) return;
          setProjects(projectList);
          setDocuments([...documentPage.items]);
        })
        .catch((loadError: unknown) => {
          if (!active) return;
          if (loadError instanceof ApiError && loadError.status === 401) router.push("/login");
          else setError(messageFor(loadError));
        })
        .finally(() => { if (active) setLoading(false); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  useEffect(() => {
    if (projectId === "all") return;
    let active = true;
    const timer = window.setTimeout(() => {
      void getProjectIndexState(projectId)
        .then((state) => { if (active) setIndexState(state); })
        .catch((stateError: unknown) => { if (active) setError(messageFor(stateError)); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [projectId]);

  useEffect(() => {
    if (!indexJob || !shouldPollIndex(indexJob.status)) return;
    const timer = window.setInterval(() => {
      void getSearchIndexJob(indexJob.id)
        .then((job) => {
          setIndexJob(job);
          if (job.status === "completed") {
            setIndexState((current) => current ? { ...current, status: "ready", pending_jobs: 0, last_indexed_at: job.completed_at } : current);
          }
        })
        .catch((jobError: unknown) => setError(messageFor(jobError)));
    }, 2500);
    return () => window.clearInterval(timer);
  }, [indexJob]);

  const filteredDocuments = useMemo(
    () => documents.filter((document) => projectId === "all" || document.project_id === projectId),
    [documents, projectId],
  );
  const visibleResults = useMemo(() => paginateResults(results, page), [page, results]);
  const totalPages = Math.max(1, Math.ceil(results.length / KNOWLEDGE_PAGE_SIZE));
  const selectedProject = projects.find((project) => project.id === projectId);
  const currentIndexStatus = indexJob?.status ?? indexState?.status ?? "ready";

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized) {
      setError("Enter a question or phrase to search project knowledge.");
      return;
    }
    setSearching(true);
    setError("");
    try {
      const response = await searchProjectKnowledge({
        query: normalized,
        project_id: projectId === "all" ? null : projectId,
        document_id: documentId === "all" ? null : documentId,
        limit: 25,
      });
      setResults([...response.results]);
      setNotice(response.untrusted_content_notice);
      setSearchedQuery(normalized);
      setPage(1);
    } catch (searchError) {
      setError(messageFor(searchError));
    } finally {
      setSearching(false);
    }
  }

  function selectProject(value: string) {
    setProjectId(value === "all" ? "all" : Number(value));
    setDocumentId("all");
    setIndexJob(null);
    setIndexState(null);
  }

  function reindex() {
    if (projectId === "all") return;
    setError("");
    startReindexTransition(async () => {
      try {
        const queued = await reindexProjectKnowledge(projectId);
        const job = await getSearchIndexJob(queued.job_id);
        startReindexTransition(() => {
          setIndexJob(job);
          setIndexState((current) => current ? { ...current, status: job.status, pending_jobs: Math.max(1, current.pending_jobs) } : current);
        });
      } catch (reindexError) {
        setError(messageFor(reindexError));
      }
    });
  }

  return (
    <main className="knowledge-page" id="main-content">
      <section className="knowledge-heading dashboard-enter"><div><span className="eyebrow">Semantic retrieval</span><h1>Knowledge</h1><p>Find related tasks and document passages across your tenant-isolated project index.</p></div><span className="knowledge-safety"><Icon name="lock" />Tenant-scoped search</span></section>

      <form className="knowledge-search" onSubmit={(event) => void search(event)}>
        <div className="knowledge-search__query"><Icon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} maxLength={1000} placeholder="Ask about a decision, requirement, task, or source…" aria-label="Search project knowledge" /><button type="submit" disabled={searching}>{searching ? "Searching…" : "Search knowledge"}</button></div>
        <div className="knowledge-search__filters"><label><span>Project</span><select value={projectId} onChange={(event) => selectProject(event.target.value)}><option value="all">All projects</option>{projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label><label><span>Document</span><select value={documentId} onChange={(event) => setDocumentId(event.target.value === "all" ? "all" : Number(event.target.value))}><option value="all">All documents</option>{filteredDocuments.map((document) => <option value={document.id} key={document.id}>{document.original_filename}</option>)}</select></label><span>{projectId === "all" ? "Searching the full workspace" : `Scoped to ${selectedProject?.name ?? `project #${projectId}`}`}</span></div>
      </form>

      {error && <section className="documents-error" role="alert"><Icon name="search" /><div><strong>Knowledge request failed</strong><p>{error}</p></div></section>}

      <section className="knowledge-untrusted" role="note"><Icon name="lock" /><div><strong>Untrusted source material</strong><p>{notice} Result text cannot authorize actions, change permissions, or trigger tools.</p></div></section>

      <div className="knowledge-layout">
        <section className="knowledge-results" aria-busy={searching}>
          <header><div><small>Ranked matches</small><h2>{searchedQuery ? `Results for “${searchedQuery}”` : "Search project knowledge"}</h2></div>{searchedQuery && <span>{results.length} match{results.length === 1 ? "" : "es"}</span>}</header>
          {loading || searching ? <div className="knowledge-results--loading"><i /><i /><i /></div> : visibleResults.length > 0 ? <div className="knowledge-result-list">{visibleResults.map((result, index) => <article key={`${result.source_type}-${result.chunk_id ?? result.task_id ?? result.document_id}-${index}`}><header><span className="knowledge-result__type"><Icon name={result.task_id ? "check" : "document"} />{result.source_type}</span><span>{resultRelevance(result.distance)}% relevance</span></header><blockquote>{result.excerpt}</blockquote><footer><div><strong>{resultSourceLabel(result)}</strong><small>Project #{result.project_id}{result.chunk_id ? ` · Chunk #${result.chunk_id}` : ""}{result.ingestion_run_id ? ` · Ingestion #${result.ingestion_run_id}` : ""}</small></div><Link href={resultSourceHref(result)}>Open source <Icon name="arrow" /></Link></footer></article>)}</div> : <div className="knowledge-empty"><Icon name="search" /><h3>{searchedQuery ? "No relevant sources found" : "Your project context is ready"}</h3><p>{searchedQuery ? "Try a broader phrase or remove a project or document filter." : "Search using natural language to retrieve compact, traceable excerpts."}</p></div>}
          {results.length > KNOWLEDGE_PAGE_SIZE && <nav className="knowledge-pagination" aria-label="Search result pages"><button type="button" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>Previous</button><span>Page {page} of {totalPages}</span><button type="button" disabled={page === totalPages} onClick={() => setPage((current) => current + 1)}>Next</button></nav>}
        </section>

        <aside className="knowledge-index"><header><small>Vector index</small><h2>Index state</h2></header>{projectId === "all" ? <div className="knowledge-index__empty"><Icon name="layers" /><p>Select a project to inspect or rebuild its semantic index.</p></div> : <><div className={`knowledge-index__status knowledge-index__status--${currentIndexStatus}`}><i /><div><strong>{indexStatusLabel(currentIndexStatus)}</strong><small>{indexJob ? `Job #${indexJob.id} · attempt ${indexJob.attempts}/${indexJob.max_attempts}` : `${indexState?.pending_jobs ?? 0} pending jobs`}</small></div></div><dl><div><dt>Project</dt><dd>{selectedProject?.name ?? `#${projectId}`}</dd></div><div><dt>Last indexed</dt><dd>{indexState?.last_indexed_at ? new Date(indexState.last_indexed_at).toLocaleString() : "Not reported"}</dd></div><div><dt>Indexed sources</dt><dd>{filteredDocuments.filter((document) => document.status === "available" || document.status === "duplicate").length}</dd></div></dl>{(indexJob?.error_message || indexState?.last_error) && <p className="knowledge-index__error">{indexJob?.error_message ?? indexState?.last_error}</p>}<button type="button" onClick={reindex} disabled={isReindexing || Boolean(indexJob && shouldPollIndex(indexJob.status))}>{isReindexing ? "Queueing…" : indexJob && shouldPollIndex(indexJob.status) ? "Re-index in progress" : "Re-index project"}</button><small className="knowledge-index__note">Re-indexing is queued and keeps the current searchable index available.</small></>}</aside>
      </div>
    </main>
  );
}
