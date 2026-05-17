import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { ReposPage } from "./pages/ReposPage";
import { RepoScanRunsPage } from "./pages/RepoScanRunsPage";
import { PromptGalleryPage } from "./pages/PromptGalleryPage";
import { PendingReviewPage } from "./pages/PendingReviewPage";
import { SearchPage } from "./pages/SearchPage";
import { ExportPage } from "./pages/ExportPage";
import { ScheduledTasksPage } from "./pages/ScheduledTasksPage";
import { PairCandidatesPage } from "./pages/PairCandidatesPage";
import { AnnotationTasksPage } from "./pages/AnnotationTasksPage";
import { SystemConfigPage } from "./pages/SystemConfigPage";
import { AgentPage } from "./pages/AgentPage";
import { AgentMemoryPage } from "./pages/AgentMemoryPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="/repos" element={<ReposPage />} />
        <Route path="/repo-scan-runs" element={<RepoScanRunsPage />} />
        <Route path="/prompts" element={<PromptGalleryPage />} />
        <Route path="/pending" element={<PendingReviewPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/scheduled-tasks" element={<ScheduledTasksPage />} />
        <Route path="/pair-candidates" element={<PairCandidatesPage />} />
        <Route path="/annotation-tasks" element={<AnnotationTasksPage />} />
        <Route path="/agent" element={<AgentPage />} />
        <Route path="/agent/memory" element={<AgentMemoryPage />} />
        <Route path="/settings" element={<SystemConfigPage />} />
        <Route path="/export" element={<ExportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
