import { ActionIcon, Autocomplete, Button, Popover, Stack } from "@mantine/core";
import { IconX } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { Redaction } from "../api/redactions";
import { listRedactionReasonPresets } from "../api/userPresets";

interface DraftRect {
  startX: number;
  startY: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

function ReasonEditor({
  redaction,
  onSave,
}: {
  redaction: Redaction;
  onSave: (reason: string) => void;
}) {
  const [opened, setOpened] = useState(false);
  const [reason, setReason] = useState(redaction.reason);
  const { data: reasonPresets } = useQuery({
    queryKey: ["redaction-reason-presets"],
    queryFn: listRedactionReasonPresets,
    enabled: opened,
  });

  return (
    <Popover
      opened={opened}
      onChange={setOpened}
      withArrow
      trapFocus
      shadow="md"
      onClose={() => setReason(redaction.reason)}
    >
      <Popover.Target>
        <div
          style={{ position: "absolute", inset: 0, cursor: "pointer" }}
          title={redaction.reason || "Click to add a reason"}
          onClick={(e) => {
            e.stopPropagation();
            setOpened((v) => !v);
          }}
        />
      </Popover.Target>
      <Popover.Dropdown onClick={(e) => e.stopPropagation()}>
        <Stack gap="xs" w={220}>
          <Autocomplete
            size="xs"
            label="Reason for this redaction"
            placeholder="e.g. PII, Privileged"
            data={(reasonPresets ?? []).map((p) => p.reason)}
            value={reason}
            onChange={setReason}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                onSave(reason);
                setOpened(false);
              }
            }}
          />
          <Button
            size="xs"
            onClick={() => {
              onSave(reason);
              setOpened(false);
            }}
          >
            Save
          </Button>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

/**
 * Absolutely-positioned overlay for drawing/reviewing redactions on top of a
 * rendered PDF page. `scale` converts between rendered CSS pixels (this
 * overlay's own coordinate space) and PDF point space (what's persisted) —
 * both pdf.js and PyMuPDF use a top-left-origin, y-down system at the
 * unrotated page level, so no axis flip is needed, just a uniform scale.
 *
 * Two tools share this surface: "draw" free-draws a box by dragging, and
 * "select" instead lets the browser's native text selection (over pdf.js's
 * text layer beneath) pick the area — the page container listens for the
 * selection and turns it into one or more redaction rects (multi-line
 * selections produce one rect per visual line). Only "draw" needs this
 * overlay to capture pointer events; "select" leaves them passing through
 * to the text layer.
 */
export function RedactionCanvasOverlay({
  pageWidthPx,
  pageHeightPx,
  scale,
  redactions,
  readOnly = false,
  tool = "draw",
  onCreate,
  onDelete,
  onUpdateReason,
}: {
  pageWidthPx: number;
  pageHeightPx: number;
  scale: number;
  redactions: Redaction[];
  readOnly?: boolean;
  tool?: "draw" | "select";
  onCreate: (rect: { x: number; y: number; width: number; height: number }) => void;
  onDelete: (redactionId: string) => void;
  onUpdateReason?: (redactionId: string, reason: string) => void;
}) {
  const [draft, setDraft] = useState<DraftRect | null>(null);
  const capturingDraw = !readOnly && tool === "draw";

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!capturingDraw) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setDraft({ startX: x, startY: y, x, y, width: 0, height: 0 });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!draft) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top;
    setDraft({
      ...draft,
      x: Math.min(draft.startX, currentX),
      y: Math.min(draft.startY, currentY),
      width: Math.abs(currentX - draft.startX),
      height: Math.abs(currentY - draft.startY),
    });
  };

  const handleMouseUp = () => {
    if (!draft) return;
    if (draft.width > 4 && draft.height > 4) {
      onCreate({
        x: draft.x * scale,
        y: draft.y * scale,
        width: draft.width * scale,
        height: draft.height * scale,
      });
    }
    setDraft(null);
  };

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: pageWidthPx,
        height: pageHeightPx,
        cursor: capturingDraw ? "crosshair" : "default",
        // react-pdf's text/annotation layers set their own z-index for text
        // selection; without an explicit one here, this overlay (and the
        // persisted redaction boxes inside it) can end up stacked *below*
        // them — invisible, and never receiving pointer events.
        zIndex: 10,
        // In "select" mode, pointer events must fall through to the text
        // layer beneath for native text selection to work at all; existing
        // redaction boxes re-enable pointer events on themselves below.
        pointerEvents: capturingDraw ? "auto" : "none",
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {redactions.map((r) => (
        <div
          key={r.id}
          style={{
            position: "absolute",
            left: r.x / scale,
            top: r.y / scale,
            width: r.width / scale,
            height: r.height / scale,
            backgroundColor: r.color,
            opacity: 0.65,
            pointerEvents: readOnly && !onUpdateReason ? "none" : "auto",
          }}
          title={r.reason || undefined}
        >
          {!readOnly && onUpdateReason && (
            <ReasonEditor redaction={r} onSave={(reason) => onUpdateReason(r.id, reason)} />
          )}
          {!readOnly && (
            <ActionIcon
              size="xs"
              color="white"
              variant="transparent"
              style={{ position: "absolute", top: -2, right: -2, zIndex: 1 }}
              onClick={(e) => {
                e.stopPropagation();
                onDelete(r.id);
              }}
            >
              <IconX size={12} />
            </ActionIcon>
          )}
        </div>
      ))}
      {draft && (
        <div
          style={{
            position: "absolute",
            left: draft.x,
            top: draft.y,
            width: draft.width,
            height: draft.height,
            backgroundColor: "black",
            opacity: 0.5,
            pointerEvents: "none",
          }}
        />
      )}
    </div>
  );
}
