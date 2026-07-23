import { apiFetch } from "./client";

export interface AuditLog {
  id: string;
  case_id: string;
  user_id: string | null;
  user_email: string | null;
  action: string;
  target_type: string;
  target_id: string;
  audit_metadata: Record<string, unknown>;
  created_at: string;
}

export async function listAuditLogs(caseId: string, page = 1): Promise<AuditLog[]> {
  return apiFetch<AuditLog[]>(`/cases/${caseId}/audit-logs?page=${page}`);
}
