import { Badge, Group, Kbd } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { applyTag, listTags, removeTag, type TagRead } from "../api/tags";

export function TagHotkeyBar({
  caseId,
  documentId,
  appliedTags,
}: {
  caseId: string;
  documentId: string;
  appliedTags: TagRead[];
}) {
  const queryClient = useQueryClient();

  const { data: allTags } = useQuery({
    queryKey: ["tags", caseId],
    queryFn: () => listTags(caseId),
  });

  // Number keys 1-9 map to the case's tags in the same alphabetical order
  // shown everywhere else, so the mapping stays predictable as tags change.
  const hotkeyTags = (allTags ?? []).slice(0, 9);
  const appliedIds = new Set(appliedTags.map((t) => t.id));

  const invalidateDocument = () => {
    queryClient.invalidateQueries({ queryKey: ["document", caseId, documentId] });
    queryClient.invalidateQueries({ queryKey: ["documents", caseId] });
  };

  const applyMutation = useMutation({
    mutationFn: (tagId: string) => applyTag(caseId, documentId, tagId),
    onSuccess: invalidateDocument,
  });
  const removeMutation = useMutation({
    mutationFn: (tagId: string) => removeTag(caseId, documentId, tagId),
    onSuccess: invalidateDocument,
  });

  const toggle = (tagId: string) => {
    if (appliedIds.has(tagId)) {
      removeMutation.mutate(tagId);
    } else {
      applyMutation.mutate(tagId);
    }
  };

  useEffect(() => {
    if (hotkeyTags.length === 0) return;
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;
      const index = Number(e.key) - 1;
      if (Number.isInteger(index) && index >= 0 && index < hotkeyTags.length) {
        toggle(hotkeyTags[index].id);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotkeyTags, appliedTags]);

  if (hotkeyTags.length === 0) return null;

  return (
    <Group gap={6} wrap="wrap">
      {hotkeyTags.map((tag, i) => {
        const isApplied = appliedIds.has(tag.id);
        return (
          <Badge
            key={tag.id}
            variant={isApplied ? "filled" : "outline"}
            color={tag.color}
            style={{ cursor: "pointer" }}
            onClick={() => toggle(tag.id)}
            leftSection={
              <Kbd size="xs" style={{ padding: "0 4px" }}>
                {i + 1}
              </Kbd>
            }
          >
            {tag.name}
          </Badge>
        );
      })}
    </Group>
  );
}
