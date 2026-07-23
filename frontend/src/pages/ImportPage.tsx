import {
  Anchor,
  Button,
  Container,
  FileInput,
  Group,
  Select,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { createImportJob, listImportJobs, TERMINAL_STATUSES } from "../api/importJobs";
import { listCustodians } from "../api/cases";
import { ImportProgressBar } from "../components/ImportProgressBar";

export function ImportPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const [custodianId, setCustodianId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: custodians } = useQuery({
    queryKey: ["custodians", caseId],
    queryFn: () => listCustodians(caseId),
    enabled: caseId !== "",
  });

  const { data: jobs } = useQuery({
    queryKey: ["import-jobs", caseId],
    queryFn: () => listImportJobs(caseId),
    enabled: caseId !== "",
    refetchInterval: (query) => {
      const currentJobs = query.state.data ?? [];
      const stillRunning = currentJobs.some((j) => !TERMINAL_STATUSES.includes(j.status));
      return stillRunning ? 2000 : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!custodianId || !file) throw new Error("Select a custodian and a .pst file");
      return createImportJob(caseId, custodianId, file);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["import-jobs", caseId] });
      setFile(null);
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    uploadMutation.mutate();
  };

  return (
    <Container size="md" py="xl">
      <Anchor component={Link} to={`/cases/${caseId}`} size="sm">
        ← Back to case
      </Anchor>
      <Title order={2} mt="sm" mb="lg">
        Import PST
      </Title>

      <form onSubmit={handleSubmit}>
        <Stack mb="xl">
          <Select
            label="Custodian"
            placeholder="Select a custodian"
            required
            data={(custodians ?? []).map((c) => ({ value: c.id, label: c.name }))}
            value={custodianId}
            onChange={setCustodianId}
          />
          <FileInput
            label="PST file"
            placeholder="Choose a .pst file"
            required
            accept=".pst"
            value={file}
            onChange={setFile}
          />
          {error && <Text c="red">{error}</Text>}
          <Group>
            <Button type="submit" loading={uploadMutation.isPending}>
              Upload and start import
            </Button>
          </Group>
        </Stack>
      </form>

      <Title order={4} mb="sm">
        Import history
      </Title>
      <Stack>
        {jobs?.map((job) => <ImportProgressBar key={job.id} job={job} />)}
        {jobs?.length === 0 && <Text c="dimmed">No imports yet.</Text>}
      </Stack>
    </Container>
  );
}
