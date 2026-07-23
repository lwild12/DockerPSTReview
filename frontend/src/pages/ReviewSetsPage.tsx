import {
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Container,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconPaperclip } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  bulkUpdateReviewStatus,
  createReviewSet,
  listReviewSetDocuments,
  listReviewSets,
  updateReviewSetDocument,
  type ReviewSetDocument,
  type ReviewStatus,
} from "../api/reviewSets";
import { childrenByParent, groupIntoFamilies } from "../lib/documentFamilies";

const STATUS_COLOR: Record<ReviewStatus, string> = {
  unreviewed: "gray",
  in_review: "blue",
  reviewed: "green",
  flagged: "red",
};

export function ReviewSetsPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [name, setName] = useState("");

  const { data: reviewSets, isLoading } = useQuery({
    queryKey: ["review-sets", caseId],
    queryFn: () => listReviewSets(caseId),
    enabled: caseId !== "",
  });

  const createMutation = useMutation({
    mutationFn: () => createReviewSet(caseId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-sets", caseId] });
      setName("");
      close();
    },
  });

  return (
    <Container size="md" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}`} size="sm">
        ← Back to case
      </Anchor>
      <Group justify="space-between" mt="sm" mb="lg">
        <Title order={2}>Review sets</Title>
        <Button onClick={open}>New review set</Button>
      </Group>

      {isLoading && <Text>Loading...</Text>}
      <Stack>
        {reviewSets?.map((rs) => (
          <Card key={rs.id} component={Link} to={`/cases/${caseId}/review-sets/${rs.id}`} withBorder>
            <Text fw={600}>{rs.name}</Text>
            {rs.description && (
              <Text size="sm" c="dimmed">
                {rs.description}
              </Text>
            )}
          </Card>
        ))}
        {reviewSets?.length === 0 && <Text c="dimmed">No review sets yet.</Text>}
      </Stack>

      <Modal opened={opened} onClose={close} title="New review set">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <Stack>
            <TextInput
              label="Name"
              required
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
            />
            <Button type="submit" loading={createMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>
    </Container>
  );
}

export function ReviewSetDetailPage() {
  const { caseId = "", reviewSetId = "" } = useParams<{ caseId: string; reviewSetId: string }>();
  const queryClient = useQueryClient();
  const enabled = caseId !== "" && reviewSetId !== "";

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkStatusChoice, setBulkStatusChoice] = useState<string | null>(null);

  const { data: documents, isLoading } = useQuery({
    queryKey: ["review-set-documents", caseId, reviewSetId],
    queryFn: () => listReviewSetDocuments(caseId, reviewSetId),
    enabled,
  });

  const updateMutation = useMutation({
    mutationFn: ({ documentId, status }: { documentId: string; status: ReviewStatus }) =>
      updateReviewSetDocument(caseId, reviewSetId, documentId, { review_status: status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-set-documents", caseId, reviewSetId] });
    },
  });

  const bulkStatusMutation = useMutation({
    mutationFn: (status: ReviewStatus) =>
      bulkUpdateReviewStatus(caseId, reviewSetId, Array.from(selectedIds), status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-set-documents", caseId, reviewSetId] });
      setSelectedIds(new Set());
      setBulkStatusChoice(null);
    },
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
      const allInFamilySelected = familyIds.every((id) => prev.has(id));
      const next = new Set(prev);
      familyIds.forEach((id) => (allInFamilySelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const allSelected = (documents ?? []).length > 0 && (documents ?? []).every((d) => selectedIds.has(d.document_id));
  const someSelected = (documents ?? []).some((d) => selectedIds.has(d.document_id));
  const toggleSelectAll = (checked: boolean) => {
    setSelectedIds(checked ? new Set((documents ?? []).map((d) => d.document_id)) : new Set());
  };

  const rsGetId = (d: ReviewSetDocument) => d.document_id;
  const rsGetParentId = (d: ReviewSetDocument) => d.document_parent_document_id;
  const familyRows = groupIntoFamilies(documents ?? [], rsGetId, rsGetParentId);
  const familyChildren = childrenByParent(documents ?? [], rsGetParentId);

  return (
    <Container size="xl" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}/review-sets`} size="sm">
        ← Back to review sets
      </Anchor>
      <Group justify="space-between" mt="sm" mb="lg">
        <Title order={2}>Review set documents</Title>
        {selectedIds.size > 0 && (
          <Select
            placeholder={`Set status for ${selectedIds.size} selected...`}
            size="sm"
            w={220}
            data={["unreviewed", "in_review", "reviewed", "flagged"]}
            value={bulkStatusChoice}
            onChange={(value) => {
              setBulkStatusChoice(value);
              if (value) bulkStatusMutation.mutate(value as ReviewStatus);
            }}
            disabled={bulkStatusMutation.isPending}
          />
        )}
      </Group>

      {isLoading && <Text>Loading...</Text>}
      {documents && documents.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={36}>
                <Checkbox
                  checked={allSelected}
                  indeterminate={someSelected && !allSelected}
                  onChange={(e) => toggleSelectAll(e.currentTarget.checked)}
                />
              </Table.Th>
              <Table.Th>Document</Table.Th>
              <Table.Th>From</Table.Th>
              <Table.Th>Sent</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Notes</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {familyRows.map(({ item: d, isChild, childCount }) => (
              <Table.Tr key={d.id} style={{ backgroundColor: isChild ? "var(--mantine-color-gray-0)" : undefined }}>
                <Table.Td>
                  <Checkbox
                    checked={selectedIds.has(d.document_id)}
                    onChange={() => {
                      const childIds = familyChildren.get(d.document_id)?.map(rsGetId) ?? [];
                      if (!isChild && childIds.length > 0) {
                        toggleFamily(d.document_id, childIds);
                      } else {
                        toggleSelect(d.document_id);
                      }
                    }}
                  />
                </Table.Td>
                <Table.Td>
                  <span style={{ paddingLeft: isChild ? 20 : 0, display: "inline-flex", alignItems: "center", gap: 4 }}>
                    {isChild && <IconPaperclip size={13} style={{ opacity: 0.6 }} />}
                    <Anchor
                      component={Link}
                      to={`/cases/${caseId}/documents/${d.document_id}?reviewSet=${reviewSetId}`}
                    >
                      {d.document_subject || "(no subject)"}
                    </Anchor>
                    {!isChild && childCount > 0 && (
                      <Badge size="xs" variant="light" ml={4}>
                        {childCount} attachment{childCount > 1 ? "s" : ""}
                      </Badge>
                    )}
                  </span>
                </Table.Td>
                <Table.Td>{d.document_sender}</Table.Td>
                <Table.Td>
                  {d.document_sent_at ? new Date(d.document_sent_at).toLocaleString() : ""}
                </Table.Td>
                <Table.Td>
                  <Badge size="sm" variant="light">
                    {d.document_doc_type}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Select
                    size="xs"
                    w={140}
                    data={["unreviewed", "in_review", "reviewed", "flagged"]}
                    value={d.review_status}
                    allowDeselect={false}
                    onChange={(value) =>
                      value &&
                      updateMutation.mutate({
                        documentId: d.document_id,
                        status: value as ReviewStatus,
                      })
                    }
                  />
                  <Badge color={STATUS_COLOR[d.review_status]} ml="xs" size="xs">
                    {d.review_status.replace("_", " ")}
                  </Badge>
                </Table.Td>
                <Table.Td>{d.notes}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {documents?.length === 0 && <Text c="dimmed">No documents in this review set yet.</Text>}
    </Container>
  );
}
