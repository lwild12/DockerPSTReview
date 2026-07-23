import { Center, Loader } from "@mantine/core";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./hooks/useAuth";
import { AuditLogPage } from "./pages/AuditLogPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CaseListPage } from "./pages/CaseListPage";
import { CodingFieldsPage } from "./pages/CodingFieldsPage";
import { DocumentListPage } from "./pages/DocumentListPage";
import { DocumentViewerPage } from "./pages/DocumentViewerPage";
import { ExportPage } from "./pages/ExportPage";
import { ImportPage } from "./pages/ImportPage";
import { LoginPage } from "./pages/LoginPage";
import { RedactionLogPage } from "./pages/RedactionLogPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ReviewSetDetailPage, ReviewSetsPage } from "./pages/ReviewSetsPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <Center mih="100vh">
        <Loader />
      </Center>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/cases"
        element={
          <RequireAuth>
            <CaseListPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId"
        element={
          <RequireAuth>
            <CaseDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/import"
        element={
          <RequireAuth>
            <ImportPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/documents"
        element={
          <RequireAuth>
            <DocumentListPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/documents/:documentId"
        element={
          <RequireAuth>
            <DocumentViewerPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/review-sets"
        element={
          <RequireAuth>
            <ReviewSetsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/review-sets/:reviewSetId"
        element={
          <RequireAuth>
            <ReviewSetDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/coding-fields"
        element={
          <RequireAuth>
            <CodingFieldsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/redaction-log"
        element={
          <RequireAuth>
            <RedactionLogPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/export"
        element={
          <RequireAuth>
            <ExportPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId/audit-log"
        element={
          <RequireAuth>
            <AuditLogPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  );
}
