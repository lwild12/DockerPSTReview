import { apiFetch } from "./client";
import type { TagRead } from "./tags";

export type DocType = "email" | "attachment" | "calendar" | "contact";
export type DedupStatus = "primary" | "duplicate";
export type OcrStatus = "not_applicable" | "completed" | "failed";

export interface DocumentListItem {
  id: string;
  doc_type: DocType;
  subject: string;
  sender: string;
  sent_at: string | null;
  custodian_id: string | null;
  thread_id: string | null;
  parent_document_id: string | null;
  dedup_status: DedupStatus;
  rendered_pdf_page_count: number;
  render_error: string;
  ocr_status: OcrStatus;
  tags: TagRead[];
}

export interface DocumentDetail extends DocumentListItem {
  case_id: string;
  import_job_id: string | null;
  recipients_to: string[];
  recipients_cc: string[];
  recipients_bcc: string[];
  message_id: string;
  in_reply_to: string;
  references: string[];
  body_text: string;
  body_html: string;
  structured_metadata: Record<string, unknown>;
  pst_folder_path: string;
  mime_type: string;
  file_size: number;
  content_hash: string;
  duplicate_of_id: string | null;
  created_at: string;
  ocr_text: string;
  ocr_error: string;
}

export interface ThreadSibling {
  id: string;
  subject: string;
  sender: string;
  sent_at: string | null;
}

export interface DocumentFilters {
  doc_type?: DocType;
  custodian_id?: string;
  dedup_status?: DedupStatus;
  thread_id?: string;
  tag_id?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export async function listDocuments(
  caseId: string,
  filters: DocumentFilters = {},
): Promise<DocumentListItem[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return apiFetch<DocumentListItem[]>(`/cases/${caseId}/documents${query ? `?${query}` : ""}`);
}

export async function getDocument(caseId: string, documentId: string): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/cases/${caseId}/documents/${documentId}`);
}

export function documentPdfUrl(caseId: string, documentId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api";
  return `${base}/cases/${caseId}/documents/${documentId}/pdf`;
}

export async function listThreadDocuments(
  caseId: string,
  threadId: string,
): Promise<ThreadSibling[]> {
  return apiFetch<ThreadSibling[]>(`/cases/${caseId}/threads/${threadId}/documents`);
}
