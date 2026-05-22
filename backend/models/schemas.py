from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PromptPairPatch(BaseModel):
    selection_status: Optional[str] = Field(default=None)
    quality_level: Optional[str] = None
    effect_review: Optional[str] = None
    reusable_value: Optional[str] = None
    commercial_risk: Optional[str] = None
    prompt_cn_explanation: Optional[str] = None
    visual_asset_type: Optional[str] = None
    visual_asset_type_confidence: Optional[int] = Field(default=None, ge=0, le=100)
    visual_asset_type_reason: Optional[str] = None
    tags: Optional[List[str]] = None


class PromptPairBatchUpdate(BaseModel):
    ids: List[int] = Field(default_factory=list)
    selection_status: Optional[str] = None
    quality_level: Optional[str] = None
    visual_asset_type: Optional[str] = None
    tags: Optional[List[str]] = None


class WebUiPromptCreate(BaseModel):
    repo_id: Optional[int] = None
    repo_name: Optional[str] = None
    repo_url: Optional[str] = None
    source_page_url: Optional[str] = None
    source_file: Optional[str] = None
    source_heading: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    asset_group: str = "design_spec"
    asset_type: str = "component_prompt"
    library_kind: Optional[str] = None
    component_type: Optional[str] = None
    page_type: Optional[str] = None
    framework: Optional[str] = None
    prompt_text: str
    prompt_cn_translation: Optional[str] = None
    design_rules: Optional[str] = None
    ui_pattern: Optional[str] = None
    screenshot_original_url: Optional[str] = None
    screenshot_local_path: Optional[str] = None
    screenshot_hash: Optional[str] = None
    tags: Optional[List[str]] = None
    quality_level: str = "pending_review"
    selection_status: str = "pending_review"
    reuse_value: Optional[str] = None
    evidence: Optional[str] = None
    confidence: int = Field(default=0, ge=0, le=100)
    content_hash: Optional[str] = None
    license: Optional[str] = None
    commercial_risk: str = "unknown"
    generated_by: Optional[str] = None
    notes: Optional[str] = None


class WebUiPromptUpdate(BaseModel):
    repo_id: Optional[int] = None
    repo_name: Optional[str] = None
    repo_url: Optional[str] = None
    source_page_url: Optional[str] = None
    source_file: Optional[str] = None
    source_heading: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    asset_group: Optional[str] = None
    asset_type: Optional[str] = None
    library_kind: Optional[str] = None
    component_type: Optional[str] = None
    page_type: Optional[str] = None
    framework: Optional[str] = None
    prompt_text: Optional[str] = None
    prompt_cn_translation: Optional[str] = None
    design_rules: Optional[str] = None
    ui_pattern: Optional[str] = None
    screenshot_original_url: Optional[str] = None
    screenshot_local_path: Optional[str] = None
    screenshot_hash: Optional[str] = None
    tags: Optional[List[str]] = None
    quality_level: Optional[str] = None
    selection_status: Optional[str] = None
    reuse_value: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=0, le=100)
    content_hash: Optional[str] = None
    license: Optional[str] = None
    commercial_risk: Optional[str] = None
    generated_by: Optional[str] = None
    notes: Optional[str] = None


class WebUiRepoProfileUpdate(BaseModel):
    profile_type: Optional[str] = None
    library_kind: Optional[str] = None
    ui_stack: Optional[str] = None
    supported_frontend_types: Optional[List[str]] = None
    component_focus: Optional[List[str]] = None
    style_keywords: Optional[List[str]] = None
    reuse_mode: Optional[str] = None
    summary_cn: Optional[str] = None
    ai_summary_cn: Optional[str] = None
    evidence: Optional[str] = None
    ai_reason_cn: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=0, le=100)
    quality_level: Optional[str] = None
    selection_status: Optional[str] = None
    commercial_risk: Optional[str] = None
    notes: Optional[str] = None


class SkillRepoProfileUpdate(BaseModel):
    skill_type: Optional[str] = None
    target_platform: Optional[str] = None
    runtime_stack: Optional[str] = None
    capabilities: Optional[List[str]] = None
    input_types: Optional[List[str]] = None
    output_types: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    install_method: Optional[str] = None
    configuration_notes: Optional[str] = None
    reuse_mode: Optional[str] = None
    summary_cn: Optional[str] = None
    ai_summary_cn: Optional[str] = None
    evidence: Optional[str] = None
    ai_reason_cn: Optional[str] = None
    tags: Optional[List[str]] = None
    confidence: Optional[int] = Field(default=None, ge=0, le=100)
    quality_level: Optional[str] = None
    selection_status: Optional[str] = None
    commercial_risk: Optional[str] = None
    notes: Optional[str] = None


class TagCreate(BaseModel):
    name: str
    type: str = "custom"


class GithubSearchRequest(BaseModel):
    categories: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    per_keyword_limit: int = 5
    allow_anonymous: bool = False


class RepoCreate(BaseModel):
    repo_name: Optional[str] = None
    owner: Optional[str] = None
    repo_url: str
    canonical_url: Optional[str] = None
    stars: int = 0
    forks: int = 0
    license: str = "unknown"
    is_fork: int = 0
    parent_repo: Optional[str] = None
    resource_type: str = "github_repo"
    category: str = "image_generation_prompt"
    quality_level: str = "pending_review"
    status: str = "pending_review"
    summary: Optional[str] = None
    notes: Optional[str] = None


class RepoUpdate(BaseModel):
    repo_name: Optional[str] = None
    owner: Optional[str] = None
    repo_url: Optional[str] = None
    canonical_url: Optional[str] = None
    stars: Optional[int] = None
    forks: Optional[int] = None
    license: Optional[str] = None
    is_fork: Optional[int] = None
    parent_repo: Optional[str] = None
    resource_type: Optional[str] = None
    category: Optional[str] = None
    quality_level: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    notes: Optional[str] = None


class RepoBatchRequest(BaseModel):
    ids: List[int] = Field(default_factory=list)


class RepoScanRequest(BaseModel):
    use_ai: bool = False
    ai_config_id: Optional[int] = None
    template_id: Optional[int] = None
    generate_template: bool = False
    scan_mode: Optional[str] = None


class RepoScanTemplatePatch(BaseModel):
    status: Optional[str] = None
    content_json: Optional[str] = None
    summary_cn: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None


class ExportRequest(BaseModel):
    format: str = "markdown"
    selection_status: str = "featured"
    category: Optional[str] = None


class GithubClientConfig(BaseModel):
    client_id: str


class GithubDeviceStartRequest(BaseModel):
    client_id: Optional[str] = None
    scope: str = "read:user"


class GithubDevicePollRequest(BaseModel):
    session_id: str


class AiConfigCreate(BaseModel):
    name: str
    provider: str = "deepseek"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    is_default: bool = False
    enabled: bool = True
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout_seconds: int = Field(default=60, ge=5, le=300)


class AiConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    clear_api_key: Optional[bool] = None
    model: Optional[str] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=300)


class AgentChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class AgentMemoryCreate(BaseModel):
    memory_type: str = "user_preference"
    scope: str = "global"
    repo_id: Optional[int] = None
    content: str
    content_json: Optional[str] = None
    status: str = "pending_review"
    confidence: int = Field(default=70, ge=0, le=100)
    source: str = "manual"


class AgentMemoryUpdate(BaseModel):
    memory_type: Optional[str] = None
    scope: Optional[str] = None
    repo_id: Optional[int] = None
    content: Optional[str] = None
    content_json: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=0, le=100)
    source: Optional[str] = None


class AnnotationRunCreate(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    pair_ids: Optional[List[int]] = None
    ai_config_id: Optional[int] = None
    allow_pending_suggestions: bool = False
    search: Optional[str] = None
    category: Optional[str] = None
    scenario: Optional[str] = None
    selection_status: Optional[str] = None
    annotation_status: str = "unannotated"


class AnnotationRunUpdate(BaseModel):
    limit: Optional[int] = Field(default=None, ge=1, le=200)
    ai_config_id: Optional[int] = None
    allow_pending_suggestions: Optional[bool] = None
    annotation_status: Optional[str] = None


class AnnotationSuggestionPatch(BaseModel):
    suggested_cn_explanation: Optional[str] = None
    suggested_tags: Optional[List[str]] = None
    image_type_cn: Optional[str] = None
    reason_cn: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=0, le=100)


class ScheduledTaskBase(BaseModel):
    name: Optional[str] = None
    task_type: str = "github_incremental_search"
    status: str = "paused"
    schedule_type: Optional[str] = None
    interval_minutes: Optional[int] = None
    daily_time: Optional[str] = None
    weekly_day: Optional[int] = None
    weekly_time: Optional[str] = None
    timezone: str = "Asia/Shanghai"
    categories: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    per_keyword_limit: int = 5
    allow_anonymous: bool = False


class ScheduledTaskCreate(ScheduledTaskBase):
    name: str
    schedule_type: str


class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    schedule_type: Optional[str] = None
    interval_minutes: Optional[int] = None
    daily_time: Optional[str] = None
    weekly_day: Optional[int] = None
    weekly_time: Optional[str] = None
    timezone: Optional[str] = None
    categories: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    per_keyword_limit: Optional[int] = None
    allow_anonymous: Optional[bool] = None
