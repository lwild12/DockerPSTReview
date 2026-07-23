import {
  Anchor,
  Button,
  Container,
  Group,
  Modal,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { listDocuments, type DedupStatus, type DocType } from "../api/documents";
import { addDocumentsToReviewSet, createReviewSet, listReviewSets } from "../api/reviewSets";
import { DocumentTable } from "../components/DocumentTable";

export function DocumentListPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const [docType, setDocType] = useState<string | null>(null);
  const [dedupStatus, setDedupStatus] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [modalOpened, { open: openModal, close: closeModal }] = useDisclosure(false);
  const [reviewSetChoice, setReviewSetChoice] = useState<string | null>(null);
  const [newReviewSetName, setNewReviewSetName] = useState("");

  const { data: documents, isLoading } = useQuery({
    queryKey: ["documents", caseId, docType, dedupStatus, search],
    queryFn: () =>
      listDocuments(caseId, {
        doc_type: (docType as DocType) || undefined,
        dedup_status: (dedupStatus as DedupStatus) || undefined,
        q: search || undefined,
      }),
    enabled: caseId !== "",
  });

  const { data: reviewSets } = useQuery({
    queryKey: ["review-sets", caseId],
    queryFn: () => listReviewSets(caseId),
    enabled: caseId !== "",
  });

  const toggleSelect = (documentId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(documentId)) next.delete(documentId);
      else next.add(documentId);
      return next;
    });
  };

  const addToReviewSetMutation = useMutation({
    mutationFn: async () => {
      let reviewSetId = reviewSetChoice;
      if (!reviewSetId && newReviewSetName.trim()) {
        const created = await createReviewSet(caseId, newReviewSetName.trim());
        reviewSetId = created.id;
      }
      if (!reviewSetId) throw new Error("Choose or create a review set");
      return addDocumentsToReviewSet(caseId, reviewSetId, Array.from(selectedIds));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-sets", caseId] });
      setSelectedIds(new Set());
      setReviewSetChoice(null);
      setNewReviewSetName("");
      closeModal();
    },
  });

  return (
    <Container size="xl" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}`} size="sm">
        ← Back to case
      </Anchor>
      <Group justify="space-between" mt="sm" mb="lg">
        <Title order={2}>Documents</Title>
        <Anchor component={Link} to={`/cases/${caseId}/review-sets`} size="sm">
          View review sets →
        </Anchor>
      </Group>

      <Group mb="md">
        <Select
          placeholder="All types"
          clearable
          data={["email", "attachment", "calendar", "contact"]}
          value={docType}
          onChange={setDocType}
          w={160}
        />
        <Select
          placeholder="All dedup statuses"
          clearable
          data={["primary", "duplicate"]}
          value={dedupStatus}
          onChange={setDedupStatus}
          w={180}
        />
        <TextInput
          placeholder="Search subject/body/sender"
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          w={280}
        />
        {selectedIds.size > 0 && (
          <Button onClick={openModal}>Add {selectedIds.size} to review set</Button>
        )}
      </Group>

      {isLoading && <Text>Loading...</Text>}
      {documents && (
        <DocumentTable
          documents={documents}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
        />
      )}
      {documents?.length === 0 && <Text c="dimmed">No documents match these filters.</Text>}

      <Modal opened={modalOpened} onClose={closeModal} title="Add to review set">
        <Stack>
          <Select
            label="Existing review set"
            placeholder="Select one"
            data={(reviewSets ?? []).map((rs) => ({ value: rs.id, label: rs.name }))}
            value={reviewSetChoice}
            onChange={setReviewSetChoice}
            clearable
          />
          <Text size="sm" c="dimmed">
            or
          </Text>
          <TextInput
            label="New review set name"
            value={newReviewSetName}
            onChange={(e) => setNewReviewSetName(e.currentTarget.value)}
            disabled={!!reviewSetChoice}
          />
          <Button
            onClick={() => addToReviewSetMutation.mutate()}
            loading={addToReviewSetMutation.isPending}
          >
            Add {selectedIds.size} document(s)
          </Button>
        </Stack>
      </Modal>
    </Container>
  );
}
