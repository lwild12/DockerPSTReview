import { apiFetch } from "./client";

export type CaseRole = "admin" | "reviewer" | "viewer";

export interface Case {
  id: string;
  name: string;
  description: string;
  created_by_id: string;
  created_at: string;
  my_role: CaseRole | null;
}

export interface CaseMember {
  id: string;
  user_id: string;
  role: CaseRole;
}

export interface Custodian {
  id: string;
  name: string;
  email: string;
}

export async function listCases(): Promise<Case[]> {
  return apiFetch<Case[]>("/cases");
}

export async function createCase(name: string, description: string): Promise<Case> {
  return apiFetch<Case>("/cases", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function getCase(caseId: string): Promise<Case> {
  return apiFetch<Case>(`/cases/${caseId}`);
}

export async function listMembers(caseId: string): Promise<CaseMember[]> {
  return apiFetch<CaseMember[]>(`/cases/${caseId}/members`);
}

export async function addMember(
  caseId: string,
  userId: string,
  role: CaseRole,
): Promise<CaseMember> {
  return apiFetch<CaseMember>(`/cases/${caseId}/members`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
}

export async function listCustodians(caseId: string): Promise<Custodian[]> {
  return apiFetch<Custodian[]>(`/cases/${caseId}/custodians`);
}

export async function createCustodian(
  caseId: string,
  name: string,
  email: string,
): Promise<Custodian> {
  return apiFetch<Custodian>(`/cases/${caseId}/custodians`, {
    method: "POST",
    body: JSON.stringify({ name, email }),
  });
}
