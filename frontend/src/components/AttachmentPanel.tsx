import { Anchor, Badge, Group, NavLink, Stack, Text, Title } from "@mantine/core";
import { IconDownload, IconPaperclip } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  documentNativeFileUrl,
  getDocument,
  listDocumentAttachments,
  type DocumentDetail,
} from "../api/documents";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AttachmentPanel({
  caseId,
  document,
  reviewSetId,
}: {
  caseId: string;
  document: DocumentDetail;
  reviewSetId?: string;
}) {
  const isAttachment = document.doc_type === "attachment";
  const parentId = document.parent_document_id;
  const familyRootId = isAttachment && parentId ? parentId : document.id;

  const { data: parent } = useQuery({
    queryKey: ["document", caseId, parentId],
    queryFn: () => getDocument(caseId, parentId as string),
    enabled: isAttachment && !!parentId,
  });

  const { data: attachments } = useQuery({
    queryKey: ["document-attachments", caseId, familyRootId],
    queryFn: () => listDocumentAttachments(caseId, familyRootId),
  });

  const linkTo = (id: string) =>
    reviewSetId ? `/cases/${caseId}/documents/${id}?reviewSet=${reviewSetId}` : `/cases/${caseId}/documents/${id}`;

  return (
    <Stack gap="xs">
      <Title order={5}>Attachments</Title>
      {isAttachment && (
        <div>
          <Text size="xs" c="dimmed">
            Attached to
          </Text>
          {parent ? (
            <Anchor component={Link} to={linkTo(parent.id)} size="sm">
              {parent.subject || "(no subject)"}
            </Anchor>
          ) : (
            <Text size="sm" c="dimmed">
              —
            </Text>
          )}
        </div>
      )}
      {document.has_native_file && (
        <Anchor
          href={documentNativeFileUrl(caseId, document.id)}
          size="sm"
          fw={600}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Group gap={4}>
            <IconDownload size={14} />
            Download original file
          </Group>
        </Anchor>
      )}
      {attachments?.map((att) => (
        <NavLink
          key={att.id}
          component={Link}
          to={linkTo(att.id)}
          active={att.id === document.id}
          label={att.subject || "(unnamed attachment)"}
          leftSection={<IconPaperclip size={14} />}
          description={
            <Group gap={6}>
              <Text size="xs" c="dimmed">
                {formatFileSize(att.file_size)}
              </Text>
              {att.render_error && (
                <Badge size="xs" color="red" variant="light">
                  render failed
                </Badge>
              )}
            </Group>
          }
        />
      ))}
      {attachments?.length === 0 && !isAttachment && (
        <Text size="sm" c="dimmed">
          No attachments on this document.
        </Text>
      )}
    </Stack>
  );
}
