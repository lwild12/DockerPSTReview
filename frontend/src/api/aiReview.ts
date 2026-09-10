import { apiFetch } from "./client";
import type { DocumentAiRelevance } from "./documents";

export interface AiReviewSummary {
  criteria: string;
  ollama_configured: boolean;
  last_run_started_at: string | null;
  last_run_completed_at: string | null;
  candidate_count: number;
  unscored_count: number;
  queued_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
}

export async function getAiReviewSummary(
  caseId: string,
): Promise<AiReviewSummary> {
  return apiFetch<AiReviewSummary>(`/cases/${caseId}/ai-review`);
}

export async function updateAiReviewCriteria(
  caseId: string,
  criteria: string,
): Promise<AiReviewSummary> {
  return apiFetch<AiReviewSummary>(`/cases/${caseId}/ai-review/criteria`, {
    method: "PATCH",
    body: JSON.stringify({ criteria }),
  });
}

export async function runAiReview(
  caseId: string,
  rescoreAll: boolean = false,
): Promise<AiReviewSummary> {
  return apiFetch<AiReviewSummary>(`/cases/${caseId}/ai-review/run`, {
    method: "POST",
    body: JSON.stringify({ rescore_all: rescoreAll }),
  });
}

export async function runAiReviewForDocument(
  caseId: string,
  documentId: string,
): Promise<DocumentAiRelevance> {
  return apiFetch<DocumentAiRelevance>(
    `/cases/${caseId}/ai-review/documents/${documentId}/run`,
    { method: "POST" },
  );
}
