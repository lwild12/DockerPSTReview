import { apiFetch } from "./client";

export interface Redaction {
  id: string;
  document_id: string;
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  reason: string;
  color: string;
  created_by_id: string;
  created_at: string;
}

export interface RedactionCreate {
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  reason?: string;
  color?: string;
}

export async function listRedactions(caseId: string, documentId: string): Promise<Redaction[]> {
  return apiFetch<Redaction[]>(`/cases/${caseId}/documents/${documentId}/redactions`);
}

export async function createRedaction(
  caseId: string,
  documentId: string,
  redaction: RedactionCreate,
): Promise<Redaction> {
  return apiFetch<Redaction>(`/cases/${caseId}/documents/${documentId}/redactions`, {
    method: "POST",
    body: JSON.stringify(redaction),
  });
}

export async function deleteRedaction(
  caseId: string,
  documentId: string,
  redactionId: string,
): Promise<void> {
  await apiFetch<void>(`/cases/${caseId}/documents/${documentId}/redactions/${redactionId}`, {
    method: "DELETE",
  });
}
