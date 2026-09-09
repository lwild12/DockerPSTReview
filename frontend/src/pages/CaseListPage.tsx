import {
  Badge,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconFolderOpen } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { createCase, listCases } from "../api/cases";
import { EmptyState } from "../components/EmptyState";

export function CaseListPage() {
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data: cases, isLoading } = useQuery({ queryKey: ["cases"], queryFn: listCases });

  const createMutation = useMutation({
    mutationFn: () => createCase(name, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      setName("");
      setDescription("");
      close();
    },
  });

  const handleCreate = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate();
  };

  return (
    <Container size="md" py="xl">
      <Group justify="space-between" mb="lg">
        <Title order={2}>Cases</Title>
        <Button onClick={open}>New case</Button>
      </Group>

      {isLoading && (
        <Center py={60}>
          <Loader />
        </Center>
      )}

      <Stack>
        {cases?.map((c) => (
          <Card key={c.id} component={Link} to={`/cases/${c.id}`} withBorder padding="lg">
            <Group justify="space-between">
              <div>
                <Text fw={600}>{c.name}</Text>
                <Text size="sm" c="dimmed">
                  {c.description}
                </Text>
              </div>
              {c.my_role && <Badge>{c.my_role}</Badge>}
            </Group>
          </Card>
        ))}
        {cases?.length === 0 && !isLoading && (
          <EmptyState
            icon={IconFolderOpen}
            title="No cases yet"
            description="Create a case to start importing PSTs and reviewing documents."
          />
        )}
      </Stack>

      <Modal opened={opened} onClose={close} title="Create case">
        <form onSubmit={handleCreate}>
          <Stack>
            <TextInput
              label="Name"
              required
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
            />
            <Textarea
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.currentTarget.value)}
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
