export type Paginated<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type Repo = {
  id: number;
  repo_name: string;
  owner: string;
  repo_url: string;
  canonical_url: string;
  stars: number;
  forks: number;
  license: string;
  is_fork: number;
  category: string;
  quality_level: string;
  status: string;
  summary: string;
  has_preview_images: number;
  has_prompt_effect_pairs: number;
  prompt_effect_pair_count: number;
  last_checked_at: string;
  last_updated_at: string;
  created_at: string;
};

export type RepoPayload = {
  repo_name?: string;
  owner?: string;
  repo_url: string;
  canonical_url?: string;
  stars?: number;
  forks?: number;
  license?: string;
  is_fork?: number;
  parent_repo?: string | null;
  resource_type?: string;
  category?: string;
  quality_level?: string;
  status?: string;
  summary?: string;
  notes?: string;
};

export type RepoScanResult = {
  status: string;
  repo_id: number;
  repo: string;
  action?: string;
  reason?: string;
  scanned_files: number;
  prompt_candidates: number;
  pair_candidates: number;
  prompt_pairs_added: number;
  pair_candidates_added: number;
  images_added: number;
  has_strict_pairs?: boolean;
  use_ai?: boolean;
  scan_mode?: "generic" | "generate_ai_template" | "template";
  template_id?: number | null;
  generated_template_id?: number | null;
  template_status?: string | null;
  template_preview?: string | null;
  primary_target_count?: number;
  secondary_target_count?: number;
  estimated_pair_count?: number;
  template_fallback?: boolean;
  web_ui_prompts_found?: number;
  web_ui_prompts_added?: number;
  web_ui_prompts_updated?: number;
  web_ui_prompts_skipped?: number;
  web_ui_screenshots_added?: number;
  skill_type?: string;
  skill_profiles_added?: number;
  skill_profiles_updated?: number;
  summary?: string | null;
};

export type RepoScanRun = {
  id: number;
  repo_id: number;
  repo_name?: string | null;
  repo_owner?: string | null;
  repo_url?: string | null;
  repo_category?: string | null;
  use_ai?: number;
  template_id?: number | null;
  status: "queued" | "running" | "succeeded" | "failed" | "cancel_request" | "cancel_requested" | "canceled" | string;
  progress_percent: number;
  current_file?: string | null;
  total_files: number;
  processed_files: number;
  total_images: number;
  downloaded_images: number;
  error_count: number;
  scanned_files: number;
  prompt_candidates: number;
  pair_candidates: number;
  prompt_pairs_added: number;
  pair_candidates_added: number;
  images_added: number;
  summary?: string | null;
  error?: string | null;
  options_json?: string | null;
  result_json?: string | null;
  web_ui_prompts_found?: number;
  web_ui_prompts_added?: number;
  web_ui_prompts_updated?: number;
  web_ui_prompts_skipped?: number;
  web_ui_screenshots_added?: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at?: string | null;
  cancel_requested?: number;
};

export type RepoScanStart = RepoScanRun & {
  run_id: number;
  queued_at?: string | null;
};

export type RepoScanPayload = {
  use_ai?: boolean;
  ai_config_id?: number | null;
  template_id?: number | null;
  generate_template?: boolean;
  scan_mode?: "generic" | "generate_ai_template" | "template";
};

export type RepoScanTemplate = {
  id: number;
  repo_id: number;
  template_version: number;
  status: "pending_review" | "active" | "rejected" | "archived";
  content_json: string;
  summary_cn?: string | null;
  confidence: number;
  source_ai_config_id?: number | null;
  created_at: string;
  updated_at: string;
  approved_at?: string | null;
  notes?: string | null;
};

export type RepoBatchDeleteResult = {
  deleted: boolean;
  requested_count: number;
  deleted_count: number;
  ids: number[];
  missing_ids: number[];
};

export type RepoBatchScanResult = {
  status: "ok" | "partial";
  summary: string;
  requested_count: number;
  queued_count?: number;
  success_count?: number;
  failed_count: number;
  skipped_count?: number;
  prompt_pairs_added?: number;
  pair_candidates_added?: number;
  images_added?: number;
  results: RepoScanRun[];
  runs?: RepoScanRun[];
  failed: Array<{ repo_id: number; status_code: number; error: string }>;
};

export type RepoScanRunBatchDeleteResult = {
  deleted: boolean;
  requested_count: number;
  deleted_count: number;
  deleted_ids: number[];
  skipped_count: number;
  skipped: Array<{ id: number; status: string; reason: string }>;
  missing_ids: number[];
};

export type PromptPair = {
  id: number;
  repo_id: number;
  repo_name: string;
  repo_url: string;
  source_page_url: string;
  original_prompt: string;
  prompt_cn_explanation: string;
  image_original_url: string;
  image_local_path: string;
  cloud_storage_url?: string | null;
  image_hash: string;
  task_type: string;
  category: string;
  scenario: string;
  visual_style: string;
  quality_level: string;
  selection_status: string;
  effect_review: string;
  reusable_value: string;
  license: string;
  commercial_risk: string;
  pair_relation_type?: string;
  pair_evidence?: string;
  pair_confidence?: number;
  generated_by?: string;
  visual_asset_type?: string;
  visual_asset_type_confidence?: number;
  visual_asset_type_source?: string;
  visual_asset_type_reason?: string;
  latest_annotation_suggestion_id?: number | null;
  latest_annotation_suggestion_status?: string | null;
  latest_suggested_cn_explanation?: string | null;
  latest_suggested_tags_json?: string | null;
  latest_suggested_tags?: Tag[];
  latest_suggested_image_type_cn?: string | null;
  latest_suggested_reason_cn?: string | null;
  annotation_display_status?: "formal" | "draft" | "none" | string;
  created_at: string;
  updated_at: string;
  tags?: Tag[];
  tag_count?: number;
};

export type VisualAsset = {
  id: number;
  repo_id: number;
  image_original_url: string;
  image_local_path: string;
  cloud_storage_url?: string | null;
  thumbnail_local_path?: string | null;
  thumbnail_cloud_storage_url?: string | null;
  image_hash: string;
  source_page_url?: string | null;
  asset_type: string;
  width?: number | null;
  height?: number | null;
  file_size?: number | null;
  description?: string | null;
  cloud_storage_provider?: string | null;
  cloud_storage_bucket?: string | null;
  cloud_storage_region?: string | null;
  cloud_storage_key?: string | null;
  cloud_uploaded_at?: string | null;
  commercial_risk?: string | null;
  created_at: string;
  repo_name?: string | null;
  repo_url?: string | null;
  repo_category?: string | null;
  repo_status?: string | null;
};

export type CloudStorageStatus = {
  configured: boolean;
  message?: string;
  provider?: string;
  host?: string;
  region?: string;
  bucket?: string;
  key_prefix?: string;
  secret_id_set?: boolean;
  secret_key_set?: boolean;
};

export type CloudUploadRun = {
  id: number;
  status: "queued" | "running" | "succeeded" | "failed" | "cancel_requested" | "canceled" | string;
  total_assets: number;
  processed_assets: number;
  uploaded_assets: number;
  skipped_assets: number;
  failed_assets: number;
  current_asset_id?: number | null;
  current_file?: string | null;
  options_json?: string | null;
  result_json?: string | null;
  error?: string | null;
  cancel_requested?: number;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at?: string | null;
};

export type CloudUploadRequest = {
  asset_ids?: number[] | null;
  only_missing?: boolean;
  include_thumbnails?: boolean;
  asset_type?: string | null;
  limit?: number | null;
};

export type PromptPairPatch = Omit<Partial<PromptPair>, "tags"> & {
  tags?: string[];
};

export type PromptPairBatchUpdate = {
  ids: number[];
  selection_status?: string;
  quality_level?: string;
  visual_asset_type?: string;
  tags?: string[];
};

export type PromptPairBatchUpdateResult = {
  updated: boolean;
  requested_count: number;
  updated_count: number;
  ids: number[];
  missing_ids: number[];
};

export type WebUiPrompt = {
  id: number;
  repo_id?: number | null;
  repo_name?: string | null;
  repo_url?: string | null;
  source_page_url?: string | null;
  source_file?: string | null;
  source_heading?: string | null;
  line_start?: number | null;
  line_end?: number | null;
  asset_group: string;
  asset_type: string;
  library_kind?: string | null;
  component_type?: string | null;
  page_type?: string | null;
  framework?: string | null;
  prompt_text: string;
  prompt_cn_translation?: string | null;
  design_rules?: string | null;
  ui_pattern?: string | null;
  screenshot_original_url?: string | null;
  screenshot_local_path?: string | null;
  screenshot_cloud_storage_url?: string | null;
  screenshot_hash?: string | null;
  tags?: string[];
  quality_level?: string | null;
  selection_status?: string | null;
  reuse_value?: string | null;
  evidence?: string | null;
  confidence?: number | null;
  content_hash?: string | null;
  license?: string | null;
  commercial_risk?: string | null;
  generated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  notes?: string | null;
};

export type WebUiRepoProfile = {
  id: number;
  repo_id: number;
  repo_name?: string | null;
  repo_url?: string | null;
  profile_type: string;
  library_kind?: string | null;
  ui_stack?: string | null;
  supported_frontend_types?: string[];
  component_focus?: string[];
  style_keywords?: string[];
  reuse_mode?: string | null;
  summary_cn?: string | null;
  ai_summary_cn?: string | null;
  evidence?: string | null;
  ai_reason_cn?: string | null;
  confidence?: number | null;
  source_ai_config_id?: number | null;
  screenshot_original_url?: string | null;
  screenshot_local_path?: string | null;
  screenshot_cloud_storage_url?: string | null;
  screenshot_hash?: string | null;
  quality_level?: string | null;
  selection_status?: string | null;
  commercial_risk?: string | null;
  last_scanned_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  notes?: string | null;
};

export type SkillRepoProfile = {
  id: number;
  repo_id: number;
  repo_name?: string | null;
  repo_url?: string | null;
  skill_type?: string | null;
  target_platform?: string | null;
  runtime_stack?: string | null;
  capabilities?: string[];
  input_types?: string[];
  output_types?: string[];
  use_cases?: string[];
  tools?: string[];
  install_method?: string | null;
  configuration_notes?: string | null;
  reuse_mode?: string | null;
  summary_cn?: string | null;
  ai_summary_cn?: string | null;
  evidence?: string | null;
  ai_reason_cn?: string | null;
  tags?: string[];
  confidence?: number | null;
  source_ai_config_id?: number | null;
  quality_level?: string | null;
  selection_status?: string | null;
  commercial_risk?: string | null;
  last_scanned_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  notes?: string | null;
};

export type PairCandidate = {
  id: number;
  repo_id: number;
  repo_name: string;
  repo_url: string;
  source_page_url: string;
  source_file: string;
  source_heading?: string | null;
  prompt_candidate_id?: number | null;
  image_candidate_id?: number | null;
  original_prompt: string;
  image_original_url: string;
  image_local_path: string;
  cloud_storage_url?: string | null;
  image_hash: string;
  match_type: string;
  match_score: number;
  structural_score: number;
  distance_score: number;
  filename_score: number;
  semantic_score: number;
  penalty_score: number;
  evidence: string;
  review_status: string;
  review_reason?: string | null;
  selection_status: string;
  created_pair_id?: number | null;
  created_at: string;
  updated_at: string;
};

export type Tag = {
  id: number;
  name: string;
  type: string;
  created_at: string;
};

export type DashboardStats = {
  counts: {
    repo_count: number;
    pair_count: number;
    featured_count: number;
    pending_count: number;
    today_new_count: number;
    today_updated_count: number;
  };
  categories: Array<{ category: string; count: number }>;
  recent_pairs: PromptPair[];
  logs: Array<Record<string, string | number>>;
};

export type GithubAuthStatus = {
  configured: boolean;
  connected: boolean;
  client_id?: string;
  login?: string;
  name?: string;
  avatar_url?: string;
  html_url?: string;
  scope?: string;
  token_type?: string;
  source: "env" | "local" | "none";
  updated_at?: string;
};

export type GithubDeviceStart = {
  session_id: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete?: string;
  expires_in: number;
  interval: number;
};

export type GithubDevicePoll = {
  status: "pending" | "connected" | "expired" | "error";
  message?: string;
  interval?: number;
  auth?: GithubAuthStatus;
};

export type AiProvider = "deepseek" | "lm_studio";

export type AiConfig = {
  id: number;
  name: string;
  provider: AiProvider;
  provider_label?: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  is_default: boolean;
  enabled: boolean;
  temperature: number;
  timeout_seconds: number;
  last_test_status?: "success" | "failed" | null;
  last_test_message?: string | null;
  last_test_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type AiConfigPayload = {
  name?: string;
  provider?: AiProvider;
  base_url?: string | null;
  api_key?: string | null;
  clear_api_key?: boolean;
  model?: string | null;
  is_default?: boolean;
  enabled?: boolean;
  temperature?: number;
  timeout_seconds?: number;
};

export type AiTestResult = {
  status: "success" | "failed";
  message: string;
  tested_at: string;
  latency_ms: number;
  config?: AiConfig;
};

export type AiModelsResult = {
  status: "success" | "failed";
  message: string;
  models: string[];
  latency_ms: number;
};

export type ScheduleType = "interval_minutes" | "daily_time" | "weekly_time";
export type ScheduledTaskStatus = "active" | "paused";
export type TaskRunStatus = "started" | "success" | "skipped" | "failed";
export type ScheduledTaskType = "github_incremental_search";

export type ScheduledTask = {
  id: number;
  name: string;
  task_type: ScheduledTaskType;
  status: ScheduledTaskStatus;
  schedule_type: ScheduleType;
  interval_minutes?: number | null;
  daily_time?: string | null;
  weekly_day?: number | null;
  weekly_time?: string | null;
  timezone: string;
  categories?: string[] | null;
  keywords?: string[] | null;
  per_keyword_limit: number;
  allow_anonymous: boolean;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_finished_at?: string | null;
  last_status?: TaskRunStatus | null;
  last_summary?: string | null;
  last_error?: string | null;
  running: boolean;
  created_at: string;
  updated_at: string;
};

export type ScheduledTaskPayload = {
  name?: string;
  task_type?: ScheduledTaskType;
  status?: ScheduledTaskStatus;
  schedule_type?: ScheduleType;
  interval_minutes?: number | null;
  daily_time?: string | null;
  weekly_day?: number | null;
  weekly_time?: string | null;
  categories?: string[] | null;
  keywords?: string[] | null;
  per_keyword_limit?: number;
  allow_anonymous?: boolean;
};

export type TaskRun = {
  id: number;
  task_id: number;
  task_name: string;
  task_type: string;
  trigger_type: "manual" | "scheduled";
  status: TaskRunStatus;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  summary?: string | null;
  error?: string | null;
  result_json?: string | null;
  created_at: string;
};

export type AgentSource = {
  type: "repo" | "prompt_pair" | "pair_candidate" | "web_ui_prompt" | "skill_repo";
  id: number;
  title: string;
  tool?: string;
  route?: string;
  external_url?: string | null;
  preview_image?: string | null;
  snippet?: string | null;
  matched_reason?: string | null;
  data: Record<string, unknown>;
};

export type AgentAction = {
  type: string;
  memory_id?: number;
  label?: string;
};

export type AgentMessage = {
  id: number;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  sources_json?: string | null;
  actions_json?: string | null;
  sources?: AgentSource[];
  actions?: AgentAction[];
  created_at: string;
};

export type AgentThread = {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type AgentChatResult = {
  thread_id: string;
  message: AgentMessage;
  sources: AgentSource[];
  actions: AgentAction[];
  tool_plan?: Record<string, unknown>;
};

export type AgentMemory = {
  id: number;
  memory_type: "user_preference" | "scan_pattern" | "review_decision" | "query_context";
  scope: string;
  repo_id?: number | null;
  content: string;
  content_json?: string | null;
  status: "pending_review" | "active" | "rejected" | "archived" | "disabled";
  confidence: number;
  source?: string | null;
  created_at: string;
  updated_at: string;
  last_used_at?: string | null;
};

export type AgentMemoryPayload = {
  memory_type?: AgentMemory["memory_type"];
  scope?: string;
  repo_id?: number | null;
  content?: string;
  content_json?: string | null;
  status?: AgentMemory["status"];
  confidence?: number;
  source?: string;
};

export type AnnotationQueueItem = PromptPair & {
  tag_count: number;
  latest_suggestion_id?: number | null;
  latest_suggestion_status?: string | null;
  annotation_status: "unannotated" | "annotated" | "has_suggestion" | string;
};

export type AnnotationRun = {
  id: number;
  status: "queued" | "running" | "succeeded" | "failed" | "cancel_requested" | "canceled" | string;
  total_items: number;
  processed_items: number;
  created_suggestions: number;
  current_pair_id?: number | null;
  ai_config_id?: number | null;
  options_json?: string | null;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at?: string | null;
  cancel_requested?: number;
};

export type AnnotationRunCreate = {
  limit?: number;
  pair_ids?: number[] | null;
  ai_config_id?: number | null;
  allow_pending_suggestions?: boolean;
  search?: string;
  category?: string;
  scenario?: string;
  selection_status?: string;
  annotation_status?: string;
};

export type AnnotationRunUpdate = {
  limit?: number;
  ai_config_id?: number | null;
  allow_pending_suggestions?: boolean;
  annotation_status?: string;
};

export type AnnotationSuggestion = {
  id: number;
  run_id?: number | null;
  pair_id: number;
  status: "pending_review" | "accepted" | "rejected" | "failed" | "superseded" | string;
  prompt_language?: string | null;
  suggested_cn_explanation?: string | null;
  suggested_tags_json?: string | null;
  image_type_cn?: string | null;
  reason_cn?: string | null;
  confidence: number;
  error?: string | null;
  created_at: string;
  updated_at?: string | null;
  accepted_at?: string | null;
  repo_name?: string | null;
  repo_url?: string | null;
  original_prompt?: string | null;
  prompt_cn_explanation?: string | null;
  image_local_path?: string | null;
  category?: string | null;
  scenario?: string | null;
  selection_status?: string | null;
};

export type AnnotationSuggestionPatch = {
  suggested_cn_explanation?: string;
  suggested_tags?: string[];
  image_type_cn?: string;
  reason_cn?: string;
  confidence?: number;
};
