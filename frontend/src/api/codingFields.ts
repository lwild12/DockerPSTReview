import { apiFetch } from "./client";

export type CodingFieldType = "single_select" | "multi_select";

export interface CodingFieldRead {
  id: string;
  case_id: string;
  name: string;
  field_type: CodingFieldType;
  options: string[];
  created_by_id: string;
  created_at: string;
}

export interface DocumentCodingValueRead {
  id: string;
  document_id: string;
  coding_field_id: string;
  value: string;
  set_by_id: string;
  set_at: string;
}

export async function listCodingFields(caseId: string): Promise<CodingFieldRead[]> {
  return apiFetch<CodingFieldRead[]>(`/cases/${caseId}/coding-fields`);
}

export async function createCodingField(
  caseId: string,
  name: string,
  fieldType: CodingFieldType,
  options: string[],
): Promise<CodingFieldRead> {
  return apiFetch<CodingFieldRead>(`/cases/${caseId}/coding-fields`, {
    method: "POST",
    body: JSON.stringify({ name, field_type: fieldType, options }),
  });
}

export async function updateCodingField(
  caseId: string,
  fieldId: string,
  payload: { name?: string; options?: string[] },
): Promise<CodingFieldRead> {
  return apiFetch<CodingFieldRead>(`/cases/${caseId}/coding-fields/${fieldId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteCodingField(caseId: string, fieldId: string): Promise<void> {
  await apiFetch<void>(`/cases/${caseId}/coding-fields/${fieldId}`, { method: "DELETE" });
}

export async function listDocumentCodingValues(
  caseId: string,
  documentId: string,
): Promise<DocumentCodingValueRead[]> {
  return apiFetch<DocumentCodingValueRead[]>(
    `/cases/${caseId}/documents/${documentId}/coding-values`,
  );
}

export async function setDocumentCodingValue(
  caseId: string,
  documentId: string,
  fieldId: string,
  values: string[],
): Promise<DocumentCodingValueRead[]> {
  return apiFetch<DocumentCodingValueRead[]>(
    `/cases/${caseId}/documents/${documentId}/coding-values/${fieldId}`,
    { method: "PUT", body: JSON.stringify({ values }) },
  );
}
