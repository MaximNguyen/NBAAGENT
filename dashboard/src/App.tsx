import { Routes, Route } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { HistoryPage } from "./pages/HistoryPage";
import { OddsPage } from "./pages/OddsPage";
import { MetricsPage } from "./pages/MetricsPage";

export default function App() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <DashboardLayout>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/odds" element={<OddsPage />} />
          <Route path="/metrics" element={<MetricsPage />} />
        </Routes>
      </ErrorBoundary>
    </DashboardLayout>
  );
}
