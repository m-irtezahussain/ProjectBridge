import type { IngestionRun, IngestionStatus, StageStatus, TaskCandidate } from "@/services/ingestion-api";

export const ingestionStages = [
  { key: "ocr_status", label: "OCR" },
  { key: "extraction_status", label: "Extract" },
  { key: "task_status", label: "Tasks" },
  { key: "indexing_status", label: "Index" },
] as const satisfies ReadonlyArray<{
  key: "ocr_status" | "extraction_status" | "task_status" | "indexing_status";
  label: string;
}>;

export type CandidateDecision = "approved" | "rejected";
export type CandidateDecisions = Readonly<Record<number, CandidateDecision>>;

export function ingestionStatusLabel(status: IngestionStatus): string {
  return {
    queued: "Queued",
    processing: "Processing",
    awaiting_confirmation: "Awaiting review",
    retry_scheduled: "Retry scheduled",
    completed: "Completed",
    partial_failure: "Partially completed",
    failed: "Failed",
  }[status];
}

export function stageStatusLabel(status: StageStatus): string {
  return {
    pending: "Pending",
    running: "Running",
    completed: "Complete",
    failed: "Failed",
    skipped: "Skipped",
  }[status];
}

export function ingestionProgress(run: IngestionRun): number {
  const weights: Record<StageStatus, number> = {
    pending: 0,
    running: 0.5,
    completed: 1,
    failed: 1,
    skipped: 1,
  };
  const total = ingestionStages.reduce((sum, stage) => sum + weights[run[stage.key]], 0);
  return Math.round((total / ingestionStages.length) * 100);
}

export function shouldPollIngestion(status: IngestionStatus): boolean {
  return status === "queued" || status === "processing" || status === "retry_scheduled";
}

export function canRetryIngestion(run: IngestionRun): boolean {
  return (run.status === "failed" || run.status === "partial_failure")
    && run.attempts < run.max_attempts;
}

export function initialCandidateDecisions(candidates: readonly TaskCandidate[]): CandidateDecisions {
  const decisions: Record<number, CandidateDecision> = {};
  for (const candidate of candidates) {
    if (candidate.status === "approved" || candidate.status === "created") {
      decisions[candidate.id] = "approved";
    } else if (candidate.status === "rejected") {
      decisions[candidate.id] = "rejected";
    }
  }
  return decisions;
}

export function candidateDecisionPayload(
  candidates: readonly TaskCandidate[],
  decisions: CandidateDecisions,
): Readonly<{ approved: number[]; rejected: number[]; complete: boolean }> {
  const approved: number[] = [];
  const rejected: number[] = [];
  for (const candidate of candidates) {
    if (decisions[candidate.id] === "approved") approved.push(candidate.id);
    if (decisions[candidate.id] === "rejected") rejected.push(candidate.id);
  }
  return { approved, rejected, complete: approved.length + rejected.length === candidates.length };
}
