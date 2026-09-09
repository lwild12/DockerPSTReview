import { apiFetch } from "./client";

export type ImportStatus =
  | "pending"
  | "extracting"
  | "parsing"
  | "dedup"
  | "rendering"
  | "completed"
  | "completed_with_errors"
  | "failed";

export interface ParseErrorDetail {
  doc_type: string;
  folder_path: string;
  error: string;
}

export interface ImportJobStats {
  fallback_used?: boolean;
  total_items?: number;
  parse_errors?: number;
  parse_error_details?: ParseErrorDetail[];
  emails?: number;
  attachments?: number;
  contacts?: number;
  calendar_items?: number;
  duplicates?: number;
  render_failures?: number;
}

export interface ImportJob {
  id: string;
  case_id: string;
  custodian_id: string;
  uploaded_filename: string;
  status: ImportStatus;
  error_message: string;
  stats: ImportJobStats;
  created_by_id: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  documents_total: number;
  documents_rendered: number;
  documents_render_failed: number;
}

export interface FailedDocumentSummary {
  id: string;
  doc_type: string;
  subject: string;
  render_error: string;
  ocr_status: string;
  ocr_error: string;
}

export async function listImportJobs(caseId: string): Promise<ImportJob[]> {
  return apiFetch<ImportJob[]>(`/cases/${caseId}/import-jobs`);
}

export async function getImportJob(caseId: string, jobId: string): Promise<ImportJob> {
  return apiFetch<ImportJob>(`/cases/${caseId}/import-jobs/${jobId}`);
}

export async function createImportJob(
  caseId: string,
  custodianId: string,
  file: File,
): Promise<ImportJob> {
  const formData = new FormData();
  formData.append("custodian_id", custodianId);
  formData.append("file", file);
  return apiFetch<ImportJob>(`/cases/${caseId}/import-jobs`, {
    method: "POST",
    body: formData,
  });
}

export async function listFailedDocuments(
  caseId: string,
  jobId: string,
): Promise<FailedDocumentSummary[]> {
  return apiFetch<FailedDocumentSummary[]>(`/cases/${caseId}/import-jobs/${jobId}/failed-documents`);
}

export const TERMINAL_STATUSES: ImportStatus[] = ["completed", "completed_with_errors", "failed"];
