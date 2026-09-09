import { API_BASE, apiFetch } from "./client";

export type ExportType = "production_set" | "combined_pdf";
export type ExportStatus = "pending" | "running" | "completed" | "failed";

export interface ExportJob {
  id: string;
  case_id: string;
  review_set_id: string | null;
  production_number: number;
  export_type: ExportType;
  apply_bates: boolean;
  bates_prefix: string;
  bates_start_number: number;
  bates_digit_padding: number;
  bates_end_number: number | null;
  document_ids: string[];
  status: ExportStatus;
  output_storage_path: string;
  requested_by_id: string;
  created_at: string;
  completed_at: string | null;
  error_message: string;
}

export interface ExportJobCreate {
  review_set_id?: string;
  document_ids?: string[];
  export_type: ExportType;
  apply_bates: boolean;
  bates_prefix?: string;
  bates_start_number?: number;
  bates_digit_padding?: number;
}

export async function listExportJobs(caseId: string): Promise<ExportJob[]> {
  return apiFetch<ExportJob[]>(`/cases/${caseId}/export-jobs`);
}

export async function createExportJob(
  caseId: string,
  payload: ExportJobCreate,
): Promise<ExportJob> {
  return apiFetch<ExportJob>(`/cases/${caseId}/export-jobs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getExportJob(caseId: string, jobId: string): Promise<ExportJob> {
  return apiFetch<ExportJob>(`/cases/${caseId}/export-jobs/${jobId}`);
}

export function exportJobDownloadUrl(caseId: string, jobId: string): string {
  return `${API_BASE}/cases/${caseId}/export-jobs/${jobId}/download`;
}

export async function getNextBatesNumber(caseId: string, prefix: string): Promise<number> {
  const body = await apiFetch<{ next_bates_number: number }>(
    `/cases/${caseId}/export-jobs/next-bates-number?prefix=${encodeURIComponent(prefix)}`,
  );
  return body.next_bates_number;
}

export function batesLabel(prefix: string, number: number, padding: number): string {
  return `${prefix}${String(number).padStart(padding, "0")}`;
}

export const EXPORT_TERMINAL_STATUSES: ExportStatus[] = ["completed", "failed"];
