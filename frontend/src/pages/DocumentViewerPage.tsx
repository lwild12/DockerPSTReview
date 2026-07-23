import {
  Anchor,
  Badge,
  Button,
  Container,
  Grid,
  Group,
  Select,
  Spoiler,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { documentPdfUrl, getDocument } from "../api/documents";
import { createRedaction, deleteRedaction, listRedactions } from "../api/redactions";
import {
  listReviewSetDocuments,
  updateReviewSetDocument,
  type ReviewStatus,
} from "../api/reviewSets";
import { PdfViewer } from "../components/PdfViewer";
import { TagPicker } from "../components/TagPicker";
import { ThreadPanel } from "../components/ThreadPanel";

const STATUS_COLOR: Record<ReviewStatus, string> = {
  unreviewed: "gray",
  in_review: "blue",
  reviewed: "green",
  flagged: "red",
};

export function DocumentViewerPage() {
  const { caseId = "", documentId = "" } = useParams<{ caseId: string; documentId: string }>();
  const [searchParams] = useSearchParams();
  const reviewSetId = searchParams.get("reviewSet") ?? "";
  const navigate = useNavigate();
  const enabled = caseId !== "" && documentId !== "";
  const queryClient = useQueryClient();
  const [redactionMode, setRedactionMode] = useState(false);

  const { data: document, isLoading } = useQuery({
    queryKey: ["document", caseId, documentId],
    queryFn: () => getDocument(caseId, documentId),
    enabled,
  });

  const { data: reviewSetDocs } = useQuery({
    queryKey: ["review-set-documents", caseId, reviewSetId],
    queryFn: () => listReviewSetDocuments(caseId, reviewSetId),
    enabled: enabled && reviewSetId !== "",
  });

  const currentIndex = reviewSetDocs?.findIndex((d) => d.document_id === documentId) ?? -1;
  const currentReviewDoc = currentIndex >= 0 ? reviewSetDocs?.[currentIndex] : undefined;
  const prevDoc = currentIndex > 0 ? reviewSetDocs?.[currentIndex - 1] : undefined;
  const nextDoc =
    reviewSetDocs && currentIndex >= 0 && currentIndex < reviewSetDocs.length - 1
      ? reviewSetDocs[currentIndex + 1]
      : undefined;

  const goTo = (targetDocumentId: string) =>
    navigate(`/cases/${caseId}/documents/${targetDocumentId}?reviewSet=${reviewSetId}`);

  useEffect(() => {
    if (reviewSetId === "") return;
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;
      if (e.key === "ArrowLeft" && prevDoc) goTo(prevDoc.document_id);
      if (e.key === "ArrowRight" && nextDoc) goTo(nextDoc.document_id);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reviewSetId, prevDoc, nextDoc]);

  const statusMutation = useMutation({
    mutationFn: (status: ReviewStatus) =>
      updateReviewSetDocument(caseId, reviewSetId, documentId, { review_status: status }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["review-set-documents", caseId, reviewSetId] }),
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
      <Group justify="space-between">
        <Anchor
          component={Link}
          to={
            reviewSetId !== ""
              ? `/cases/${caseId}/review-sets/${reviewSetId}`
              : `/cases/${caseId}/documents`
          }
          size="sm"
        >
          ← Back to {reviewSetId !== "" ? "review set" : "documents"}
        </Anchor>
        {reviewSetId !== "" && reviewSetDocs && currentIndex >= 0 && (
          <Group gap="xs">
            <Text size="sm" c="dimmed">
              {currentIndex + 1} of {reviewSetDocs.length}
            </Text>
            <Button
              size="xs"
              variant="light"
              disabled={!prevDoc}
              onClick={() => prevDoc && goTo(prevDoc.document_id)}
            >
              ← Previous
            </Button>
            <Button
              size="xs"
              variant="light"
              disabled={!nextDoc}
              onClick={() => nextDoc && goTo(nextDoc.document_id)}
            >
              Next →
            </Button>
          </Group>
        )}
      </Group>

      {isLoading && <Text mt="md">Loading...</Text>}

      {document && (
        <>
          <Group justify="space-between" mt="sm" mb="md">
            <Title order={3}>{document.subject || "(no subject)"}</Title>
            <Group gap="xs">
              {currentReviewDoc && (
                <>
                  <Select
                    size="xs"
                    w={140}
                    data={["unreviewed", "in_review", "reviewed", "flagged"]}
                    value={currentReviewDoc.review_status}
                    allowDeselect={false}
                    onChange={(value) => value && statusMutation.mutate(value as ReviewStatus)}
                  />
                  <Badge color={STATUS_COLOR[currentReviewDoc.review_status]} size="sm">
                    {currentReviewDoc.review_status.replace("_", " ")}
                  </Badge>
                </>
              )}
              <Badge>{document.doc_type}</Badge>
            </Group>
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

          {document.ocr_status === "completed" && (
            <Stack gap={4} mt="md">
              <Badge color="blue" variant="light" w="fit-content">
                Scanned document — text extracted via OCR
              </Badge>
              <Spoiler maxHeight={120} showLabel="Show more" hideLabel="Show less">
                <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>
                  {document.ocr_text}
                </Text>
              </Spoiler>
            </Stack>
          )}
          {document.ocr_status === "failed" && (
            <Badge color="red" variant="light" mt="md" w="fit-content">
              OCR failed: {document.ocr_error}
            </Badge>
          )}

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
