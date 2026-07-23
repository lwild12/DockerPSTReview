import {
  Anchor,
  Badge,
  Button,
  Container,
  Group,
  List,
  Modal,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  addMember,
  createCustodian,
  getCase,
  listCustodians,
  listMembers,
  type CaseRole,
} from "../api/cases";

export function CaseDetailPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const [memberModal, { open: openMemberModal, close: closeMemberModal }] = useDisclosure(false);
  const [custodianModal, { open: openCustodianModal, close: closeCustodianModal }] =
    useDisclosure(false);
  const [memberUserId, setMemberUserId] = useState("");
  const [memberRole, setMemberRole] = useState<CaseRole>("reviewer");
  const [custodianName, setCustodianName] = useState("");
  const [custodianEmail, setCustodianEmail] = useState("");

  const enabled = caseId !== "";
  const { data: caseData } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId),
    enabled,
  });
  const { data: members } = useQuery({
    queryKey: ["case-members", caseId],
    queryFn: () => listMembers(caseId),
    enabled,
  });
  const { data: custodians } = useQuery({
    queryKey: ["custodians", caseId],
    queryFn: () => listCustodians(caseId),
    enabled,
  });

  const isAdmin = caseData?.my_role === "admin";

  const addMemberMutation = useMutation({
    mutationFn: () => addMember(caseId, memberUserId, memberRole),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-members", caseId] });
      setMemberUserId("");
      closeMemberModal();
    },
  });

  const addCustodianMutation = useMutation({
    mutationFn: () => createCustodian(caseId, custodianName, custodianEmail),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["custodians", caseId] });
      setCustodianName("");
      setCustodianEmail("");
      closeCustodianModal();
    },
  });

  return (
    <Container size="md" py="xl">
      <Anchor component={Link} to="/cases" size="sm">
        ← Back to cases
      </Anchor>
      <Group justify="space-between" mt="sm" mb="lg">
        <Title order={2}>{caseData?.name}</Title>
        <Group>
          {caseData?.my_role && <Badge>{caseData.my_role}</Badge>}
          <Button component={Link} to={`/cases/${caseId}/documents`} size="xs" variant="light">
            Documents
          </Button>
          <Button component={Link} to={`/cases/${caseId}/review-sets`} size="xs" variant="light">
            Review sets
          </Button>
          <Button component={Link} to={`/cases/${caseId}/export`} size="xs" variant="light">
            Export
          </Button>
          <Button component={Link} to={`/cases/${caseId}/import`} size="xs" variant="light">
            Import PST
          </Button>
          {isAdmin && (
            <Button component={Link} to={`/cases/${caseId}/audit-log`} size="xs" variant="light">
              Audit log
            </Button>
          )}
        </Group>
      </Group>
      <Text c="dimmed" mb="xl">
        {caseData?.description}
      </Text>

      <Group justify="space-between" mb="sm">
        <Title order={4}>Members</Title>
        {isAdmin && (
          <Button size="xs" onClick={openMemberModal}>
            Add member
          </Button>
        )}
      </Group>
      <List mb="xl">
        {members?.map((m) => (
          <List.Item key={m.id}>
            {m.user_id} — <Badge size="sm">{m.role}</Badge>
          </List.Item>
        ))}
      </List>

      <Group justify="space-between" mb="sm">
        <Title order={4}>Custodians</Title>
        {isAdmin && (
          <Button size="xs" onClick={openCustodianModal}>
            Add custodian
          </Button>
        )}
      </Group>
      <List>
        {custodians?.map((c) => (
          <List.Item key={c.id}>
            {c.name} {c.email && `(${c.email})`}
          </List.Item>
        ))}
      </List>

      <Modal opened={memberModal} onClose={closeMemberModal} title="Add member">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            addMemberMutation.mutate();
          }}
        >
          <Stack>
            <TextInput
              label="User ID"
              description="UUID of an already-registered user"
              required
              value={memberUserId}
              onChange={(e) => setMemberUserId(e.currentTarget.value)}
            />
            <Select
              label="Role"
              data={["admin", "reviewer", "viewer"]}
              required
              allowDeselect={false}
              value={memberRole}
              onChange={(value) => setMemberRole(value as CaseRole)}
            />
            <Button type="submit" loading={addMemberMutation.isPending}>
              Add
            </Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={custodianModal} onClose={closeCustodianModal} title="Add custodian">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            addCustodianMutation.mutate();
          }}
        >
          <Stack>
            <TextInput
              label="Name"
              required
              value={custodianName}
              onChange={(e) => setCustodianName(e.currentTarget.value)}
            />
            <TextInput
              label="Email"
              value={custodianEmail}
              onChange={(e) => setCustodianEmail(e.currentTarget.value)}
            />
            <Button type="submit" loading={addCustodianMutation.isPending}>
              Add
            </Button>
          </Stack>
        </form>
      </Modal>
    </Container>
  );
}
