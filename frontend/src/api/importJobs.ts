const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export type ImportStatus =
  | "pending"
  | "extracting"
  | "parsing"
  | "dedup"
  | "rendering"
  | "completed"
  | "completed_with_errors"
  | "failed";

export interface ImportJob {
  id: string;
  case_id: string;
  custodian_id: string;
  uploaded_filename: string;
  status: ImportStatus;
  error_message: string;
  stats: Record<string, number | boolean | undefined>;
  created_by_id: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
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

export async function listImportJobs(caseId: string): Promise<ImportJob[]> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/import-jobs`, { credentials: "include" });
  return handle<ImportJob[]>(res);
}

export async function getImportJob(caseId: string, jobId: string): Promise<ImportJob> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/import-jobs/${jobId}`, {
    credentials: "include",
  });
  return handle<ImportJob>(res);
}

export async function createImportJob(
  caseId: string,
  custodianId: string,
  file: File,
): Promise<ImportJob> {
  const formData = new FormData();
  formData.append("custodian_id", custodianId);
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/cases/${caseId}/import-jobs`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  return handle<ImportJob>(res);
}

export const TERMINAL_STATUSES: ImportStatus[] = ["completed", "completed_with_errors", "failed"];
