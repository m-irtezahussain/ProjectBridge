"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { Icon } from "@/components/ui/icon";
import { VersionConflictError } from "@/services/api-client";
import type { DocumentSummary } from "@/services/documents-api";
import {
  confirmTaskCandidates,
  getDocumentIngestion,
  getDocumentIngestionForDocument,
  listTaskCandidates,
  retryDocumentIngestion,
  startDocumentIngestion,
  type IngestionRun,
  type TaskCandidate,
} from "@/services/ingestion-api";
import type { ProjectRecord } from "@/services/projects-api";
import {
  candidateDecisionPayload,
  canRetryIngestion,
  ingestionProgress,
  ingestionStages,
  ingestionStatusLabel,
  initialCandidateDecisions,
  shouldPollIngestion,
  stageStatusLabel,
  type CandidateDecision,
  type CandidateDecisions,
} from "./ingestion-data";

type IngestionPanelProps = Readonly<{
  document: DocumentSummary;
  project: ProjectRecord | null;
}>;

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : "The ingestion request could not be completed.";
}

export function IngestionPanel({ document, project }: IngestionPanelProps) {
  const [run, setRun] = useState<IngestionRun | null>(null);
  const [candidates, setCandidates] = useState<TaskCandidate[]>([]);
  const [decisions, setDecisions] = useState<CandidateDecisions>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  const loadCandidates = useCallback(async (runId: number) => {
    const result = await listTaskCandidates(runId);
    setRun(result.ingestion);
    setCandidates([...result.candidates]);
    setDecisions(initialCandidateDecisions(result.candidates));
  }, []);

  const refreshRun = useCallback(async (runId: number, includeCandidates = false) => {
    if (includeCandidates) {
      await loadCandidates(runId);
      return;
    }
    const updated = await getDocumentIngestion(runId);
    setRun(updated);
    if (["awaiting_confirmation", "completed", "partial_failure", "failed"].includes(updated.status)) {
      await loadCandidates(runId);
    }
  }, [loadCandidates]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void getDocumentIngestionForDocument(document.id)
        .then(async (existing) => {
          if (!active) return;
          setRun(existing);
          if (existing && ["awaiting_confirmation", "completed", "partial_failure", "failed"].includes(existing.status)) {
            await loadCandidates(existing.id);
          }
        })
        .catch((loadError: unknown) => { if (active) setError(messageFor(loadError)); })
        .finally(() => { if (active) setLoading(false); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [document.id, loadCandidates]);

  useEffect(() => {
    if (!run || !shouldPollIngestion(run.status)) return;
    const timer = window.setInterval(() => void refreshRun(run.id).catch((pollError: unknown) => setError(messageFor(pollError))), 2500);
    return () => window.clearInterval(timer);
  }, [refreshRun, run]);

  const review = useMemo(
    () => candidateDecisionPayload(candidates, decisions),
    [candidates, decisions],
  );
  const createdCount = candidates.filter((candidate) => candidate.status === "created").length;
  const rejectedCount = candidates.filter((candidate) => candidate.status === "rejected").length;

  function runAction(action: () => Promise<IngestionRun>) {
    setError("");
    startTransition(async () => {
      try {
        const updated = await action();
        startTransition(() => setRun(updated));
        await refreshRun(updated.id);
      } catch (actionError) {
        if (actionError instanceof VersionConflictError && run) await refreshRun(run.id, true);
        setError(messageFor(actionError));
      }
    });
  }

  function start() {
    if (!project) return;
    runAction(() => startDocumentIngestion({
      document_id: document.id,
      project_id: project.id,
      idempotency_key: crypto.randomUUID(),
    }));
  }

  function retry() {
    if (!run) return;
    runAction(() => retryDocumentIngestion(run.id, run.version, crypto.randomUUID()));
  }

  function confirm() {
    if (!run || !review.complete) return;
    runAction(() => confirmTaskCandidates(run.id, {
      approved_candidate_ids: review.approved,
      rejected_candidate_ids: review.rejected,
      expected_version: run.version,
      idempotency_key: crypto.randomUUID(),
    }));
  }

  function decide(candidateId: number, decision: CandidateDecision) {
    setDecisions((current) => ({ ...current, [candidateId]: decision }));
  }

  const sourceReady = document.status === "available" || document.status === "duplicate";

  return (
    <section className="ingestion-panel" aria-labelledby="ingestion-title">
      <header className="ingestion-panel__heading"><div><small>Controlled automation</small><h2 id="ingestion-title">OCR ingestion</h2><p>Extract task proposals from the source. OCR text is untrusted and cannot create tasks until you review every candidate.</p></div>{run && <span className={`ingestion-run-status ingestion-run-status--${run.status}`}><i />{ingestionStatusLabel(run.status)}</span>}</header>

      {error && <div className="ingestion-error" role="alert"><Icon name="document" /><span>{error}</span></div>}

      {loading ? <div className="ingestion-loading"><i /><i /><i /><i /></div> : !run ? (
        <div className="ingestion-start"><div><Icon name="spark" /><span><strong>Ready to extract safely</strong><small>{project ? `Tasks will be linked to ${project.name}.` : "Link this source to a project before starting ingestion."}</small></span></div><button type="button" onClick={start} disabled={!sourceReady || !project || isPending}>{isPending ? "Starting…" : "Start ingestion"}</button></div>
      ) : (
        <>
          <div className="ingestion-overview"><div><span>Run #{run.id}</span><strong>{ingestionProgress(run)}%</strong></div><span className="ingestion-overview__track"><i style={{ width: `${ingestionProgress(run)}%` }} /></span><small>Attempt {run.attempts} of {run.max_attempts}{run.next_attempt_at ? ` · next worker check ${new Date(run.next_attempt_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}</small></div>
          <div className="ingestion-stages">{ingestionStages.map((stage) => <article className={`ingestion-stage ingestion-stage--${run[stage.key]}`} key={stage.key}><span>{stage.label}</span><i><Icon name={run[stage.key] === "completed" ? "check" : stage.key === "ocr_status" ? "document" : stage.key === "indexing_status" ? "search" : "spark"} /></i><strong>{stageStatusLabel(run[stage.key])}</strong></article>)}</div>

          {(run.last_error_message || run.status === "partial_failure" || run.status === "failed") && <div className="ingestion-recovery"><div><strong>{run.status === "partial_failure" ? "Some durable stages completed" : "Ingestion needs attention"}</strong><p>{run.last_error_message ?? "Resume from the last durable checkpoint without duplicating OCR text, candidates, or tasks."}</p>{run.last_error_code && <code>{run.last_error_code}</code>}</div>{canRetryIngestion(run) && <button type="button" onClick={retry} disabled={isPending}>{isPending ? "Retrying…" : "Retry from checkpoint"}</button>}</div>}

          {candidates.length > 0 && <section className="candidate-review"><header><div><small>Untrusted OCR proposals</small><h3>{run.status === "awaiting_confirmation" ? "Review every candidate" : "Task creation results"}</h3></div><span>{run.status === "awaiting_confirmation" ? `${Object.keys(decisions).length} / ${candidates.length} decided` : `${createdCount} created · ${rejectedCount} rejected`}</span></header><div className="candidate-list">{candidates.map((candidate) => <article className={`candidate-card candidate-card--${candidate.status}`} key={candidate.id}><header><div><span>Candidate #{candidate.id}</span>{candidate.confidence !== null && <small>{Math.round(candidate.confidence * 100)}% confidence</small>}</div><strong>{candidate.title}</strong>{candidate.description && <p>{candidate.description}</p>}</header><blockquote>{candidate.source_excerpt}</blockquote><footer><span>{candidate.page_number ? `Page ${candidate.page_number}` : "Source location unavailable"} · {candidate.extractor} {candidate.extractor_version}</span>{run.status === "awaiting_confirmation" && candidate.status === "pending" ? <div><button className={decisions[candidate.id] === "approved" ? "active approve" : "approve"} type="button" onClick={() => decide(candidate.id, "approved")}>Approve</button><button className={decisions[candidate.id] === "rejected" ? "active reject" : "reject"} type="button" onClick={() => decide(candidate.id, "rejected")}>Reject</button></div> : candidate.created_task_id ? <Link href={`/projects/${run.project_id}`}>Task #{candidate.created_task_id} created <Icon name="arrow" /></Link> : <em>{candidate.status}</em>}</footer>{candidate.failure_message && <p className="candidate-failure">{candidate.failure_message}</p>}</article>)}</div>{run.status === "awaiting_confirmation" && <footer><p>{review.complete ? `${review.approved.length} approved and ${review.rejected.length} rejected.` : "Every candidate needs an explicit decision."}</p><button type="button" onClick={confirm} disabled={!review.complete || isPending}>{isPending ? "Confirming…" : "Confirm decisions"}</button></footer>}</section>}

          {run.status === "awaiting_confirmation" && candidates.length === 0 && <div className="ingestion-empty"><Icon name="check" /><div><strong>No task candidates found</strong><p>The source contained no explicitly marked TODO, TASK, or ACTION lines. Confirm the empty review to finish ingestion.</p></div><button type="button" onClick={confirm} disabled={isPending}>{isPending ? "Confirming…" : "Confirm empty review"}</button></div>}
        </>
      )}
    </section>
  );
}
