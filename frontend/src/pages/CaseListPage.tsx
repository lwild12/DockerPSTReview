import {
  Badge,
  Button,
  Card,
  Container,
  Group,
  Modal,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { createCase, listCases } from "../api/cases";
import { useAuth } from "../hooks/useAuth";

export function CaseListPage() {
  const { user, logout } = useAuth();
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
        <Group>
          <Text size="sm" c="dimmed">
            {user?.email}
          </Text>
          <Button variant="subtle" onClick={() => { logout().catch(() => {}); }}>
            Sign out
          </Button>
        </Group>
      </Group>

      <Group justify="flex-end" mb="md">
        <Button onClick={open}>New case</Button>
      </Group>

      {isLoading && <Text>Loading...</Text>}

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
          <Text c="dimmed">No cases yet. Create one to get started.</Text>
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
