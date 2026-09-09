import { Alert, Anchor, Badge, Collapse, Group, Progress, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listFailedDocuments, type ImportJob } from "../api/importJobs";

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
  const isRendering = job.status === "rendering" && job.documents_total > 0;
  const renderedSoFar = job.documents_rendered + job.documents_render_failed;
  const progress = isRendering
    ? Math.round((renderedSoFar / job.documents_total) * 100)
    : progressForStatus(job.status);

  const [detailsOpened, { toggle: toggleDetails }] = useDisclosure(false);
  const parseErrorDetails = job.stats.parse_error_details ?? [];
  const totalFailures = (job.stats.parse_errors ?? 0) + job.documents_render_failed;
  const isTerminal = job.status === "completed" || job.status === "completed_with_errors";

  const { data: failedDocs } = useQuery({
    queryKey: ["import-job-failed-documents", job.case_id, job.id],
    queryFn: () => listFailedDocuments(job.case_id, job.id),
    enabled: detailsOpened && job.documents_render_failed > 0,
  });

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Text size="sm" fw={500}>
          {job.uploaded_filename}
        </Text>
        <Badge color={color}>{job.status.replace(/_/g, " ")}</Badge>
      </Group>
      <Progress value={progress} color={color} animated={color === "blue"} />
      {isRendering && (
        <Text size="xs" c="dimmed">
          Rendering documents: {renderedSoFar} / {job.documents_total}
          {job.documents_render_failed > 0 && ` (${job.documents_render_failed} failed)`}
        </Text>
      )}
      {job.status === "failed" && job.error_message && (
        <Alert color="red" title="Import failed">
          {job.error_message}
        </Alert>
      )}
      {isTerminal && (
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
      {isTerminal && totalFailures > 0 && (
        <>
          <Anchor size="xs" onClick={toggleDetails}>
            {detailsOpened ? "Hide" : "View"} {totalFailures} failed item
            {totalFailures > 1 ? "s" : ""}
          </Anchor>
          <Collapse in={detailsOpened}>
            <Stack gap={4} mt={4}>
              {parseErrorDetails.map((detail, i) => (
                <Text key={i} size="xs" c="dimmed">
                  <Text span fw={600}>
                    {detail.folder_path || "(unknown folder)"}
                  </Text>{" "}
                  ({detail.doc_type}): {detail.error}
                </Text>
              ))}
              {failedDocs?.map((doc) => (
                <Anchor
                  key={doc.id}
                  component={Link}
                  to={`/cases/${job.case_id}/documents/${doc.id}`}
                  size="xs"
                >
                  {doc.subject || "(no subject)"} — {doc.render_error || doc.ocr_error}
                </Anchor>
              ))}
            </Stack>
          </Collapse>
        </>
      )}
    </Stack>
  );
}
