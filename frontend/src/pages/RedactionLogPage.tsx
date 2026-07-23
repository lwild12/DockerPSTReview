import { Anchor, Badge, Button, Container, Table, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { listCaseRedactionLog, redactionLogCsvUrl } from "../api/redactionLog";

export function RedactionLogPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const enabled = caseId !== "";

  const { data: entries, isLoading } = useQuery({
    queryKey: ["redaction-log", caseId],
    queryFn: () => listCaseRedactionLog(caseId),
    enabled,
  });

  return (
    <Container size="lg" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}`} size="sm">
        ← Back to case
      </Anchor>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Title order={2} mt="sm" mb="lg">
          Redaction log
        </Title>
        <Button
          component="a"
          href={redactionLogCsvUrl(caseId)}
          variant="light"
          size="xs"
          download
        >
          Export CSV
        </Button>
      </div>
      <Text c="dimmed" size="sm" mb="lg">
        Every redaction currently applied across this case's documents, for QC review and
        privilege-log style reporting.
      </Text>

      {isLoading && <Text>Loading...</Text>}
      {entries && entries.length > 0 && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Document</Table.Th>
              <Table.Th>From</Table.Th>
              <Table.Th>Page</Table.Th>
              <Table.Th>Reason</Table.Th>
              <Table.Th>Redacted by</Table.Th>
              <Table.Th>Date</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {entries.map((entry) => (
              <Table.Tr key={entry.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/cases/${caseId}/documents/${entry.document_id}`}>
                    {entry.document_subject || "(no subject)"}
                  </Anchor>
                </Table.Td>
                <Table.Td>{entry.document_sender}</Table.Td>
                <Table.Td>
                  <Badge size="sm" variant="light">
                    {entry.page_number + 1}
                  </Badge>
                </Table.Td>
                <Table.Td>{entry.reason || <Text c="dimmed">—</Text>}</Table.Td>
                <Table.Td>{entry.created_by_email ?? "—"}</Table.Td>
                <Table.Td>{new Date(entry.created_at).toLocaleString()}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {entries?.length === 0 && <Text c="dimmed">No redactions applied in this case yet.</Text>}
    </Container>
  );
}
