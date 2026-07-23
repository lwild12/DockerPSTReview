import { NavLink, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listThreadDocuments } from "../api/documents";

export function ThreadPanel({
  caseId,
  threadId,
  currentDocumentId,
}: {
  caseId: string;
  threadId: string;
  currentDocumentId: string;
}) {
  const { data: siblings } = useQuery({
    queryKey: ["thread", caseId, threadId],
    queryFn: () => listThreadDocuments(caseId, threadId),
  });

  return (
    <Stack gap="xs">
      <Title order={5}>Thread</Title>
      {siblings?.map((doc) => (
        <NavLink
          key={doc.id}
          component={Link}
          to={`/cases/${caseId}/documents/${doc.id}`}
          active={doc.id === currentDocumentId}
          label={doc.subject || "(no subject)"}
          description={
            <Text size="xs" c="dimmed">
              {doc.sender} {doc.sent_at ? `— ${new Date(doc.sent_at).toLocaleString()}` : ""}
            </Text>
          }
        />
      ))}
      {siblings?.length === 0 && (
        <Text size="sm" c="dimmed">
          No other messages in this thread.
        </Text>
      )}
    </Stack>
  );
}
