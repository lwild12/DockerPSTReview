import { Center, Loader } from "@mantine/core";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./hooks/useAuth";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CaseListPage } from "./pages/CaseListPage";
import { LoginPage } from "./pages/LoginPage";

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
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  );
}
