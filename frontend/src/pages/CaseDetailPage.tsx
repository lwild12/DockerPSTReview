import {
  Badge,
  Button,
  Card,
  Checkbox,
  Container,
  FileInput,
  Group,
  List,
  Modal,
  Progress,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getAiReviewSummary, runAiReview, updateAiReviewCriteria } from "../api/aiReview";
import { getCaseAnalytics, recomputeCaseAnalytics } from "../api/analytics";
import {
  addMember,
  createCustodian,
  deleteCase,
  getCase,
  getCaseStats,
  listCustodians,
  listMembers,
  type CaseRole,
} from "../api/cases";
import { createImportJob, listImportJobs, TERMINAL_STATUSES } from "../api/importJobs";
import { listAllDocuments } from "../api/documents";
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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const enabled = caseId !== "";

  const [deleteModal, { open: openDeleteModal, close: closeDeleteModal }] = useDisclosure(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
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
  const [excludeRedundant, setExcludeRedundant] = useState(true);
  const [excludeNearDuplicates, setExcludeNearDuplicates] = useState(true);
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
  const { data: analytics } = useQuery({
    queryKey: ["case-analytics", caseId],
    queryFn: () => getCaseAnalytics(caseId),
    enabled,
  });
  const { data: aiReview } = useQuery({
    queryKey: ["ai-review", caseId],
    queryFn: () => getAiReviewSummary(caseId),
    enabled,
    refetchInterval: (query) => {
      const s = query.state.data;
      const stillRunning = s ? s.running_count > 0 || s.queued_count > 0 : false;
      return stillRunning ? 2000 : false;
    },
  });

  const isAdmin = caseData?.my_role === "admin";
  const canEdit = caseData?.my_role === "admin" || caseData?.my_role === "reviewer";

  const [aiCriteria, setAiCriteria] = useState("");
  const [aiCriteriaInitialized, setAiCriteriaInitialized] = useState(false);
  useEffect(() => {
    if (aiCriteriaInitialized || !aiReview) return;
    setAiCriteria(aiReview.criteria);
    setAiCriteriaInitialized(true);
  }, [aiReview, aiCriteriaInitialized]);
  const [rescoreAll, setRescoreAll] = useState(false);

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
      const primaryDocs = await listAllDocuments(caseId, { dedup_status: "primary" });
      let toAdd = primaryDocs;
      if (excludeRedundant) {
        toAdd = toAdd.filter((d) => !(d.doc_type === "email" && !d.is_inclusive_email));
      }
      if (excludeNearDuplicates) {
        const seenClusters = new Set<string>();
        toAdd = toAdd.filter((d) => {
          if (!d.near_duplicate_cluster_id) return true;
          if (seenClusters.has(d.near_duplicate_cluster_id)) return false;
          seenClusters.add(d.near_duplicate_cluster_id);
          return true;
        });
      }
      return addDocumentsToReviewSet(
        caseId,
        reviewSetId,
        toAdd.map((d) => d.id),
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

  const recomputeAnalyticsMutation = useMutation({
    mutationFn: () => recomputeCaseAnalytics(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-analytics", caseId] });
    },
  });

  const saveAiCriteriaMutation = useMutation({
    mutationFn: () => updateAiReviewCriteria(caseId, aiCriteria),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-review", caseId] }),
  });

  const runAiReviewMutation = useMutation({
    mutationFn: () => runAiReview(caseId, rescoreAll),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-review", caseId] }),
  });

  const deleteCaseMutation = useMutation({
    mutationFn: () => deleteCase(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      navigate("/cases");
    },
  });

  return (
    <Container size="md" py="xl">
      <Group justify="space-between" mb="xs">
        <Title order={2}>{caseData?.name}</Title>
        <Group>
          {caseData?.my_role && <Badge>{caseData.my_role}</Badge>}
          <Button size="xs" variant="subtle" onClick={openMemberModal}>
            Members
          </Button>
          {isAdmin && (
            <Button size="xs" variant="subtle" color="red" onClick={openDeleteModal}>
              Delete case
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

      <Card withBorder radius="md" p="lg" mb="md">
        <Group justify="space-between" align="flex-start" mb="xs">
          <div>
            <Title order={4}>Review analytics</Title>
            <Text size="sm" c="dimmed">
              Finds near-duplicate documents and marks redundant thread messages (ones whose
              content is fully quoted in a later message) so they can be filtered out of review.
              Run this whenever you want it refreshed — it doesn't run automatically.
            </Text>
          </div>
          {canEdit && (
            <Button
              size="xs"
              variant="light"
              onClick={() => recomputeAnalyticsMutation.mutate()}
              loading={recomputeAnalyticsMutation.isPending}
              disabled={!stats || stats.documents_total === 0}
            >
              {analytics?.computed_at ? "Recompute" : "Compute now"}
            </Button>
          )}
        </Group>
        {analytics?.computed_at ? (
          <Text size="sm">
            <b>{analytics.near_duplicate_cluster_count}</b> near-duplicate group
            {analytics.near_duplicate_cluster_count === 1 ? "" : "s"}, <b>
              {analytics.non_inclusive_email_count}
            </b>{" "}
            redundant thread message{analytics.non_inclusive_email_count === 1 ? "" : "s"} — last
            computed {new Date(analytics.computed_at).toLocaleString()}
          </Text>
        ) : (
          <Text size="sm" c="dimmed">
            Not computed yet for this case.
          </Text>
        )}
      </Card>

      <Card withBorder radius="md" p="lg" mb="md">
        <Title order={4} mb="xs">
          AI pre-review
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          Scores each document against your relevance criteria using a connected Ollama model.
          Scores are advisory only, meant to assist human review — never a final relevance call.
        </Text>
        {aiReview && !aiReview.ollama_configured && (
          <Text size="sm" c="orange" mb="sm">
            Ollama isn't configured yet — an admin can set it up on the Admin page.
          </Text>
        )}
        <Textarea
          label="Relevance criteria"
          description="Describe what makes a document relevant to this case."
          minRows={3}
          mb="sm"
          value={aiCriteria}
          onChange={(e) => setAiCriteria(e.currentTarget.value)}
          disabled={!canEdit}
        />
        {canEdit && (
          <Button
            size="xs"
            variant="light"
            mb="sm"
            onClick={() => saveAiCriteriaMutation.mutate()}
            loading={saveAiCriteriaMutation.isPending}
            disabled={!aiReview || aiCriteria === aiReview.criteria}
          >
            Save criteria
          </Button>
        )}
        {aiReview && (
          <Text size="sm" mb="sm">
            <b>{aiReview.candidate_count}</b> candidate document
            {aiReview.candidate_count === 1 ? "" : "s"}
            {aiReview.candidate_count > 0 && (
              <>
                {" "}
                — <b>{aiReview.completed_count}</b> scored, <b>{aiReview.failed_count}</b> failed,{" "}
                <b>{aiReview.unscored_count}</b> not yet scored
              </>
            )}
            {aiReview.last_run_completed_at && (
              <> — last run completed {new Date(aiReview.last_run_completed_at).toLocaleString()}</>
            )}
          </Text>
        )}
        {isAdmin && (
          <Group gap="sm">
            <Checkbox
              label="Rescore everything"
              description="Otherwise only new, failed, or criteria-changed documents are (re)scored."
              checked={rescoreAll}
              onChange={(e) => setRescoreAll(e.currentTarget.checked)}
            />
            <Button
              size="xs"
              onClick={() => runAiReviewMutation.mutate()}
              loading={
                runAiReviewMutation.isPending ||
                (aiReview?.running_count ?? 0) > 0 ||
                (aiReview?.queued_count ?? 0) > 0
              }
              disabled={!aiReview?.ollama_configured || !aiReview?.candidate_count}
            >
              Run AI review
            </Button>
          </Group>
        )}
        {runAiReviewMutation.isError && (
          <Text c="red" size="sm" mt="xs">
            Couldn't start the run — check that Ollama is configured correctly.
          </Text>
        )}
      </Card>

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
          <Checkbox
            label="Exclude redundant thread messages"
            description="Emails whose content is fully quoted in a later message in the same thread"
            checked={excludeRedundant}
            onChange={(e) => setExcludeRedundant(e.currentTarget.checked)}
          />
          <Checkbox
            label="Exclude near-duplicates"
            description="Keep only one document from each near-duplicate group"
            checked={excludeNearDuplicates}
            onChange={(e) => setExcludeNearDuplicates(e.currentTarget.checked)}
          />
          {(excludeRedundant || excludeNearDuplicates) && !analytics?.computed_at && (
            <Text size="xs" c="orange">
              Review analytics hasn't been computed for this case yet, so these won't exclude
              anything right now — run it above first.
            </Text>
          )}
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

      <Modal
        opened={deleteModal}
        onClose={() => {
          setDeleteConfirmText("");
          closeDeleteModal();
        }}
        title="Delete case"
      >
        <Stack>
          <Text size="sm">
            This permanently deletes <strong>{caseData?.name}</strong> and everything in it —
            every imported document, review set, tag, and coding value. This can't be undone.
          </Text>
          <TextInput
            label={`Type "${caseData?.name}" to confirm`}
            value={deleteConfirmText}
            onChange={(e) => setDeleteConfirmText(e.currentTarget.value)}
          />
          {deleteCaseMutation.isError && (
            <Text c="red" size="sm">
              Couldn't delete this case — try again.
            </Text>
          )}
          <Button
            color="red"
            disabled={deleteConfirmText !== caseData?.name}
            loading={deleteCaseMutation.isPending}
            onClick={() => deleteCaseMutation.mutate()}
          >
            Delete case permanently
          </Button>
        </Stack>
      </Modal>
    </Container>
  );
}
