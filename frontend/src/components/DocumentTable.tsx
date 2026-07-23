import { Badge, Checkbox, Table, Text } from "@mantine/core";
import { useNavigate, useParams } from "react-router-dom";

import type { DocumentListItem } from "../api/documents";

const DEDUP_COLOR: Record<string, string> = { primary: "gray", duplicate: "orange" };

export function DocumentTable({
  documents,
  selectedIds,
  onToggleSelect,
}: {
  documents: DocumentListItem[];
  selectedIds: Set<string>;
  onToggleSelect: (documentId: string) => void;
}) {
  const navigate = useNavigate();
  const { caseId } = useParams<{ caseId: string }>();

  return (
    <Table striped highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={36} />
          <Table.Th>Subject</Table.Th>
          <Table.Th>From</Table.Th>
          <Table.Th>Sent</Table.Th>
          <Table.Th>Type</Table.Th>
          <Table.Th>Status</Table.Th>
          <Table.Th>Tags</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {documents.map((doc) => (
          <Table.Tr key={doc.id} style={{ cursor: "pointer" }}>
            <Table.Td>
              <Checkbox
                checked={selectedIds.has(doc.id)}
                onChange={() => onToggleSelect(doc.id)}
                onClick={(e) => e.stopPropagation()}
              />
            </Table.Td>
            <Table.Td onClick={() => navigate(`/cases/${caseId}/documents/${doc.id}`)}>
              {doc.subject || <Text c="dimmed">(no subject)</Text>}
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
