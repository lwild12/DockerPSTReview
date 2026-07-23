import { Anchor, Code, Container, Table, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { listAuditLogs } from "../api/auditLogs";

export function AuditLogPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const enabled = caseId !== "";

  const { data: logs } = useQuery({
    queryKey: ["audit-logs", caseId],
    queryFn: () => listAuditLogs(caseId),
    enabled,
  });

  return (
    <Container size="lg" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}`} size="sm">
        ← Back to case
      </Anchor>
      <Title order={2} mt="sm" mb="lg">
        Audit log
      </Title>

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Time</Table.Th>
            <Table.Th>Action</Table.Th>
            <Table.Th>Target</Table.Th>
            <Table.Th>User</Table.Th>
            <Table.Th>Details</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {logs?.map((entry) => (
            <Table.Tr key={entry.id}>
              <Table.Td>
                <Text size="sm">{new Date(entry.created_at).toLocaleString()}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" fw={600}>
                  {entry.action}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {entry.target_type}
                  {entry.target_id && ` #${entry.target_id.slice(0, 8)}`}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {entry.user_id ? entry.user_id.slice(0, 8) : "—"}
                </Text>
              </Table.Td>
              <Table.Td>
                {Object.keys(entry.audit_metadata).length > 0 && (
                  <Code block fz="xs">
                    {JSON.stringify(entry.audit_metadata)}
                  </Code>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {logs?.length === 0 && (
        <Text c="dimmed" mt="md">
          No audit events yet.
        </Text>
      )}
    </Container>
  );
}
