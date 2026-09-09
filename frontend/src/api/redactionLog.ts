import { API_BASE, apiFetch } from "./client";

export interface RedactionLogEntry {
  id: string;
  document_id: string;
  document_subject: string;
  document_sender: string;
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  reason: string;
  color: string;
  created_by_id: string;
  created_by_email: string | null;
  created_at: string;
}

export async function listCaseRedactionLog(caseId: string): Promise<RedactionLogEntry[]> {
  return apiFetch<RedactionLogEntry[]>(`/cases/${caseId}/redactions`);
}

export function redactionLogCsvUrl(caseId: string): string {
  return `${API_BASE}/cases/${caseId}/redactions/export.csv`;
}
