import { Alert, Center, Loader, Pagination, Stack } from "@mantine/core";
import { useState } from "react";
import { Document as PdfDocument, Page as PdfPage, pdfjs } from "react-pdf";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfViewer({ url }: { url: string }) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState<string | null>(null);

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
        <PdfPage pageNumber={pageNumber} width={720} />
      </PdfDocument>
      {numPages && numPages > 1 && (
        <Pagination total={numPages} value={pageNumber} onChange={setPageNumber} />
      )}
    </Stack>
  );
}
