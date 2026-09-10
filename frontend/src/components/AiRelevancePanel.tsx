import { Badge, Button, Group, Stack, Text, Title } from "@mantine/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runAiReviewForDocument } from "../api/aiReview";
import type { DocumentDetail } from "../api/documents";

function scoreColor(score: number): string {
  if (score >= 70) return "green";
  if (score >= 40) return "yellow";
  return "gray";
}

export function AiRelevancePanel({
  caseId,
  document,
  canRun,
}: {
  caseId: string;
  document: DocumentDetail;
  canRun: boolean;
}) {
  const queryClient = useQueryClient();
  const relevance = document.ai_relevance;

  const runMutation = useMutation({
    mutationFn: () => runAiReviewForDocument(caseId, document.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document", caseId, document.id] });
    },
  });

  return (
    <Stack gap="xs">
      <Title order={5}>AI relevance</Title>
      <Text size="xs" c="dimmed">
        Advisory only — assists human review, never a final relevance determination.
      </Text>
      {!relevance && (
        <Text size="sm" c="dimmed">
          Not yet scored.
        </Text>
      )}
      {relevance && (relevance.status === "queued" || relevance.status === "running") && (
        <Text size="sm" c="dimmed">
          Scoring in progress...
        </Text>
      )}
      {relevance && relevance.status === "failed" && (
        <Text size="sm" c="red">
          Scoring failed: {relevance.error || "unknown error"}
        </Text>
      )}
      {relevance && relevance.status === "completed" && relevance.score !== null && (
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
      {canRun && (
        <Button
          size="xs"
          variant="light"
          w="fit-content"
          loading={runMutation.isPending}
          onClick={() => runMutation.mutate()}
        >
          {relevance ? "Re-run on this document" : "Run AI review on this document"}
        </Button>
      )}
      {runMutation.isError && (
        <Text size="xs" c="red">
          Couldn't run scoring — check that Ollama is configured correctly.
        </Text>
      )}
    </Stack>
  );
}
