import { apiFetch } from "./client";

export interface TagRead {
  id: string;
  case_id: string;
  name: string;
  color: string;
  created_by_id: string;
  created_at: string;
}

export async function listTags(caseId: string): Promise<TagRead[]> {
  return apiFetch<TagRead[]>(`/cases/${caseId}/tags`);
}

export async function createTag(caseId: string, name: string, color?: string): Promise<TagRead> {
  return apiFetch<TagRead>(`/cases/${caseId}/tags`, {
    method: "POST",
    body: JSON.stringify({ name, ...(color ? { color } : {}) }),
  });
}

export async function deleteTag(caseId: string, tagId: string): Promise<void> {
  await apiFetch<void>(`/cases/${caseId}/tags/${tagId}`, { method: "DELETE" });
}

export async function applyTag(
  caseId: string,
  documentId: string,
  tagId: string,
): Promise<TagRead> {
  return apiFetch<TagRead>(`/cases/${caseId}/documents/${documentId}/tags/${tagId}`, {
    method: "POST",
  });
}

export async function removeTag(
  caseId: string,
  documentId: string,
  tagId: string,
): Promise<void> {
  await apiFetch<void>(`/cases/${caseId}/documents/${documentId}/tags/${tagId}`, {
    method: "DELETE",
  });
}

export async function applyTagBulk(
  caseId: string,
  tagId: string,
  documentIds: string[],
): Promise<{ tagged_count: number }> {
  return apiFetch<{ tagged_count: number }>(`/cases/${caseId}/tags/${tagId}/apply-bulk`, {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
}
