import { Center, Loader } from "@mantine/core";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./hooks/useAuth";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CaseListPage } from "./pages/CaseListPage";
import { DocumentListPage } from "./pages/DocumentListPage";
import { DocumentViewerPage } from "./pages/DocumentViewerPage";
import { ImportPage } from "./pages/ImportPage";
import { LoginPage } from "./pages/LoginPage";
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
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  );
}
