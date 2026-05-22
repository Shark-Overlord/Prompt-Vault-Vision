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
import { WebUiPromptLibraryPage } from "./pages/WebUiPromptLibraryPage";
import { SkillRepoLibraryPage } from "./pages/SkillRepoLibraryPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="/repos" element={<ReposPage />} />
        <Route path="/repo-scan-runs" element={<RepoScanRunsPage />} />
        <Route path="/prompts" element={<Navigate to="/prompt-assets/image-generation" replace />} />
        <Route path="/prompt-assets/web-ui" element={<WebUiPromptLibraryPage />} />
        <Route path="/prompt-assets/skills" element={<SkillRepoLibraryPage />} />
        <Route path="/prompt-assets/image-editing" element={<Navigate to="/prompt-assets/skills" replace />} />
        <Route
          path="/prompt-assets/image-generation"
          element={
            <PromptGalleryPage
              fixedCategory="image_generation_prompt"
              title="图像生成 Prompt 资产库"
              eyebrow="Image Generation Asset Library"
              description="保存图像生成类 Prompt 与对应效果图、来源页面、证据链和筛选结论。"
            />
          }
        />
        <Route
          path="/prompt-assets/video-generation"
          element={
            <PromptGalleryPage
              fixedCategory="video_generation_prompt"
              title="视频生成 Prompt 资产库"
              eyebrow="Video Generation Asset Library"
              description="保存视频生成、分镜、产品视频、广告视频等 Prompt 与缩略图或输出证据。"
            />
          }
        />
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
