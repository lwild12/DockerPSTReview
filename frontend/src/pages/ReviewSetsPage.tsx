import {
  Anchor,
  Badge,
  Button,
  Card,
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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  createReviewSet,
  listReviewSetDocuments,
  listReviewSets,
  updateReviewSetDocument,
  type ReviewStatus,
} from "../api/reviewSets";

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

  return (
    <Container size="xl" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}/review-sets`} size="sm">
        ← Back to review sets
      </Anchor>
      <Title order={2} mt="sm" mb="lg">
        Review set documents
      </Title>

      {isLoading && <Text>Loading...</Text>}
      {documents && documents.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Document</Table.Th>
              <Table.Th>From</Table.Th>
              <Table.Th>Sent</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Notes</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {documents.map((d) => (
              <Table.Tr key={d.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/cases/${caseId}/documents/${d.document_id}`}>
                    {d.document_subject || "(no subject)"}
                  </Anchor>
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
