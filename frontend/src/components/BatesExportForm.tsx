import { Button, Checkbox, Group, NumberInput, Radio, Select, Stack, TextInput } from "@mantine/core";
import { useState, type FormEvent } from "react";

import type { ExportJobCreate, ExportType } from "../api/exportJobs";

export function BatesExportForm({
  reviewSetOptions,
  submitting,
  onSubmit,
}: {
  reviewSetOptions: { value: string; label: string }[];
  submitting: boolean;
  onSubmit: (payload: ExportJobCreate) => void;
}) {
  const [reviewSetId, setReviewSetId] = useState<string | null>(null);
  const [exportType, setExportType] = useState<ExportType>("production_set");
  const [applyBates, setApplyBates] = useState(true);
  const [batesPrefix, setBatesPrefix] = useState("ABC");
  const [batesStart, setBatesStart] = useState<string | number>(1);
  const [batesPadding, setBatesPadding] = useState<string | number>(6);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!reviewSetId) return;
    onSubmit({
      review_set_id: reviewSetId,
      export_type: exportType,
      apply_bates: applyBates,
      bates_prefix: batesPrefix,
      bates_start_number: Number(batesStart) || 1,
      bates_digit_padding: Number(batesPadding) || 6,
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <Stack>
        <Select
          label="Review set"
          placeholder="Select a review set to export"
          required
          data={reviewSetOptions}
          value={reviewSetId}
          onChange={setReviewSetId}
        />
        <Radio.Group
          label="Export format"
          value={exportType}
          onChange={(v) => setExportType(v as ExportType)}
        >
          <Group mt="xs">
            <Radio value="production_set" label="Bates-numbered production set (one PDF per document)" />
            <Radio value="combined_pdf" label="Single combined PDF" />
          </Group>
        </Radio.Group>
        <Checkbox
          label="Apply Bates numbering"
          checked={applyBates}
          onChange={(e) => setApplyBates(e.currentTarget.checked)}
        />
        {applyBates && (
          <Group>
            <TextInput
              label="Prefix"
              value={batesPrefix}
              onChange={(e) => setBatesPrefix(e.currentTarget.value)}
              w={120}
            />
            <NumberInput
              label="Start number"
              value={batesStart}
              onChange={setBatesStart}
              min={1}
              w={140}
            />
            <NumberInput
              label="Digit padding"
              value={batesPadding}
              onChange={setBatesPadding}
              min={1}
              max={12}
              w={140}
            />
          </Group>
        )}
        <Button type="submit" loading={submitting} disabled={!reviewSetId}>
          Start export
        </Button>
      </Stack>
    </form>
  );
}
