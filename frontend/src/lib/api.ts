import type {
  AgentChatResult,
  AgentMemory,
  AgentMemoryPayload,
  AgentMessage,
  AgentThread,
  AnnotationQueueItem,
  AnnotationRun,
  AnnotationRunCreate,
  AnnotationRunUpdate,
  AnnotationSuggestion,
  AnnotationSuggestionPatch,
  AiConfig,
  AiConfigPayload,
  AiModelsResult,
  AiTestResult,
  CloudStorageStatus,
  CloudUploadRequest,
  CloudUploadRun,
  DashboardStats,
  GithubAuthStatus,
  GithubDevicePoll,
  GithubDeviceStart,
  Paginated,
  PairCandidate,
  PromptPairBatchUpdate,
  PromptPairBatchUpdateResult,
  PromptPair,
  PromptPairPatch,
  Repo,
  RepoBatchDeleteResult,
  RepoBatchScanResult,
  RepoPayload,
  RepoScanPayload,
  RepoScanRun,
  RepoScanRunBatchDeleteResult,
  RepoScanResult,
  RepoScanStart,
  RepoScanTemplate,
  ScheduledTask,
  ScheduledTaskPayload,
  SkillRepoProfile,
  Tag,
  TaskRun,
  VisualAsset,
  WebUiRepoProfile,
  WebUiPrompt
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

const params = (input: Record<string, unknown>) => {
  const query = new URLSearchParams();
  Object.entries(input).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  return query.toString();
};

export const api = {
  dashboard: () => request<DashboardStats>("/api/dashboard/stats"),
  annotationQueue: (filters: Record<string, unknown>) => request<Paginated<AnnotationQueueItem>>(`/api/annotations/queue?${params(filters)}`),
  annotationRuns: (filters: Record<string, unknown>) => request<Paginated<AnnotationRun>>(`/api/annotation-runs?${params(filters)}`),
  annotationRun: (id: number) => request<AnnotationRun>(`/api/annotation-runs/${id}`),
  createAnnotationRun: (payload: AnnotationRunCreate) => request<AnnotationRun>("/api/annotation-runs", { method: "POST", body: JSON.stringify(payload) }),
  updateAnnotationRun: (id: number, payload: AnnotationRunUpdate) =>
    request<AnnotationRun>(`/api/annotation-runs/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  cancelAnnotationRun: (id: number) => request<AnnotationRun>(`/api/annotation-runs/${id}/cancel`, { method: "POST" }),
  pauseAnnotationRun: (id: number) => request<AnnotationRun>(`/api/annotation-runs/${id}/pause`, { method: "POST" }),
  rerunAnnotationRun: (id: number) => request<AnnotationRun>(`/api/annotation-runs/${id}/rerun`, { method: "POST" }),
  deleteAnnotationRun: (id: number) => request<{ deleted: boolean; id: number }>(`/api/annotation-runs/${id}`, { method: "DELETE" }),
  annotationSuggestions: (filters: Record<string, unknown>) => request<Paginated<AnnotationSuggestion>>(`/api/annotation-suggestions?${params(filters)}`),
  annotationSuggestion: (id: number) => request<AnnotationSuggestion>(`/api/annotation-suggestions/${id}`),
  updateAnnotationSuggestion: (id: number, payload: AnnotationSuggestionPatch) =>
    request<AnnotationSuggestion>(`/api/annotation-suggestions/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  acceptAnnotationSuggestion: (id: number) => request<AnnotationSuggestion>(`/api/annotation-suggestions/${id}/accept`, { method: "POST" }),
  rejectAnnotationSuggestion: (id: number) => request<AnnotationSuggestion>(`/api/annotation-suggestions/${id}/reject`, { method: "POST" }),
  repos: (filters: Record<string, unknown>) => request<Paginated<Repo>>(`/api/repos?${params(filters)}`),
  createRepo: (payload: RepoPayload) => request<Repo>("/api/repos", { method: "POST", body: JSON.stringify(payload) }),
  repo: (id: number) => request<Repo>(`/api/repos/${id}`),
  updateRepo: (id: number, payload: Partial<RepoPayload>) => request<Repo>(`/api/repos/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteRepo: (id: number) => request<{ deleted: boolean; id: number }>(`/api/repos/${id}`, { method: "DELETE" }),
  scanRepo: (id: number, payload?: RepoScanPayload) =>
    request<RepoScanStart>(`/api/repos/${id}/scan`, { method: "POST", body: JSON.stringify(payload || {}) }),
  repoScanRunsList: (filters: Record<string, unknown>) => request<Paginated<RepoScanRun>>(`/api/repo-scan-runs?${params(filters)}`),
  repoScanRun: (id: number) => request<RepoScanRun>(`/api/repo-scan-runs/${id}`),
  cancelRepoScanRun: (id: number) => request<RepoScanRun>(`/api/repo-scan-runs/${id}/cancel`, { method: "POST" }),
  batchDeleteRepoScanRuns: (ids: number[]) =>
    request<RepoScanRunBatchDeleteResult>("/api/repo-scan-runs/batch-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  repoScanRuns: (repoId: number, limit = 20) => request<RepoScanRun[]>(`/api/repos/${repoId}/scan-runs?limit=${limit}`),
  batchDeleteRepos: (ids: number[]) => request<RepoBatchDeleteResult>("/api/repos/batch-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  batchScanRepos: (ids: number[]) => request<RepoBatchScanResult>("/api/repos/batch-scan", { method: "POST", body: JSON.stringify({ ids }) }),
  promptPairs: (filters: Record<string, unknown>) => request<Paginated<PromptPair>>(`/api/prompt-pairs?${params(filters)}`),
  promptPair: (id: number) => request<PromptPair>(`/api/prompt-pairs/${id}`),
  updatePromptPair: (id: number, payload: PromptPairPatch) =>
    request<PromptPair>(`/api/prompt-pairs/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  batchUpdatePromptPairs: (payload: PromptPairBatchUpdate) =>
    request<PromptPairBatchUpdateResult>("/api/prompt-pairs/batch-update", { method: "POST", body: JSON.stringify(payload) }),
  webUiPrompts: (filters: Record<string, unknown>) => request<Paginated<WebUiPrompt>>(`/api/web-ui-prompts?${params(filters)}`),
  webUiPrompt: (id: number) => request<WebUiPrompt>(`/api/web-ui-prompts/${id}`),
  webUiRepoProfiles: (filters: Record<string, unknown>) => request<Paginated<WebUiRepoProfile>>(`/api/web-ui-repo-profiles?${params(filters)}`),
  webUiRepoProfile: (id: number) => request<WebUiRepoProfile>(`/api/web-ui-repo-profiles/${id}`),
  updateWebUiRepoProfile: (id: number, payload: Partial<WebUiRepoProfile>) =>
    request<WebUiRepoProfile>(`/api/web-ui-repo-profiles/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  skillRepoProfiles: (filters: Record<string, unknown>) => request<Paginated<SkillRepoProfile>>(`/api/skill-repo-profiles?${params(filters)}`),
  skillRepoProfile: (id: number) => request<SkillRepoProfile>(`/api/skill-repo-profiles/${id}`),
  updateSkillRepoProfile: (id: number, payload: Partial<SkillRepoProfile>) =>
    request<SkillRepoProfile>(`/api/skill-repo-profiles/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  pairCandidates: (filters: Record<string, unknown>) => request<Paginated<PairCandidate>>(`/api/pair-candidates?${params(filters)}`),
  updatePairCandidate: (id: number, payload: { review_status: string; review_reason?: string }) =>
    request<PairCandidate>(`/api/pair-candidates/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  acceptPairCandidate: (id: number, payload: { selection_status?: string }) =>
    request<PairCandidate>(`/api/pair-candidates/${id}/accept`, { method: "POST", body: JSON.stringify(payload) }),
  rejectPairCandidate: (id: number) => request<PairCandidate>(`/api/pair-candidates/${id}/reject`, { method: "POST" }),
  assets: (filters: Record<string, unknown>) => request<Paginated<VisualAsset>>(`/api/assets?${params(filters)}`),
  updateAsset: (id: number, payload: Partial<VisualAsset>) => request<VisualAsset>(`/api/assets/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  cloudStorageStatus: () => request<CloudStorageStatus>("/api/cloud-storage/status"),
  cloudUploadRuns: (filters: Record<string, unknown> = {}) => request<Paginated<CloudUploadRun>>(`/api/cloud-storage/upload-runs?${params(filters)}`),
  cloudUploadRun: (id: number) => request<CloudUploadRun>(`/api/cloud-storage/upload-runs/${id}`),
  createCloudUploadRun: (payload: CloudUploadRequest) => request<CloudUploadRun>("/api/cloud-storage/upload-assets", { method: "POST", body: JSON.stringify(payload) }),
  cancelCloudUploadRun: (id: number) => request<CloudUploadRun>(`/api/cloud-storage/upload-runs/${id}/cancel`, { method: "POST" }),
  tags: () => request<Tag[]>("/api/tags"),
  createTag: (payload: { name: string; type?: string }) => request<Tag>("/api/tags", { method: "POST", body: JSON.stringify(payload) }),
  exportData: (payload: { format: string; selection_status?: string; category?: string }) =>
    request<{ path: string; format: string }>("/api/export", { method: "POST", body: JSON.stringify(payload) }),
  searchGithub: (payload: { categories?: string[]; keywords?: string[]; per_keyword_limit?: number; allow_anonymous?: boolean }) =>
    request<Record<string, unknown>>("/api/search/github", { method: "POST", body: JSON.stringify(payload) }),
  searchLogs: () => request<Array<Record<string, unknown>>>("/api/search/logs"),
  scheduledTasks: (filters: Record<string, unknown> = {}) => request<Paginated<ScheduledTask>>(`/api/scheduled-tasks?${params(filters)}`),
  scheduledTask: (id: number) => request<ScheduledTask>(`/api/scheduled-tasks/${id}`),
  createScheduledTask: (payload: ScheduledTaskPayload) =>
    request<ScheduledTask>("/api/scheduled-tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateScheduledTask: (id: number, payload: ScheduledTaskPayload) =>
    request<ScheduledTask>(`/api/scheduled-tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteScheduledTask: (id: number) => request<{ deleted: boolean }>(`/api/scheduled-tasks/${id}`, { method: "DELETE" }),
  runScheduledTaskNow: (id: number) => request<TaskRun>(`/api/scheduled-tasks/${id}/run-now`, { method: "POST" }),
  scheduledTaskRuns: (id: number, filters: Record<string, unknown> = {}) =>
    request<Paginated<TaskRun>>(`/api/scheduled-tasks/${id}/runs?${params(filters)}`),
  aiConfigs: () => request<AiConfig[]>("/api/ai-configs"),
  aiConfig: (id: number) => request<AiConfig>(`/api/ai-configs/${id}`),
  createAiConfig: (payload: AiConfigPayload) => request<AiConfig>("/api/ai-configs", { method: "POST", body: JSON.stringify(payload) }),
  updateAiConfig: (id: number, payload: AiConfigPayload) =>
    request<AiConfig>(`/api/ai-configs/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAiConfig: (id: number) => request<{ deleted: boolean; id: number }>(`/api/ai-configs/${id}`, { method: "DELETE" }),
  testAiConfig: (id: number) => request<AiTestResult>(`/api/ai-configs/${id}/test`, { method: "POST" }),
  aiConfigModels: (id: number) => request<AiModelsResult>(`/api/ai-configs/${id}/models`),
  repoScanTemplates: (repoId: number) => request<RepoScanTemplate[]>(`/api/repos/${repoId}/scan-templates`),
  generateRepoScanTemplate: (repoId: number, aiConfigId?: number | null) =>
    request<RepoScanTemplate>(`/api/repos/${repoId}/scan-template/generate${aiConfigId ? `?ai_config_id=${aiConfigId}` : ""}`, { method: "POST" }),
  updateRepoScanTemplate: (id: number, payload: Partial<RepoScanTemplate>) =>
    request<RepoScanTemplate>(`/api/repo-scan-templates/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  approveRepoScanTemplate: (id: number) => request<RepoScanTemplate>(`/api/repo-scan-templates/${id}/approve`, { method: "POST" }),
  rejectRepoScanTemplate: (id: number) => request<RepoScanTemplate>(`/api/repo-scan-templates/${id}/reject`, { method: "POST" }),
  agentChat: (payload: { message: string; thread_id?: string | null }) =>
    request<AgentChatResult>("/api/agent/chat", { method: "POST", body: JSON.stringify(payload) }),
  agentThreads: () => request<AgentThread[]>("/api/agent/threads"),
  agentMessages: (threadId: string) => request<AgentMessage[]>(`/api/agent/threads/${threadId}/messages`),
  deleteAgentThread: (threadId: string) => request<{ deleted: boolean; thread_id: string }>(`/api/agent/threads/${threadId}`, { method: "DELETE" }),
  agentMemories: (filters: Record<string, unknown> = {}) => request<Paginated<AgentMemory>>(`/api/agent/memories?${params(filters)}`),
  createAgentMemory: (payload: AgentMemoryPayload) => request<AgentMemory>("/api/agent/memories", { method: "POST", body: JSON.stringify(payload) }),
  updateAgentMemory: (id: number, payload: AgentMemoryPayload) =>
    request<AgentMemory>(`/api/agent/memories/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  approveAgentMemory: (id: number) => request<AgentMemory>(`/api/agent/memories/${id}/approve`, { method: "POST" }),
  rejectAgentMemory: (id: number) => request<AgentMemory>(`/api/agent/memories/${id}/reject`, { method: "POST" }),
  deleteAgentMemory: (id: number) => request<{ deleted: boolean; id: number }>(`/api/agent/memories/${id}`, { method: "DELETE" }),
  githubAuthStatus: () => request<GithubAuthStatus>("/api/auth/github/status"),
  saveGithubClientId: (payload: { client_id: string }) => request<GithubAuthStatus>("/api/auth/github/config", { method: "POST", body: JSON.stringify(payload) }),
  startGithubDevice: (payload: { client_id?: string; scope?: string }) =>
    request<GithubDeviceStart>("/api/auth/github/device/start", { method: "POST", body: JSON.stringify(payload) }),
  pollGithubDevice: (payload: { session_id: string }) =>
    request<GithubDevicePoll>("/api/auth/github/device/poll", { method: "POST", body: JSON.stringify(payload) }),
  logoutGithub: () => request<GithubAuthStatus>("/api/auth/github/logout", { method: "POST" })
};
