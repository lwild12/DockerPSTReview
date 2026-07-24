import { Anchor, Badge, Button, Container, Group, Stack, Text, Title } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import {
  batesLabel,
  createExportJob,
  exportJobDownloadUrl,
  listExportJobs,
  EXPORT_TERMINAL_STATUSES,
  type ExportJobCreate,
} from "../api/exportJobs";
import { listReviewSets } from "../api/reviewSets";
import { BatesExportForm } from "../components/BatesExportForm";

const STATUS_COLOR: Record<string, string> = {
  pending: "gray",
  running: "blue",
  completed: "green",
  failed: "red",
};

export function ExportPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const enabled = caseId !== "";

  const { data: reviewSets } = useQuery({
    queryKey: ["review-sets", caseId],
    queryFn: () => listReviewSets(caseId),
    enabled,
  });

  const { data: jobs } = useQuery({
    queryKey: ["export-jobs", caseId],
    queryFn: () => listExportJobs(caseId),
    enabled,
    refetchInterval: (query) => {
      const currentJobs = query.state.data ?? [];
      const stillRunning = currentJobs.some((j) => !EXPORT_TERMINAL_STATUSES.includes(j.status));
      return stillRunning ? 2000 : false;
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: ExportJobCreate) => createExportJob(caseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["export-jobs", caseId] }),
  });

  return (
    <Container size="md" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}`} size="sm">
        ← Back to case
      </Anchor>
      <Title order={2} mt="sm" mb="lg">
        Export
      </Title>

      <BatesExportForm
        caseId={caseId}
        reviewSetOptions={(reviewSets ?? []).map((rs) => ({ value: rs.id, label: rs.name }))}
        submitting={createMutation.isPending}
        onSubmit={(payload) => createMutation.mutate(payload)}
        completedExportCount={(jobs ?? []).filter((j) => j.status === "completed").length}
      />

      <Title order={4} mt="xl" mb="sm">
        Export history
      </Title>
      <Stack>
        {jobs?.map((job) => (
          <Group key={job.id} justify="space-between" wrap="nowrap">
            <div>
              <Text size="sm" fw={600}>
                Production {job.production_number}
                <Text span fw={400} c="dimmed">
                  {" "}
                  — {job.export_type === "production_set" ? "Production set" : "Combined PDF"}
                </Text>
              </Text>
              {job.apply_bates && (
                <Text size="xs" c="dimmed">
                  {batesLabel(job.bates_prefix, job.bates_start_number, job.bates_digit_padding)}
                  {job.bates_end_number != null &&
                    job.bates_end_number > job.bates_start_number + 1 &&
                    ` – ${batesLabel(job.bates_prefix, job.bates_end_number - 1, job.bates_digit_padding)}`}
                </Text>
              )}
              <Text size="xs" c="dimmed">
                {new Date(job.created_at).toLocaleString()} — {job.document_ids.length} documents
              </Text>
              {job.status === "failed" && job.error_message && (
                <Text size="xs" c="red">
                  {job.error_message}
                </Text>
              )}
            </div>
            <Group>
              <Badge color={STATUS_COLOR[job.status]}>{job.status}</Badge>
              {job.status === "completed" && (
                <Button
                  size="xs"
                  component="a"
                  href={exportJobDownloadUrl(caseId, job.id)}
                  target="_blank"
                >
                  Download
                </Button>
              )}
            </Group>
          </Group>
        ))}
        {jobs?.length === 0 && <Text c="dimmed">No exports yet.</Text>}
      </Stack>
    </Container>
  );
}
