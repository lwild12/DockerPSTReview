// A document viewer link, carrying the active review set along (if any) so
// Previous/Next navigation and the "back to review set" link keep working.
export function documentLink(caseId: string, documentId: string, reviewSetId?: string): string {
  return reviewSetId
    ? `/cases/${caseId}/documents/${documentId}?reviewSet=${reviewSetId}`
    : `/cases/${caseId}/documents/${documentId}`;
}
