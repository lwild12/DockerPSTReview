import { ActionIcon, Badge, Group, Select, TextInput } from "@mantine/core";
import { IconPlus, IconX } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { applyTag, createTag, listTags, removeTag } from "../api/tags";
import { listTagPresets } from "../api/userPresets";

const PRESET_PREFIX = "preset:";

export function TagPicker({
  caseId,
  documentId,
  appliedTags,
}: {
  caseId: string;
  documentId: string;
  appliedTags: { id: string; name: string; color: string }[];
}) {
  const queryClient = useQueryClient();
  const [selectedTagId, setSelectedTagId] = useState<string | null>(null);
  const [newTagName, setNewTagName] = useState("");

  const { data: allTags } = useQuery({
    queryKey: ["tags", caseId],
    queryFn: () => listTags(caseId),
  });

  const { data: tagPresets } = useQuery({
    queryKey: ["tag-presets"],
    queryFn: listTagPresets,
  });

  const invalidateDocument = () => {
    queryClient.invalidateQueries({ queryKey: ["document", caseId, documentId] });
    queryClient.invalidateQueries({ queryKey: ["documents", caseId] });
    queryClient.invalidateQueries({ queryKey: ["tags", caseId] });
  };

  const applyMutation = useMutation({
    mutationFn: (tagId: string) => applyTag(caseId, documentId, tagId),
    onSuccess: () => {
      setSelectedTagId(null);
      invalidateDocument();
    },
  });

  const removeMutation = useMutation({
    mutationFn: (tagId: string) => removeTag(caseId, documentId, tagId),
    onSuccess: invalidateDocument,
  });

  const createMutation = useMutation({
    mutationFn: ({ name, color }: { name: string; color?: string }) =>
      createTag(caseId, name, color),
    onSuccess: (tag) => {
      setNewTagName("");
      applyMutation.mutate(tag.id);
    },
  });

  const appliedIds = new Set(appliedTags.map((t) => t.id));
  const existingNames = new Set((allTags ?? []).map((t) => t.name.toLowerCase()));
  const availableOptions = (allTags ?? [])
    .filter((t) => !appliedIds.has(t.id))
    .map((t) => ({ value: t.id, label: t.name }));
  const presetOptions = (tagPresets ?? [])
    .filter((p) => !existingNames.has(p.name.toLowerCase()))
    .map((p) => ({ value: `${PRESET_PREFIX}${p.name}`, label: `${p.name} (your preset)` }));
  const selectData =
    presetOptions.length > 0
      ? [
          { group: "Case tags", items: availableOptions },
          { group: "Your presets", items: presetOptions },
        ]
      : availableOptions;

  return (
    <Group gap="xs" wrap="wrap">
      {appliedTags.map((tag) => (
        <Badge
          key={tag.id}
          color={tag.color}
          rightSection={
            <ActionIcon
              size="xs"
              variant="transparent"
              color="white"
              onClick={() => removeMutation.mutate(tag.id)}
            >
              <IconX size={10} />
            </ActionIcon>
          }
        >
          {tag.name}
        </Badge>
      ))}
      <Select
        placeholder="Add tag"
        size="xs"
        w={160}
        searchable
        data={selectData}
        value={selectedTagId}
        onChange={(value) => {
          if (!value) return;
          if (value.startsWith(PRESET_PREFIX)) {
            const name = value.slice(PRESET_PREFIX.length);
            const preset = (tagPresets ?? []).find((p) => p.name === name);
            createMutation.mutate({ name, color: preset?.color });
          } else {
            applyMutation.mutate(value);
          }
        }}
      />
      <TextInput
        placeholder="New tag..."
        size="xs"
        w={120}
        value={newTagName}
        onChange={(e) => setNewTagName(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && newTagName.trim()) {
            createMutation.mutate({ name: newTagName.trim() });
          }
        }}
        rightSection={
          <ActionIcon
            size="xs"
            variant="transparent"
            disabled={!newTagName.trim()}
            onClick={() =>
              newTagName.trim() && createMutation.mutate({ name: newTagName.trim() })
            }
          >
            <IconPlus size={12} />
          </ActionIcon>
        }
      />
    </Group>
  );
}
