import { Anchor, Badge, Button, Container, Grid, Group, Stack, Text, Title } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { documentPdfUrl, getDocument } from "../api/documents";
import { createRedaction, deleteRedaction, listRedactions } from "../api/redactions";
import { PdfViewer } from "../components/PdfViewer";
import { TagPicker } from "../components/TagPicker";
import { ThreadPanel } from "../components/ThreadPanel";

export function DocumentViewerPage() {
  const { caseId = "", documentId = "" } = useParams<{ caseId: string; documentId: string }>();
  const enabled = caseId !== "" && documentId !== "";
  const queryClient = useQueryClient();
  const [redactionMode, setRedactionMode] = useState(false);

  const { data: document, isLoading } = useQuery({
    queryKey: ["document", caseId, documentId],
    queryFn: () => getDocument(caseId, documentId),
    enabled,
  });

  const { data: redactions } = useQuery({
    queryKey: ["redactions", caseId, documentId],
    queryFn: () => listRedactions(caseId, documentId),
    enabled,
  });

  const invalidateRedactions = () =>
    queryClient.invalidateQueries({ queryKey: ["redactions", caseId, documentId] });

  const createMutation = useMutation({
    mutationFn: (params: {
      pageNumber: number;
      rect: { x: number; y: number; width: number; height: number };
    }) =>
      createRedaction(caseId, documentId, {
        page_number: params.pageNumber,
        ...params.rect,
      }),
    onSuccess: invalidateRedactions,
  });

  const deleteMutation = useMutation({
    mutationFn: (redactionId: string) => deleteRedaction(caseId, documentId, redactionId),
    onSuccess: invalidateRedactions,
  });

  return (
    <Container size="xl" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}/documents`} size="sm">
        ← Back to documents
      </Anchor>

      {isLoading && <Text mt="md">Loading...</Text>}

      {document && (
        <>
          <Group justify="space-between" mt="sm" mb="md">
            <Title order={3}>{document.subject || "(no subject)"}</Title>
            <Badge>{document.doc_type}</Badge>
          </Group>

          <Stack gap={4} mb="md">
            <Text size="sm">
              <Text span fw={600}>
                From:
              </Text>{" "}
              {document.sender}
            </Text>
            {document.recipients_to.length > 0 && (
              <Text size="sm">
                <Text span fw={600}>
                  To:
                </Text>{" "}
                {document.recipients_to.join(", ")}
              </Text>
            )}
            {document.sent_at && (
              <Text size="sm">
                <Text span fw={600}>
                  Sent:
                </Text>{" "}
                {new Date(document.sent_at).toLocaleString()}
              </Text>
            )}
            {document.dedup_status === "duplicate" && (
              <Badge color="orange" w="fit-content">
                Duplicate of another document
              </Badge>
            )}
          </Stack>

          <TagPicker caseId={caseId} documentId={documentId} appliedTags={document.tags} />

          <Grid mt="lg">
            <Grid.Col span={document.thread_id ? 9 : 12}>
              {document.rendered_pdf_page_count > 0 ? (
                <>
                  <Group justify="flex-end" mb="xs">
                    <Button
                      size="xs"
                      variant={redactionMode ? "filled" : "light"}
                      color={redactionMode ? "red" : "gray"}
                      onClick={() => setRedactionMode((v) => !v)}
                    >
                      {redactionMode ? "Done redacting" : "Redact"}
                    </Button>
                  </Group>
                  <PdfViewer
                    url={documentPdfUrl(caseId, documentId)}
                    redactions={redactions ?? []}
                    readOnly={!redactionMode}
                    onCreateRedaction={
                      redactionMode
                        ? (pageNumber, rect) => createMutation.mutate({ pageNumber, rect })
                        : undefined
                    }
                    onDeleteRedaction={
                      redactionMode ? (id) => deleteMutation.mutate(id) : undefined
                    }
                  />
                </>
              ) : (
                <Text c="dimmed">
                  {document.render_error
                    ? `This document failed to render: ${document.render_error}`
                    : "This document has not been rendered yet."}
                </Text>
              )}
            </Grid.Col>
            {document.thread_id && (
              <Grid.Col span={3}>
                <ThreadPanel
                  caseId={caseId}
                  threadId={document.thread_id}
                  currentDocumentId={documentId}
                />
              </Grid.Col>
            )}
          </Grid>
        </>
      )}
    </Container>
  );
}
