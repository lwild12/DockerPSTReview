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
  onCreateRedaction,
  onDeleteRedaction,
}: {
  url: string;
  redactions?: Redaction[];
  readOnly?: boolean;
  onCreateRedaction?: (pageNumber: number, rect: { x: number; y: number; width: number; height: number }) => void;
  onDeleteRedaction?: (redactionId: string) => void;
}) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [pageHeightPx, setPageHeightPx] = useState<number | null>(null);
  const [pointsPerPixel, setPointsPerPixel] = useState<number | null>(null);

  // page_number in the API is 0-indexed; the viewer's pageNumber is 1-indexed.
  const currentPageRedactions = redactions.filter((r) => r.page_number === pageNumber - 1);

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
        <div style={{ position: "relative", width: RENDER_WIDTH_PX }}>
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
              onCreate={(rect) => onCreateRedaction?.(pageNumber - 1, rect)}
              onDelete={(id) => onDeleteRedaction?.(id)}
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
