import {
  Anchor,
  Badge,
  Button,
  Card,
  Container,
  FileInput,
  Group,
  List,
  Modal,
  Progress,
  Select,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import {
  addMember,
  createCustodian,
  getCase,
  getCaseStats,
  listCustodians,
  listMembers,
  type CaseRole,
} from "../api/cases";
import { createImportJob, listImportJobs, TERMINAL_STATUSES } from "../api/importJobs";
import { listDocuments } from "../api/documents";
import {
  addDocumentsToReviewSet,
  createReviewSet,
  listReviewSets,
} from "../api/reviewSets";
import { ImportProgressBar } from "../components/ImportProgressBar";

function StepCard({
  number,
  title,
  subtitle,
  children,
}: {
  number: number;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card withBorder radius="md" p="lg" mb="md">
      <Group align="flex-start" mb="sm">
        <ThemeIcon radius="xl" size={32}>
          {number}
        </ThemeIcon>
        <div style={{ flex: 1 }}>
          <Title order={4}>{title}</Title>
          {subtitle && (
            <Text size="sm" c="dimmed">
              {subtitle}
            </Text>
          )}
        </div>
      </Group>
      {children}
    </Card>
  );
}

export function CaseDetailPage() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const enabled = caseId !== "";

  const [memberModal, { open: openMemberModal, close: closeMemberModal }] = useDisclosure(false);
  const [custodianModal, { open: openCustodianModal, close: closeCustodianModal }] =
    useDisclosure(false);
  const [importModal, { open: openImportModal, close: closeImportModal }] = useDisclosure(false);
  const [addToReviewModal, { open: openAddToReviewModal, close: closeAddToReviewModal }] =
    useDisclosure(false);
  const [reviewSetModal, { open: openReviewSetModal, close: closeReviewSetModal }] =
    useDisclosure(false);

  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState<CaseRole>("reviewer");
  const [custodianName, setCustodianName] = useState("");
  const [custodianEmail, setCustodianEmail] = useState("");
  const [importCustodianId, setImportCustodianId] = useState<string | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [addToReviewChoice, setAddToReviewChoice] = useState<string | null>(null);
  const [newReviewSetName, setNewReviewSetName] = useState("");
  const [reviewSetName, setReviewSetName] = useState("");

  const { data: caseData } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId),
    enabled,
  });
  const { data: members } = useQuery({
    queryKey: ["case-members", caseId],
    queryFn: () => listMembers(caseId),
    enabled,
  });
  const { data: custodians } = useQuery({
    queryKey: ["custodians", caseId],
    queryFn: () => listCustodians(caseId),
    enabled,
  });
  const { data: importJobs } = useQuery({
    queryKey: ["import-jobs", caseId],
    queryFn: () => listImportJobs(caseId),
    enabled,
    refetchInterval: (query) => {
      const jobs = query.state.data ?? [];
      return jobs.some((j) => !TERMINAL_STATUSES.includes(j.status)) ? 2000 : false;
    },
  });
  const { data: stats } = useQuery({
    queryKey: ["case-stats", caseId],
    queryFn: () => getCaseStats(caseId),
    enabled,
    refetchInterval: (query) => {
      const s = query.state.data;
      const stillWorking = (importJobs ?? []).some((j) => !TERMINAL_STATUSES.includes(j.status));
      const stillRendering = s ? s.documents_pending_render > 0 : false;
      return stillWorking || stillRendering ? 2000 : false;
    },
  });
  const { data: reviewSets } = useQuery({
    queryKey: ["review-sets", caseId],
    queryFn: () => listReviewSets(caseId),
    enabled,
  });

  const isAdmin = caseData?.my_role === "admin";
  const canEdit = caseData?.my_role === "admin" || caseData?.my_role === "reviewer";

  const addMemberMutation = useMutation({
    mutationFn: () => addMember(caseId, memberEmail, memberRole),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-members", caseId] });
      setMemberEmail("");
      closeMemberModal();
    },
  });

  const addCustodianMutation = useMutation({
    mutationFn: () => createCustodian(caseId, custodianName, custodianEmail),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["custodians", caseId] });
      setCustodianName("");
      setCustodianEmail("");
      closeCustodianModal();
    },
  });

  const importMutation = useMutation({
    mutationFn: () => {
      if (!importCustodianId || !importFile) {
        throw new Error("Select a custodian and a .pst file");
      }
      return createImportJob(caseId, importCustodianId, importFile);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["import-jobs", caseId] });
      setImportFile(null);
      setImportError(null);
      closeImportModal();
    },
    onError: (err: Error) => setImportError(err.message),
  });

  const addAllToReviewMutation = useMutation({
    mutationFn: async () => {
      let reviewSetId = addToReviewChoice;
      if (reviewSetId === "__new__") {
        const created = await createReviewSet(caseId, newReviewSetName || "Review set");
        reviewSetId = created.id;
      }
      if (!reviewSetId) throw new Error("Choose or name a review set");
      const primaryDocs = await listDocuments(caseId, {
        dedup_status: "primary",
        page_size: 5000,
      });
      return addDocumentsToReviewSet(
        caseId,
        reviewSetId,
        primaryDocs.map((d) => d.id),
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-sets", caseId] });
      setAddToReviewChoice(null);
      setNewReviewSetName("");
      closeAddToReviewModal();
    },
  });

  const createReviewSetMutation = useMutation({
    mutationFn: () => createReviewSet(caseId, reviewSetName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-sets", caseId] });
      setReviewSetName("");
      closeReviewSetModal();
    },
  });

  return (
    <Container size="md" py="xl">
      <Anchor component={Link} to="/cases" size="sm">
        ← Back to cases
      </Anchor>
      <Group justify="space-between" mt="sm" mb="xs">
        <Title order={2}>{caseData?.name}</Title>
        <Group>
          {caseData?.my_role && <Badge>{caseData.my_role}</Badge>}
          <Button component={Link} to={`/cases/${caseId}/documents`} size="xs" variant="subtle">
            All documents
          </Button>
          <Button size="xs" variant="subtle" onClick={openMemberModal}>
            Members
          </Button>
          <Button component={Link} to={`/cases/${caseId}/coding-fields`} size="xs" variant="subtle">
            Coding fields
          </Button>
          {isAdmin && (
            <Button component={Link} to={`/cases/${caseId}/audit-log`} size="xs" variant="subtle">
              Audit log
            </Button>
          )}
        </Group>
      </Group>
      <Text c="dimmed" mb="xl">
        {caseData?.description}
      </Text>

      <StepCard
        number={1}
        title="Custodians & import"
        subtitle="Add everyone whose mailbox you're reviewing, then import their PST files. Add as many custodians and PSTs as you need — nothing here is one-shot."
      >
        <Group justify="space-between" mb="xs">
          <Text fw={500} size="sm">
            Custodians
          </Text>
          {canEdit && (
            <Button size="xs" variant="light" onClick={openCustodianModal}>
              Add custodian
            </Button>
          )}
        </Group>
        <List size="sm" mb="md">
          {custodians?.map((c) => (
            <List.Item key={c.id}>
              {c.name} {c.email && `(${c.email})`}
            </List.Item>
          ))}
          {custodians?.length === 0 && <Text c="dimmed">No custodians yet.</Text>}
        </List>

        <Group justify="space-between" mb="xs">
          <Text fw={500} size="sm">
            Imports
          </Text>
          {canEdit && (
            <Button
              size="xs"
              variant="light"
              onClick={openImportModal}
              disabled={!custodians || custodians.length === 0}
            >
              Import a PST
            </Button>
          )}
        </Group>
        <Stack gap="sm">
          {importJobs?.map((job) => <ImportProgressBar key={job.id} job={job} />)}
          {importJobs?.length === 0 && (
            <Text c="dimmed" size="sm">
              No imports yet — add a custodian above, then import their PST.
            </Text>
          )}
        </Stack>
      </StepCard>

      <StepCard
        number={2}
        title="De-duplication & rendering"
        subtitle="Runs automatically as each PST finishes importing — nothing to do here but watch."
      >
        {stats && stats.documents_total > 0 ? (
          <Stack gap={6}>
            <Text size="sm">
              <b>{stats.documents_total}</b> documents ({stats.documents_by_type.email ?? 0} email,{" "}
              {stats.documents_by_type.attachment ?? 0} attachment,{" "}
              {stats.documents_by_type.contact ?? 0} contact,{" "}
              {stats.documents_by_type.calendar ?? 0} calendar)
            </Text>
            <Text size="sm">
              <b>{stats.documents_primary}</b> unique, <b>{stats.documents_duplicate}</b> duplicates
              (skipped from review automatically)
            </Text>
            <Text size="sm" mb={4}>
              Rendered for viewing: {stats.documents_rendered} / {stats.documents_primary}
              {stats.documents_render_failed > 0 &&
                ` (${stats.documents_render_failed} failed to render)`}
            </Text>
            <Progress
              value={
                stats.documents_primary > 0
                  ? Math.round(
                      ((stats.documents_rendered + stats.documents_render_failed) /
                        stats.documents_primary) *
                        100,
                    )
                  : 0
              }
              color={stats.documents_pending_render > 0 ? "blue" : "green"}
              animated={stats.documents_pending_render > 0}
            />
          </Stack>
        ) : (
          <Text c="dimmed" size="sm">
            Nothing to de-duplicate yet — import a PST above first.
          </Text>
        )}
      </StepCard>

      <StepCard
        number={3}
        title="Add documents to review"
        subtitle="Add every unique document to a review set in one go, or hand-pick a subset from the document list."
      >
        <Group>
          {canEdit && (
            <Button
              size="xs"
              onClick={openAddToReviewModal}
              disabled={!stats || stats.documents_primary === 0}
            >
              Add all documents to a review set
            </Button>
          )}
          <Button
            size="xs"
            variant="light"
            component={Link}
            to={`/cases/${caseId}/documents`}
          >
            Hand-pick documents instead
          </Button>
        </Group>
      </StepCard>

      <StepCard
        number={4}
        title="Review"
        subtitle="Tagging, redaction, and review status all happen inside a review set."
      >
        <Group justify="space-between" mb="xs">
          <Text fw={500} size="sm">
            Review sets
          </Text>
          {canEdit && (
            <Button size="xs" variant="light" onClick={openReviewSetModal}>
              New review set
            </Button>
          )}
        </Group>
        <Stack gap="xs">
          {reviewSets?.map((rs) => (
            <Group key={rs.id} justify="space-between">
              <Text size="sm">{rs.name}</Text>
              <Button
                size="xs"
                variant="subtle"
                component={Link}
                to={`/cases/${caseId}/review-sets/${rs.id}`}
              >
                Open
              </Button>
            </Group>
          ))}
          {reviewSets?.length === 0 && (
            <Text c="dimmed" size="sm">
              No review sets yet.
            </Text>
          )}
        </Stack>
        <Button
          mt="md"
          size="xs"
          variant="outline"
          component={Link}
          to={`/cases/${caseId}/export`}
        >
          Export a review set →
        </Button>
      </StepCard>

      <Modal opened={memberModal} onClose={closeMemberModal} title="Members">
        <List size="sm" mb="md">
          {members?.map((m) => (
            <List.Item key={m.id}>
              {m.email} — <Badge size="sm">{m.role}</Badge>
            </List.Item>
          ))}
        </List>
        {isAdmin && (
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              addMemberMutation.mutate();
            }}
          >
            <Stack>
              <TextInput
                label="Email"
                description="They must already have a registered account"
                type="email"
                required
                value={memberEmail}
                onChange={(e) => setMemberEmail(e.currentTarget.value)}
              />
              <Select
                label="Role"
                data={["admin", "reviewer", "viewer"]}
                required
                allowDeselect={false}
                value={memberRole}
                onChange={(value) => setMemberRole(value as CaseRole)}
              />
              {addMemberMutation.isError && (
                <Text c="red" size="sm">
                  Couldn't add that member — check the email is registered and not already on this
                  case.
                </Text>
              )}
              <Button type="submit" loading={addMemberMutation.isPending}>
                Add
              </Button>
            </Stack>
          </form>
        )}
      </Modal>

      <Modal opened={custodianModal} onClose={closeCustodianModal} title="Add custodian">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            addCustodianMutation.mutate();
          }}
        >
          <Stack>
            <TextInput
              label="Name"
              required
              value={custodianName}
              onChange={(e) => setCustodianName(e.currentTarget.value)}
            />
            <TextInput
              label="Email"
              value={custodianEmail}
              onChange={(e) => setCustodianEmail(e.currentTarget.value)}
            />
            <Button type="submit" loading={addCustodianMutation.isPending}>
              Add
            </Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={importModal} onClose={closeImportModal} title="Import a PST">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            importMutation.mutate();
          }}
        >
          <Stack>
            <Select
              label="Custodian"
              placeholder="Select a custodian"
              required
              data={(custodians ?? []).map((c) => ({ value: c.id, label: c.name }))}
              value={importCustodianId}
              onChange={setImportCustodianId}
            />
            <FileInput
              label="PST file"
              placeholder="Choose a .pst file"
              required
              accept=".pst"
              value={importFile}
              onChange={setImportFile}
            />
            {importError && (
              <Text c="red" size="sm">
                {importError}
              </Text>
            )}
            <Button type="submit" loading={importMutation.isPending}>
              Upload and start import
            </Button>
          </Stack>
        </form>
      </Modal>

      <Modal
        opened={addToReviewModal}
        onClose={closeAddToReviewModal}
        title="Add all documents to a review set"
      >
        <Stack>
          <Text size="sm" c="dimmed">
            Adds all {stats?.documents_primary ?? 0} unique documents (duplicates are skipped
            automatically).
          </Text>
          <Select
            label="Review set"
            placeholder="Choose an existing set, or create a new one"
            data={[
              ...(reviewSets ?? []).map((rs) => ({ value: rs.id, label: rs.name })),
              { value: "__new__", label: "+ Create a new review set" },
            ]}
            value={addToReviewChoice}
            onChange={setAddToReviewChoice}
          />
          {addToReviewChoice === "__new__" && (
            <TextInput
              label="New review set name"
              required
              value={newReviewSetName}
              onChange={(e) => setNewReviewSetName(e.currentTarget.value)}
            />
          )}
          <Button
            loading={addAllToReviewMutation.isPending}
            disabled={!addToReviewChoice}
            onClick={() => addAllToReviewMutation.mutate()}
          >
            Add all documents
          </Button>
        </Stack>
      </Modal>

      <Modal opened={reviewSetModal} onClose={closeReviewSetModal} title="New review set">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            createReviewSetMutation.mutate();
          }}
        >
          <Stack>
            <TextInput
              label="Name"
              required
              value={reviewSetName}
              onChange={(e) => setReviewSetName(e.currentTarget.value)}
            />
            <Button type="submit" loading={createReviewSetMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>
    </Container>
  );
}
