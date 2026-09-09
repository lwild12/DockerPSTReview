import {
  Badge,
  Button,
  Center,
  Container,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconMailOff, IconX } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { listDocuments, type DedupStatus, type DocType } from "../api/documents";
import { addDocumentsToReviewSet, createReviewSet, listReviewSets } from "../api/reviewSets";
import { applyTagBulk, listTags } from "../api/tags";
import { DocumentTable } from "../components/DocumentTable";
import { EmptyState } from "../components/EmptyState";

export function DocumentListPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [docType, setDocType] = useState<string | null>(null);
  const [dedupStatus, setDedupStatus] = useState<string | null>(null);
  const [inclusiveFilter, setInclusiveFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const clusterFilter = searchParams.get("near_duplicate_cluster_id");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [modalOpened, { open: openModal, close: closeModal }] = useDisclosure(false);
  const [reviewSetChoice, setReviewSetChoice] = useState<string | null>(null);
  const [newReviewSetName, setNewReviewSetName] = useState("");
  const [bulkTagChoice, setBulkTagChoice] = useState<string | null>(null);

  const { data: documents, isLoading } = useQuery({
    queryKey: ["documents", caseId, docType, dedupStatus, inclusiveFilter, clusterFilter, search],
    queryFn: () =>
      listDocuments(caseId, {
        doc_type: (docType as DocType) || undefined,
        dedup_status: (dedupStatus as DedupStatus) || undefined,
        is_inclusive_email: inclusiveFilter ? inclusiveFilter === "true" : undefined,
        near_duplicate_cluster_id: clusterFilter || undefined,
        q: search || undefined,
      }),
    enabled: caseId !== "",
  });

  const { data: reviewSets } = useQuery({
    queryKey: ["review-sets", caseId],
    queryFn: () => listReviewSets(caseId),
    enabled: caseId !== "",
  });

  const { data: tags } = useQuery({
    queryKey: ["tags", caseId],
    queryFn: () => listTags(caseId),
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

  const toggleFamily = (parentId: string, childIds: string[]) => {
    setSelectedIds((prev) => {
      const familyIds = [parentId, ...childIds];
      const allSelected = familyIds.every((id) => prev.has(id));
      const next = new Set(prev);
      familyIds.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const toggleSelectAll = (checked: boolean) => {
    setSelectedIds(checked ? new Set((documents ?? []).map((d) => d.id)) : new Set());
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

  const bulkTagMutation = useMutation({
    mutationFn: (tagId: string) => applyTagBulk(caseId, tagId, Array.from(selectedIds)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", caseId] });
      setSelectedIds(new Set());
      setBulkTagChoice(null);
    },
  });

  return (
    <Container size="xl" py="xl">
      <Title order={2} mb="lg">
        Documents
      </Title>

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
        <Select
          placeholder="All thread messages"
          clearable
          data={[
            { value: "true", label: "Hide redundant thread messages" },
            { value: "false", label: "Only redundant thread messages" },
          ]}
          value={inclusiveFilter}
          onChange={setInclusiveFilter}
          w={240}
        />
        <TextInput
          placeholder="Search subject/body/sender"
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          w={280}
        />
        {selectedIds.size > 0 && (
          <>
            <Button onClick={openModal}>Add {selectedIds.size} to review set</Button>
            <Select
              placeholder="Tag selected..."
              size="sm"
              w={160}
              data={(tags ?? []).map((t) => ({ value: t.id, label: t.name }))}
              value={bulkTagChoice}
              onChange={(value) => {
                setBulkTagChoice(value);
                if (value) bulkTagMutation.mutate(value);
              }}
              disabled={bulkTagMutation.isPending}
            />
          </>
        )}
      </Group>

      {clusterFilter && (
        <Badge
          size="lg"
          variant="light"
          mb="md"
          rightSection={
            <IconX
              size={12}
              style={{ cursor: "pointer" }}
              onClick={() =>
                setSearchParams((prev) => {
                  const next = new URLSearchParams(prev);
                  next.delete("near_duplicate_cluster_id");
                  return next;
                })
              }
            />
          }
        >
          Showing near-duplicates of this document
        </Badge>
      )}

      {isLoading && (
        <Center py={60}>
          <Loader />
        </Center>
      )}
      {documents && documents.length > 0 && (
        <DocumentTable
          documents={documents}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onToggleSelectAll={toggleSelectAll}
          onToggleFamily={toggleFamily}
        />
      )}
      {documents?.length === 0 && (
        <EmptyState
          icon={IconMailOff}
          title="No documents match these filters"
          description="Try clearing the type, status, or search filters above."
        />
      )}

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
