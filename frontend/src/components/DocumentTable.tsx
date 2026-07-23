import { Badge, Checkbox, Table, Text } from "@mantine/core";
import { IconPaperclip } from "@tabler/icons-react";
import { useNavigate, useParams } from "react-router-dom";

import type { DocumentListItem } from "../api/documents";
import { childrenByParent, groupIntoFamilies } from "../lib/documentFamilies";

const DEDUP_COLOR: Record<string, string> = { primary: "gray", duplicate: "orange" };

const getId = (d: DocumentListItem) => d.id;
const getParentId = (d: DocumentListItem) => d.parent_document_id;

export function DocumentTable({
  documents,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onToggleFamily,
}: {
  documents: DocumentListItem[];
  selectedIds: Set<string>;
  onToggleSelect: (documentId: string) => void;
  onToggleSelectAll?: (checked: boolean) => void;
  onToggleFamily?: (parentId: string, childIds: string[]) => void;
}) {
  const navigate = useNavigate();
  const { caseId } = useParams<{ caseId: string }>();

  const allSelected = documents.length > 0 && documents.every((d) => selectedIds.has(d.id));
  const someSelected = documents.some((d) => selectedIds.has(d.id));
  const rows = groupIntoFamilies(documents, getId, getParentId);
  const children = childrenByParent(documents, getParentId);

  return (
    <Table striped highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={36}>
            {onToggleSelectAll && (
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected && !allSelected}
                onChange={(e) => onToggleSelectAll(e.currentTarget.checked)}
              />
            )}
          </Table.Th>
          <Table.Th>Subject</Table.Th>
          <Table.Th>From</Table.Th>
          <Table.Th>Sent</Table.Th>
          <Table.Th>Type</Table.Th>
          <Table.Th>Status</Table.Th>
          <Table.Th>Tags</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map(({ item: doc, isChild, childCount }) => (
          <Table.Tr
            key={doc.id}
            style={{ cursor: "pointer", backgroundColor: isChild ? "var(--mantine-color-gray-0)" : undefined }}
          >
            <Table.Td>
              <Checkbox
                checked={selectedIds.has(doc.id)}
                onChange={() => {
                  const childIds = children.get(doc.id)?.map(getId) ?? [];
                  if (!isChild && childIds.length > 0 && onToggleFamily) {
                    onToggleFamily(doc.id, childIds);
                  } else {
                    onToggleSelect(doc.id);
                  }
                }}
                onClick={(e) => e.stopPropagation()}
              />
            </Table.Td>
            <Table.Td onClick={() => navigate(`/cases/${caseId}/documents/${doc.id}`)}>
              <span style={{ paddingLeft: isChild ? 20 : 0, display: "inline-flex", alignItems: "center", gap: 4 }}>
                {isChild && <IconPaperclip size={13} style={{ opacity: 0.6 }} />}
                {doc.subject || <Text c="dimmed">(no subject)</Text>}
                {!isChild && childCount > 0 && (
                  <Badge size="xs" variant="light" ml={4}>
                    {childCount} attachment{childCount > 1 ? "s" : ""}
                  </Badge>
                )}
              </span>
            </Table.Td>
            <Table.Td onClick={() => navigate(`/cases/${caseId}/documents/${doc.id}`)}>
              {doc.sender}
            </Table.Td>
            <Table.Td onClick={() => navigate(`/cases/${caseId}/documents/${doc.id}`)}>
              {doc.sent_at ? new Date(doc.sent_at).toLocaleString() : ""}
            </Table.Td>
            <Table.Td onClick={() => navigate(`/cases/${caseId}/documents/${doc.id}`)}>
              <Badge size="sm" variant="light">
                {doc.doc_type}
              </Badge>
            </Table.Td>
            <Table.Td onClick={() => navigate(`/cases/${caseId}/documents/${doc.id}`)}>
              <Badge size="sm" color={DEDUP_COLOR[doc.dedup_status]}>
                {doc.dedup_status}
              </Badge>
              {doc.render_error && (
                <Badge size="sm" color="red" ml={4}>
                  render failed
                </Badge>
              )}
              {doc.ocr_status === "completed" && (
                <Badge size="sm" color="blue" variant="light" ml={4}>
                  OCR'd
                </Badge>
              )}
              {doc.ocr_status === "failed" && (
                <Badge size="sm" color="red" variant="light" ml={4}>
                  OCR failed
                </Badge>
              )}
            </Table.Td>
            <Table.Td onClick={() => navigate(`/cases/${caseId}/documents/${doc.id}`)}>
              {doc.tags.map((tag) => (
                <Badge key={tag.id} size="sm" color={tag.color} mr={4}>
                  {tag.name}
                </Badge>
              ))}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
