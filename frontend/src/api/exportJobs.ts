const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

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

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return (await res.json()) as T;
}

export async function listExportJobs(caseId: string): Promise<ExportJob[]> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/export-jobs`, { credentials: "include" });
  return handle<ExportJob[]>(res);
}

export async function createExportJob(
  caseId: string,
  payload: ExportJobCreate,
): Promise<ExportJob> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/export-jobs`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle<ExportJob>(res);
}

export async function getExportJob(caseId: string, jobId: string): Promise<ExportJob> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/export-jobs/${jobId}`, {
    credentials: "include",
  });
  return handle<ExportJob>(res);
}

export function exportJobDownloadUrl(caseId: string, jobId: string): string {
  return `${API_BASE}/cases/${caseId}/export-jobs/${jobId}/download`;
}

export async function getNextBatesNumber(caseId: string, prefix: string): Promise<number> {
  const res = await fetch(
    `${API_BASE}/cases/${caseId}/export-jobs/next-bates-number?prefix=${encodeURIComponent(prefix)}`,
    { credentials: "include" },
  );
  const body = await handle<{ next_bates_number: number }>(res);
  return body.next_bates_number;
}

export function batesLabel(prefix: string, number: number, padding: number): string {
  return `${prefix}${String(number).padStart(padding, "0")}`;
}

export const EXPORT_TERMINAL_STATUSES: ExportStatus[] = ["completed", "failed"];
