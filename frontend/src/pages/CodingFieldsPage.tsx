import {
  ActionIcon,
  Anchor,
  Badge,
  Button,
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
import { IconPlus, IconX } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { getCase } from "../api/cases";
import {
  createCodingField,
  deleteCodingField,
  listCodingFields,
  updateCodingField,
  type CodingFieldType,
} from "../api/codingFields";

function OptionEditor({
  options,
  onChange,
}: {
  options: string[];
  onChange: (options: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  const addOption = () => {
    const value = draft.trim();
    if (value && !options.includes(value)) {
      onChange([...options, value]);
    }
    setDraft("");
  };

  return (
    <Stack gap="xs">
      <Group gap="xs" wrap="wrap">
        {options.map((option) => (
          <Badge
            key={option}
            variant="light"
            rightSection={
              <ActionIcon
                size="xs"
                variant="transparent"
                color="gray"
                onClick={() => onChange(options.filter((o) => o !== option))}
              >
                <IconX size={10} />
              </ActionIcon>
            }
          >
            {option}
          </Badge>
        ))}
        {options.length === 0 && (
          <Text size="sm" c="dimmed">
            No options yet.
          </Text>
        )}
      </Group>
      <TextInput
        placeholder="Add option and press Enter"
        size="xs"
        value={draft}
        onChange={(e) => setDraft(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            addOption();
          }
        }}
        rightSection={
          <ActionIcon size="xs" variant="transparent" disabled={!draft.trim()} onClick={addOption}>
            <IconPlus size={12} />
          </ActionIcon>
        }
      />
    </Stack>
  );
}

export function CodingFieldsPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const enabled = caseId !== "";

  const [createModal, { open: openCreateModal, close: closeCreateModal }] = useDisclosure(false);
  const [editFieldId, setEditFieldId] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<CodingFieldType>("single_select");
  const [newOptions, setNewOptions] = useState<string[]>([]);

  const [editName, setEditName] = useState("");
  const [editOptions, setEditOptions] = useState<string[]>([]);

  const { data: caseData } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId),
    enabled,
  });
  const isAdmin = caseData?.my_role === "admin";

  const { data: fields, isLoading } = useQuery({
    queryKey: ["coding-fields", caseId],
    queryFn: () => listCodingFields(caseId),
    enabled,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["coding-fields", caseId] });

  const createMutation = useMutation({
    mutationFn: () => createCodingField(caseId, newName, newType, newOptions),
    onSuccess: () => {
      invalidate();
      setNewName("");
      setNewType("single_select");
      setNewOptions([]);
      closeCreateModal();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (fieldId: string) =>
      updateCodingField(caseId, fieldId, { name: editName, options: editOptions }),
    onSuccess: () => {
      invalidate();
      setEditFieldId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (fieldId: string) => deleteCodingField(caseId, fieldId),
    onSuccess: invalidate,
  });

  const editingField = fields?.find((f) => f.id === editFieldId);

  return (
    <Container size="md" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}`} size="sm">
        ← Back to case
      </Anchor>
      <Group justify="space-between" mt="sm" mb="lg">
        <Title order={2}>Coding fields</Title>
        {isAdmin && <Button onClick={openCreateModal}>New field</Button>}
      </Group>
      <Text c="dimmed" size="sm" mb="lg">
        Structured single/multi-select fields for consistent review coding, separate from
        free-text tags.
      </Text>

      {isLoading && <Text>Loading...</Text>}
      {fields && fields.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Options</Table.Th>
              {isAdmin && <Table.Th w={140} />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {fields.map((field) => (
              <Table.Tr key={field.id}>
                <Table.Td>{field.name}</Table.Td>
                <Table.Td>
                  <Badge size="sm" variant="light">
                    {field.field_type === "single_select" ? "Single-select" : "Multi-select"}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap={4} wrap="wrap">
                    {field.options.map((option) => (
                      <Badge key={option} size="sm" variant="outline">
                        {option}
                      </Badge>
                    ))}
                  </Group>
                </Table.Td>
                {isAdmin && (
                  <Table.Td>
                    <Group gap="xs">
                      <Button
                        size="xs"
                        variant="subtle"
                        onClick={() => {
                          setEditFieldId(field.id);
                          setEditName(field.name);
                          setEditOptions(field.options);
                        }}
                      >
                        Edit
                      </Button>
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        onClick={() => deleteMutation.mutate(field.id)}
                      >
                        Delete
                      </Button>
                    </Group>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {fields?.length === 0 && <Text c="dimmed">No coding fields yet.</Text>}

      <Modal opened={createModal} onClose={closeCreateModal} title="New coding field">
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
              value={newName}
              onChange={(e) => setNewName(e.currentTarget.value)}
            />
            <Select
              label="Type"
              data={[
                { value: "single_select", label: "Single-select" },
                { value: "multi_select", label: "Multi-select" },
              ]}
              required
              allowDeselect={false}
              value={newType}
              onChange={(value) => setNewType(value as CodingFieldType)}
            />
            <Text size="sm" fw={500}>
              Options
            </Text>
            <OptionEditor options={newOptions} onChange={setNewOptions} />
            {createMutation.isError && (
              <Text c="red" size="sm">
                Couldn't create that field — check the name isn't already used and there's at
                least one option.
              </Text>
            )}
            <Button type="submit" loading={createMutation.isPending} disabled={newOptions.length === 0}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={editFieldId !== null} onClose={() => setEditFieldId(null)} title="Edit coding field">
        <Stack>
          <TextInput
            label="Name"
            required
            value={editName}
            onChange={(e) => setEditName(e.currentTarget.value)}
          />
          <Text size="sm" fw={500}>
            Options
          </Text>
          <OptionEditor options={editOptions} onChange={setEditOptions} />
          {updateMutation.isError && (
            <Text c="red" size="sm">
              Couldn't save — a field needs at least one option.
            </Text>
          )}
          <Button
            loading={updateMutation.isPending}
            disabled={editOptions.length === 0}
            onClick={() => editingField && updateMutation.mutate(editingField.id)}
          >
            Save
          </Button>
        </Stack>
      </Modal>
    </Container>
  );
}
