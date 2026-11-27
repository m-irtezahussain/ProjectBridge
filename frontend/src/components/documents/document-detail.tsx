"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Icon } from "@/components/ui/icon";
import { ApiError, VersionConflictError } from "@/services/api-client";
import {
  archiveDocument,
  getDocument,
  getDocumentDownloadUrl,
  type DocumentSummary,
} from "@/services/documents-api";
import { getProject, type ProjectRecord } from "@/services/projects-api";
import {
  documentStatusLabel,
  documentStatusProgress,
  formatBytes,
  formatDocumentDate,
} from "./document-data";
import { IngestionPanel } from "./ingestion-panel";

type DocumentDetailProps = Readonly<{ documentId: number }>;

function shortHash(hash: string | null): string {
  return hash ? `${hash.slice(0, 14)}…${hash.slice(-10)}` : "Assigned after validation";
}

export function DocumentDetail({ documentId }: DocumentDetailProps) {
  const router = useRouter();
  const [document, setDocument] = useState<DocumentSummary | null>(null);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [archiving, setArchiving] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError("");
    try {
      const loaded = await getDocument(documentId);
      setDocument(loaded);
      if (loaded.project_id) setProject(await getProject(loaded.project_id));
      else setProject(null);
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 401) router.push("/login");
      else setError(loadError instanceof Error ? loadError.message : "The document could not be loaded.");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [documentId, router]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  useEffect(() => {
    if (document?.status !== "pending" && document?.status !== "validating") return;
    const timer = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(timer);
  }, [document?.status, load]);

  async function download() {
    if (!document) return;
    setDownloading(true);
    setError("");
    try {
      const target = await getDocumentDownloadUrl(document.id);
      const anchor = window.document.createElement("a");
      anchor.href = target.url;
      anchor.rel = "noreferrer";
      anchor.download = document.original_filename;
      anchor.click();
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "The download could not be prepared.");
    } finally {
      setDownloading(false);
    }
  }

  async function archive() {
    if (!document) return;
    if (!window.confirm(`Archive ${document.original_filename}? Its immutable raw source and audit history will be retained.`)) return;
    setArchiving(true);
    setError("");
    try {
      await archiveDocument(document.id, document.version, crypto.randomUUID());
      router.push("/documents");
    } catch (archiveError) {
      if (archiveError instanceof VersionConflictError) await load();
      setError(archiveError instanceof Error ? archiveError.message : "The document could not be archived.");
      setArchiving(false);
    }
  }

  if (loading) return <main className="document-detail document-detail--loading"><header /><section /><div><i /><i /><i /></div></main>;
  if (!document) return <main className="document-detail"><section className="documents-error" role="alert"><Icon name="document" /><div><strong>Document unavailable</strong><p>{error || "This source could not be found."}</p></div><button type="button" onClick={() => void load()}>Try again</button></section></main>;

  const canDownload = document.status === "available" || document.status === "duplicate";

  return (
    <main className="document-detail" id="main-content">
      <Link className="document-back" href="/documents">← Back to documents</Link>
      <section className="document-detail__heading">
        <div><span className="eyebrow">Source #{document.id}</span><h1>{document.original_filename}</h1><p>Original file metadata and immutable validation record.</p></div>
        <div className="document-detail__actions"><button type="button" onClick={() => void download()} disabled={!canDownload || downloading}>{downloading ? "Preparing…" : "Download original"}</button><button className="danger" type="button" onClick={() => void archive()} disabled={archiving}>{archiving ? "Archiving…" : "Archive"}</button></div>
      </section>

      {error && <section className="documents-error" role="alert"><Icon name="document" /><div><strong>Request could not be completed</strong><p>{error}</p></div></section>}

      <section className={`document-progress document-progress--${document.status}`}>
        <header><div><span className={`document-status document-status--${document.status}`}><i />{documentStatusLabel(document.status)}</span><strong>{documentStatusProgress(document.status)}%</strong></div><span><i style={{ width: `${documentStatusProgress(document.status)}%` }} /></span></header>
        <p>{document.status === "failed" ? document.failure_message ?? "The source did not pass validation." : document.status === "duplicate" ? "This content already exists. ProjectBridge preserved this record and linked it to the canonical source." : document.status === "available" ? "Validation complete. The immutable source is ready for ingestion and download." : "ProjectBridge is validating file signatures, safety limits, and immutable storage."}</p>
        {document.failure_code && <code>{document.failure_code}</code>}
        {document.duplicate_of_document_id && <Link href={`/documents/${document.duplicate_of_document_id}`}>Open canonical document #{document.duplicate_of_document_id} <Icon name="arrow" /></Link>}
      </section>

      <div className="document-detail__grid">
        <section className="document-metadata"><header><small>Source metadata</small><h2>Original file</h2></header><dl><div><dt>Original filename</dt><dd>{document.original_filename}</dd></div><div><dt>Detected type</dt><dd>{document.detected_mime_type ?? "Pending validation"}</dd></div><div><dt>Declared type</dt><dd>{document.declared_mime_type}</dd></div><div><dt>Validated size</dt><dd>{formatBytes(document.size_bytes)}</dd></div><div><dt>Declared size</dt><dd>{formatBytes(document.declared_size)}</dd></div><div><dt>SHA-256</dt><dd title={document.content_sha256 ?? undefined}>{shortHash(document.content_sha256)}</dd></div></dl></section>
        <section className="document-metadata"><header><small>Provenance</small><h2>Source record</h2></header><dl><div><dt>Linked project</dt><dd>{project ? <Link href={`/projects/${project.id}`}>{project.name}</Link> : "Workspace document"}</dd></div><div><dt>Created via</dt><dd>{document.created_via.toUpperCase()}</dd></div><div><dt>Created</dt><dd>{formatDocumentDate(document.created_at)}</dd></div><div><dt>Last updated</dt><dd>{formatDocumentDate(document.updated_at)}</dd></div><div><dt>Record version</dt><dd>v{document.version}</dd></div><div><dt>Document ID</dt><dd>#{document.id}</dd></div></dl></section>
      </div>
      <IngestionPanel document={document} project={project} />
    </main>
  );
}
