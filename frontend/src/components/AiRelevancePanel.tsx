import { Badge, Group, Stack, Text, Title } from "@mantine/core";

import type { DocumentDetail } from "../api/documents";

function scoreColor(score: number): string {
  if (score >= 70) return "green";
  if (score >= 40) return "yellow";
  return "gray";
}

export function AiRelevancePanel({ document }: { document: DocumentDetail }) {
  const relevance = document.ai_relevance;
  if (!relevance) return null;

  return (
    <Stack gap="xs">
      <Title order={5}>AI relevance</Title>
      <Text size="xs" c="dimmed">
        Advisory only — assists human review, never a final relevance determination.
      </Text>
      {(relevance.status === "queued" || relevance.status === "running") && (
        <Text size="sm" c="dimmed">
          Scoring in progress...
        </Text>
      )}
      {relevance.status === "failed" && (
        <Text size="sm" c="red">
          Scoring failed: {relevance.error || "unknown error"}
        </Text>
      )}
      {relevance.status === "completed" && relevance.score !== null && (
        <>
          <Group gap="xs">
            <Badge size="lg" color={scoreColor(relevance.score)}>
              {relevance.score}/100
            </Badge>
          </Group>
          <Text size="sm">{relevance.rationale}</Text>
          {relevance.scored_at && (
            <Text size="xs" c="dimmed">
              Scored {new Date(relevance.scored_at).toLocaleString()}
            </Text>
          )}
        </>
      )}
    </Stack>
  );
}
