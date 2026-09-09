import {
  Button,
  Container,
  FileInput,
  Group,
  Select,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconUpload } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { listCustodians } from "../api/cases";
import { createImportJob, listImportJobs, TERMINAL_STATUSES } from "../api/importJobs";
import { EmptyState } from "../components/EmptyState";
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
      <Title order={2} mb="lg">
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
        {jobs?.length === 0 && (
          <EmptyState
            icon={IconUpload}
            title="No imports yet"
            description="Select a custodian and upload a .pst file above to start an import."
          />
        )}
      </Stack>
    </Container>
  );
}
