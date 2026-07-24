import { MultiSelect, Select, Stack, Text } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listCodingFields,
  listDocumentCodingValues,
  setDocumentCodingValue,
  type DocumentCodingValueRead,
} from "../api/codingFields";

export function CodingForm({ caseId, documentId }: { caseId: string; documentId: string }) {
  const queryClient = useQueryClient();
  const valuesKey = ["document-coding-values", caseId, documentId];

  const { data: fields } = useQuery({
    queryKey: ["coding-fields", caseId],
    queryFn: () => listCodingFields(caseId),
  });

  const { data: values } = useQuery({
    queryKey: valuesKey,
    queryFn: () => listDocumentCodingValues(caseId, documentId),
  });

  // Optimistically write the new selection into the cache before the request
  // resolves. Without this, a second click before the first PUT's response
  // (and refetch) lands would compute its "current values" from stale data
  // and silently drop the just-made selection.
  const setMutation = useMutation({
    mutationFn: ({ fieldId, values }: { fieldId: string; values: string[] }) =>
      setDocumentCodingValue(caseId, documentId, fieldId, values),
    onMutate: async ({ fieldId, values: newValues }) => {
      await queryClient.cancelQueries({ queryKey: valuesKey });
      const previous = queryClient.getQueryData<DocumentCodingValueRead[]>(valuesKey);
      queryClient.setQueryData<DocumentCodingValueRead[]>(valuesKey, (old) => [
        ...(old ?? []).filter((v) => v.coding_field_id !== fieldId),
        ...newValues.map((value) => ({
          id: `optimistic-${fieldId}-${value}`,
          document_id: documentId,
          coding_field_id: fieldId,
          value,
          set_by_id: "",
          set_at: new Date().toISOString(),
        })),
      ]);
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(valuesKey, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: valuesKey }),
  });

  if (!fields || fields.length === 0) return null;

  const valuesByField = new Map<string, string[]>();
  for (const v of values ?? []) {
    valuesByField.set(v.coding_field_id, [...(valuesByField.get(v.coding_field_id) ?? []), v.value]);
  }

  return (
    <Stack gap="xs" mt="md">
      <Text size="sm" fw={600}>
        Coding
      </Text>
      {fields.map((field) =>
        field.field_type === "single_select" ? (
          <Select
            key={field.id}
            label={field.name}
            size="xs"
            w={260}
            clearable
            data={field.options}
            value={valuesByField.get(field.id)?.[0] ?? null}
            onChange={(value) =>
              setMutation.mutate({ fieldId: field.id, values: value ? [value] : [] })
            }
          />
        ) : (
          <MultiSelect
            key={field.id}
            label={field.name}
            size="xs"
            w={340}
            clearable
            data={field.options}
            value={valuesByField.get(field.id) ?? []}
            onChange={(newValues) => setMutation.mutate({ fieldId: field.id, values: newValues })}
          />
        ),
      )}
    </Stack>
  );
}
