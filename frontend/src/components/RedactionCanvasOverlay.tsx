import { ActionIcon } from "@mantine/core";
import { IconX } from "@tabler/icons-react";
import { useState } from "react";

import type { Redaction } from "../api/redactions";

interface DraftRect {
  startX: number;
  startY: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Absolutely-positioned overlay for drawing/reviewing redactions on top of a
 * rendered PDF page. `scale` converts between rendered CSS pixels (this
 * overlay's own coordinate space) and PDF point space (what's persisted) —
 * both pdf.js and PyMuPDF use a top-left-origin, y-down system at the
 * unrotated page level, so no axis flip is needed, just a uniform scale.
 */
export function RedactionCanvasOverlay({
  pageWidthPx,
  pageHeightPx,
  scale,
  redactions,
  readOnly = false,
  onCreate,
  onDelete,
}: {
  pageWidthPx: number;
  pageHeightPx: number;
  scale: number;
  redactions: Redaction[];
  readOnly?: boolean;
  onCreate: (rect: { x: number; y: number; width: number; height: number }) => void;
  onDelete: (redactionId: string) => void;
}) {
  const [draft, setDraft] = useState<DraftRect | null>(null);

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (readOnly) return;
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
        cursor: readOnly ? "default" : "crosshair",
        // react-pdf's text/annotation layers set their own z-index for text
        // selection; without an explicit one here, this overlay (and the
        // persisted redaction boxes inside it) can end up stacked *below*
        // them — invisible, and never receiving pointer events.
        zIndex: 10,
        pointerEvents: readOnly ? "none" : "auto",
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
          }}
        >
          {!readOnly && (
            <ActionIcon
              size="xs"
              color="white"
              variant="transparent"
              style={{ position: "absolute", top: -2, right: -2 }}
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
