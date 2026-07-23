import { Alert, Badge, Group, Progress, Stack, Text } from "@mantine/core";

import type { ImportJob } from "../api/importJobs";

const STEP_ORDER = ["pending", "extracting", "parsing", "dedup", "rendering"] as const;

const STATUS_COLOR: Record<string, string> = {
  pending: "gray",
  extracting: "blue",
  parsing: "blue",
  dedup: "blue",
  rendering: "blue",
  completed: "green",
  completed_with_errors: "yellow",
  failed: "red",
};

function progressForStatus(status: ImportJob["status"]): number {
  if (status === "completed" || status === "completed_with_errors") return 100;
  if (status === "failed") return 100;
  const index = STEP_ORDER.indexOf(status as (typeof STEP_ORDER)[number]);
  if (index === -1) return 0;
  return Math.round(((index + 1) / (STEP_ORDER.length + 1)) * 100);
}

export function ImportProgressBar({ job }: { job: ImportJob }) {
  const color = STATUS_COLOR[job.status] ?? "gray";

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Text size="sm" fw={500}>
          {job.uploaded_filename}
        </Text>
        <Badge color={color}>{job.status.replace(/_/g, " ")}</Badge>
      </Group>
      <Progress value={progressForStatus(job.status)} color={color} animated={color === "blue"} />
      {job.status === "failed" && job.error_message && (
        <Alert color="red" title="Import failed">
          {job.error_message}
        </Alert>
      )}
      {(job.status === "completed" || job.status === "completed_with_errors") && (
        <Text size="sm" c="dimmed">
          {job.stats.total_items ?? 0} items — {job.stats.emails ?? 0} emails,{" "}
          {job.stats.attachments ?? 0} attachments, {job.stats.contacts ?? 0} contacts,{" "}
          {job.stats.calendar_items ?? 0} calendar items
          {typeof job.stats.duplicates === "number" && job.stats.duplicates > 0
            ? ` (${job.stats.duplicates} duplicates)`
            : ""}
          {job.stats.fallback_used ? " — used reduced-fidelity mail-only fallback" : ""}
        </Text>
      )}
    </Stack>
  );
}
