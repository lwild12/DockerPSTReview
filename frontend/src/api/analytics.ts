import { apiFetch } from "./client";
import type { DocumentListItem } from "./documents";

export interface CaseAnalyticsSummary {
  computed_at: string | null;
  near_duplicate_cluster_count: number;
  non_inclusive_email_count: number;
}

export interface NearDuplicateCluster {
  id: string;
  member_count: number;
}

export async function getCaseAnalytics(caseId: string): Promise<CaseAnalyticsSummary> {
  return apiFetch<CaseAnalyticsSummary>(`/cases/${caseId}/analytics`);
}

export async function recomputeCaseAnalytics(caseId: string): Promise<CaseAnalyticsSummary> {
  return apiFetch<CaseAnalyticsSummary>(`/cases/${caseId}/analytics/recompute`, {
    method: "POST",
  });
}

export async function listNearDuplicateClusters(caseId: string): Promise<NearDuplicateCluster[]> {
  return apiFetch<NearDuplicateCluster[]>(`/cases/${caseId}/near-duplicate-clusters`);
}

export async function listNearDuplicateClusterDocuments(
  caseId: string,
  clusterId: string,
): Promise<DocumentListItem[]> {
  return apiFetch<DocumentListItem[]>(
    `/cases/${caseId}/near-duplicate-clusters/${clusterId}/documents`,
  );
}
