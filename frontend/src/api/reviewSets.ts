import { apiFetch } from "./client";

export type ReviewStatus = "unreviewed" | "in_review" | "reviewed" | "flagged";

export interface ReviewSet {
  id: string;
  case_id: string;
  name: string;
  description: string;
  created_by_id: string;
  created_at: string;
}

export interface ReviewSetDocument {
  id: string;
  review_set_id: string;
  document_id: string;
  review_status: ReviewStatus;
  assigned_reviewer_id: string | null;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  notes: string;
  document_subject: string;
  document_sender: string;
  document_doc_type: string;
  document_sent_at: string | null;
}

export async function listReviewSets(caseId: string): Promise<ReviewSet[]> {
  return apiFetch<ReviewSet[]>(`/cases/${caseId}/review-sets`);
}

export async function createReviewSet(
  caseId: string,
  name: string,
  description = "",
): Promise<ReviewSet> {
  return apiFetch<ReviewSet>(`/cases/${caseId}/review-sets`, {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function getReviewSet(caseId: string, reviewSetId: string): Promise<ReviewSet> {
  return apiFetch<ReviewSet>(`/cases/${caseId}/review-sets/${reviewSetId}`);
}

export async function listReviewSetDocuments(
  caseId: string,
  reviewSetId: string,
): Promise<ReviewSetDocument[]> {
  return apiFetch<ReviewSetDocument[]>(`/cases/${caseId}/review-sets/${reviewSetId}/documents`);
}

export async function addDocumentsToReviewSet(
  caseId: string,
  reviewSetId: string,
  documentIds: string[],
): Promise<ReviewSetDocument[]> {
  return apiFetch<ReviewSetDocument[]>(`/cases/${caseId}/review-sets/${reviewSetId}/documents`, {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

export async function updateReviewSetDocument(
  caseId: string,
  reviewSetId: string,
  documentId: string,
  update: { review_status?: ReviewStatus; assigned_reviewer_id?: string; notes?: string },
): Promise<ReviewSetDocument> {
  return apiFetch<ReviewSetDocument>(
    `/cases/${caseId}/review-sets/${reviewSetId}/documents/${documentId}`,
    { method: "PATCH", body: JSON.stringify(update) },
  );
}
