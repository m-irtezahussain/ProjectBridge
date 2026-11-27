"use client";

import { useRef, useState, type FormEvent } from "react";

import { Icon } from "@/components/ui/icon";
import type { ProjectRecord } from "@/services/projects-api";
import {
  finalizeDocumentUpload,
  initiateDocumentUpload,
  type DocumentSummary,
  uploadDocumentFile,
} from "@/services/documents-api";
import {
  ACCEPTED_DOCUMENT_TYPES,
  formatBytes,
  validateDocumentFile,
} from "./document-data";

type UploadPhase = "ready" | "initiating" | "uploading" | "finalizing";

type UploadDialogProps = Readonly<{
  projects: readonly ProjectRecord[];
  onClose: () => void;
  onUploaded: (document: DocumentSummary) => void;
}>;

const phaseCopy: Record<UploadPhase, string> = {
  ready: "Ready to upload",
  initiating: "Securing upload target…",
  uploading: "Uploading original file…",
  finalizing: "Validating and preserving source…",
};

export function UploadDialog({ projects, onClose, onUploaded }: UploadDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState<number | "">("");
  const [phase, setPhase] = useState<UploadPhase>("ready");
  const [error, setError] = useState("");
  const busy = phase !== "ready";

  function selectFile(nextFile: File | undefined) {
    if (!nextFile) return;
    const validationError = validateDocumentFile(nextFile);
    setError(validationError ?? "");
    setFile(validationError ? null : nextFile);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || busy) return;
    setError("");
    try {
      setPhase("initiating");
      const target = await initiateDocumentUpload({
        filename: file.name,
        mime_type: file.type as "application/pdf" | "image/jpeg" | "image/png",
        size_bytes: file.size,
        project_id: projectId || null,
      });
      setPhase("uploading");
      await uploadDocumentFile(target.upload, file);
      setPhase("finalizing");
      const finalized = await finalizeDocumentUpload(target.document.id);
      onUploaded(finalized.document);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "The document could not be uploaded.");
      setPhase("ready");
    }
  }

  const progress = { ready: 0, initiating: 18, uploading: 55, finalizing: 86 }[phase];

  return (
    <div className="document-dialog-layer">
      <button className="document-dialog-backdrop" type="button" aria-label="Close upload dialog" onClick={busy ? undefined : onClose} />
      <section className="document-upload-dialog" role="dialog" aria-modal="true" aria-labelledby="document-upload-title">
        <header><div><small>Immutable source</small><h2 id="document-upload-title">Upload a document</h2></div><button type="button" onClick={onClose} disabled={busy} aria-label="Close">×</button></header>
        <form onSubmit={(event) => void submit(event)}>
          <label className={`document-dropzone${file ? " has-file" : ""}${busy ? " is-disabled" : ""}`}>
            <input ref={inputRef} type="file" accept={ACCEPTED_DOCUMENT_TYPES.join(",")} onChange={(event) => selectFile(event.target.files?.[0])} disabled={busy} />
            <Icon name="document" />
            {file ? <><strong>{file.name}</strong><span>{formatBytes(file.size)} · {file.type}</span></> : <><strong>Choose the original file</strong><span>PDF, PNG, or JPEG · up to 25 MB</span></>}
          </label>
          <label><span>Link to project <small>optional</small></span><select value={projectId} onChange={(event) => setProjectId(event.target.value ? Number(event.target.value) : "")} disabled={busy}><option value="">Workspace document</option>{projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label>
          {busy && <div className="document-upload-progress" role="status"><span><i style={{ width: `${progress}%` }} /></span><strong>{phaseCopy[phase]}</strong><small>Keep this window open until validation begins.</small></div>}
          {error && <p className="document-form-error" role="alert">{error}</p>}
          <footer><button type="button" onClick={onClose} disabled={busy}>Cancel</button><button className="primary" type="submit" disabled={!file || busy}>{busy ? phaseCopy[phase] : "Upload securely"}</button></footer>
        </form>
      </section>
    </div>
  );
}
