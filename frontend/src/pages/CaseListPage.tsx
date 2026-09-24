import {
  Badge,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconFolder, IconFolderOpen, IconPlus } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { createCase, listCases, type CaseRole } from "../api/cases";
import { EmptyState } from "../components/EmptyState";

const ROLE_COLOR: Record<CaseRole, string> = {
  admin: "indigo",
  reviewer: "blue",
  viewer: "gray",
};

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
    <Container size="lg" py="xl">
      <Group justify="space-between" mb="xl" align="flex-end">
        <div>
          <Title order={2}>Cases</Title>
          <Text size="sm" c="dimmed">
            Everything you have access to review, in one place.
          </Text>
        </div>
        <Button onClick={open} leftSection={<IconPlus size={16} />}>
          New case
        </Button>
      </Group>

      {isLoading && (
        <Center py={60}>
          <Loader />
        </Center>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
        {cases?.map((c) => (
          <Card
            key={c.id}
            component={Link}
            to={`/cases/${c.id}`}
            padding="lg"
            className="hover-lift"
            style={{ textDecoration: "none" }}
          >
            <Group justify="space-between" align="flex-start" wrap="nowrap" mb="sm">
              <ThemeIcon size={38} radius="md" variant="light" color="indigo">
                <IconFolder size={20} stroke={1.75} />
              </ThemeIcon>
              {c.my_role && (
                <Badge color={ROLE_COLOR[c.my_role]} variant="light">
                  {c.my_role}
                </Badge>
              )}
            </Group>
            <Text fw={600} lineClamp={1}>
              {c.name}
            </Text>
            <Text size="sm" c="dimmed" lineClamp={2} mt={2}>
              {c.description || "No description"}
            </Text>
          </Card>
        ))}
      </SimpleGrid>

      {cases?.length === 0 && !isLoading && (
        <EmptyState
          icon={IconFolderOpen}
          title="No cases yet"
          description="Create a case to start importing PSTs and reviewing documents."
          action={
            <Button onClick={open} leftSection={<IconPlus size={16} />} mt="xs">
              New case
            </Button>
          }
        />
      )}

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
