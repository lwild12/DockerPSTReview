import { Center, Loader } from "@mantine/core";
import { Navigate, Route, Routes } from "react-router-dom";

import { CaseShell } from "./components/layout/CaseShell";
import { PlainShell } from "./components/layout/PlainShell";
import { useAuth } from "./hooks/useAuth";
import { AdminPage } from "./pages/AdminPage";
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

function RequireSuperuser({ children }: { children: React.ReactNode }) {
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
  if (!user.is_superuser) {
    return <Navigate to="/cases" replace />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <RequireAuth>
            <PlainShell />
          </RequireAuth>
        }
      >
        <Route path="/cases" element={<CaseListPage />} />
      </Route>

      <Route
        element={
          <RequireSuperuser>
            <PlainShell />
          </RequireSuperuser>
        }
      >
        <Route path="/admin" element={<AdminPage />} />
      </Route>

      <Route
        element={
          <RequireAuth>
            <CaseShell />
          </RequireAuth>
        }
      >
        <Route path="/cases/:caseId" element={<CaseDetailPage />} />
        <Route path="/cases/:caseId/import" element={<ImportPage />} />
        <Route path="/cases/:caseId/documents" element={<DocumentListPage />} />
        <Route path="/cases/:caseId/documents/:documentId" element={<DocumentViewerPage />} />
        <Route path="/cases/:caseId/review-sets" element={<ReviewSetsPage />} />
        <Route
          path="/cases/:caseId/review-sets/:reviewSetId"
          element={<ReviewSetDetailPage />}
        />
        <Route path="/cases/:caseId/coding-fields" element={<CodingFieldsPage />} />
        <Route path="/cases/:caseId/redaction-log" element={<RedactionLogPage />} />
        <Route path="/cases/:caseId/export" element={<ExportPage />} />
        <Route path="/cases/:caseId/audit-log" element={<AuditLogPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  );
}
