import { Anchor, NavLink, Stack, Text, Title } from "@mantine/core";
import { IconCopy } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listNearDuplicateClusterDocuments } from "../api/analytics";
import type { DocumentDetail } from "../api/documents";
import { documentLink } from "../lib/links";

export function NearDuplicatesPanel({
  caseId,
  document,
  reviewSetId,
}: {
  caseId: string;
  document: DocumentDetail;
  reviewSetId?: string;
}) {
  const clusterId = document.near_duplicate_cluster_id as string;

  const { data: members } = useQuery({
    queryKey: ["near-duplicate-cluster-documents", caseId, clusterId],
    queryFn: () => listNearDuplicateClusterDocuments(caseId, clusterId),
  });

  const others = (members ?? []).filter((m) => m.id !== document.id);

  const linkTo = (id: string) => documentLink(caseId, id, reviewSetId);

  return (
    <Stack gap="xs">
      <Title order={5}>Similar documents</Title>
      <Text size="xs" c="dimmed">
        Flagged as near-duplicates of each other based on content similarity.
      </Text>
      {others.map((doc) => (
        <NavLink
          key={doc.id}
          component={Link}
          to={linkTo(doc.id)}
          label={doc.subject || "(no subject)"}
          leftSection={<IconCopy size={14} />}
          description={doc.sender}
        />
      ))}
      <Anchor
        component={Link}
        to={`/cases/${caseId}/documents?near_duplicate_cluster_id=${clusterId}`}
        size="xs"
      >
        View all in document list →
      </Anchor>
    </Stack>
  );
}
