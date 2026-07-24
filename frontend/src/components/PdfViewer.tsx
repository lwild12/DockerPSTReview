import { Alert, Center, Loader, Pagination, Stack } from "@mantine/core";
import { useState } from "react";
import { Document as PdfDocument, Page as PdfPage, pdfjs } from "react-pdf";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import type { Redaction } from "../api/redactions";
import { RedactionCanvasOverlay } from "./RedactionCanvasOverlay";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const RENDER_WIDTH_PX = 720;

export function PdfViewer({
  url,
  redactions = [],
  readOnly = true,
  redactionTool = "draw",
  onCreateRedaction,
  onDeleteRedaction,
  onUpdateRedactionReason,
}: {
  url: string;
  redactions?: Redaction[];
  readOnly?: boolean;
  redactionTool?: "draw" | "select";
  onCreateRedaction?: (pageNumber: number, rect: { x: number; y: number; width: number; height: number }) => void;
  onDeleteRedaction?: (redactionId: string) => void;
  onUpdateRedactionReason?: (redactionId: string, reason: string) => void;
}) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [pageHeightPx, setPageHeightPx] = useState<number | null>(null);
  const [pointsPerPixel, setPointsPerPixel] = useState<number | null>(null);

  // page_number in the API is 0-indexed; the viewer's pageNumber is 1-indexed.
  const currentPageRedactions = redactions.filter((r) => r.page_number === pageNumber - 1);

  const handleSelectionMouseUp = (e: React.MouseEvent<HTMLDivElement>) => {
    if (readOnly || !onCreateRedaction || redactionTool !== "select" || pointsPerPixel === null) {
      return;
    }
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return;
    // Ignore selections started/ended outside this page (e.g. dragging from
    // the thread panel) so we don't redact text on the wrong page.
    if (!e.currentTarget.contains(selection.anchorNode)) return;

    const containerRect = e.currentTarget.getBoundingClientRect();
    for (let i = 0; i < selection.rangeCount; i++) {
      const range = selection.getRangeAt(i);
      // A multi-line selection yields one client rect per visual line --
      // exactly the per-line redaction bands a text-select tool should produce.
      for (const rect of range.getClientRects()) {
        if (rect.width <= 0 || rect.height <= 0) continue;
        onCreateRedaction(pageNumber - 1, {
          x: (rect.left - containerRect.left) * pointsPerPixel,
          y: (rect.top - containerRect.top) * pointsPerPixel,
          width: rect.width * pointsPerPixel,
          height: rect.height * pointsPerPixel,
        });
      }
    }
    selection.removeAllRanges();
  };

  return (
    <Stack align="center">
      {error && <Alert color="red">{error}</Alert>}
      <PdfDocument
        file={url}
        onLoadSuccess={({ numPages: n }) => {
          setNumPages(n);
          setPageNumber(1);
          setError(null);
        }}
        onLoadError={(err) => setError(err.message)}
        loading={
          <Center h={200}>
            <Loader />
          </Center>
        }
      >
        <div
          style={{ position: "relative", width: RENDER_WIDTH_PX }}
          onMouseUp={handleSelectionMouseUp}
        >
          <PdfPage
            pageNumber={pageNumber}
            width={RENDER_WIDTH_PX}
            onLoadSuccess={(page) => {
              const nativeWidth = page.view[2] - page.view[0];
              const nativeHeight = page.view[3] - page.view[1];
              setPointsPerPixel(nativeWidth / RENDER_WIDTH_PX);
              setPageHeightPx(RENDER_WIDTH_PX * (nativeHeight / nativeWidth));
            }}
          />
          {pageHeightPx !== null && pointsPerPixel !== null && (onCreateRedaction || currentPageRedactions.length > 0) && (
            <RedactionCanvasOverlay
              pageWidthPx={RENDER_WIDTH_PX}
              pageHeightPx={pageHeightPx}
              scale={pointsPerPixel}
              redactions={currentPageRedactions}
              readOnly={readOnly || !onCreateRedaction}
              tool={redactionTool}
              onCreate={(rect) => onCreateRedaction?.(pageNumber - 1, rect)}
              onDelete={(id) => onDeleteRedaction?.(id)}
              onUpdateReason={onUpdateRedactionReason}
            />
          )}
        </div>
      </PdfDocument>
      {numPages && numPages > 1 && (
        <Pagination total={numPages} value={pageNumber} onChange={setPageNumber} />
      )}
    </Stack>
  );
}
