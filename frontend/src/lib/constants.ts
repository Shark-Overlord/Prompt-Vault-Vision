import {
  Brain,
  Bot,
  CalendarClock,
  ClipboardCheck,
  ClipboardList,
  ClipboardPenLine,
  Database,
  Download,
  Image,
  LayoutDashboard,
  PanelsTopLeft,
  Puzzle,
  Settings2,
  Video
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

export const navGroups: NavGroup[] = [
  {
    label: "工作台",
    items: [
      { label: "仪表盘", href: "/", icon: LayoutDashboard },
      { label: "智能体", href: "/agent", icon: Bot }
    ]
  },
  {
    label: "仓库采集",
    items: [
      { label: "资源库", href: "/repos", icon: Database },
      { label: "定时任务", href: "/scheduled-tasks", icon: CalendarClock },
      { label: "仓库扫描任务", href: "/repo-scan-runs", icon: ClipboardList },
      { label: "候选配对", href: "/pair-candidates", icon: ClipboardCheck }
    ]
  },
  {
    label: "Prompt 资产",
    items: [
      { label: "Web UI 资产库", href: "/prompt-assets/web-ui", icon: PanelsTopLeft },
      { label: "图像生成资产库", href: "/prompt-assets/image-generation", icon: Image },
      { label: "Skill 资产库", href: "/prompt-assets/skills", icon: Puzzle },
      { label: "视频生成资产库", href: "/prompt-assets/video-generation", icon: Video },
      { label: "翻译标注", href: "/annotation-tasks", icon: ClipboardPenLine }
    ]
  },
  {
    label: "AI 智能",
    items: [{ label: "记忆", href: "/agent/memory", icon: Brain }]
  },
  {
    label: "系统与输出",
    items: [
      { label: "导出", href: "/export", icon: Download },
      { label: "系统配置", href: "/settings", icon: Settings2 }
    ]
  }
];

export const navItems = navGroups.flatMap((group) => group.items);

export const categoryLabels: Record<string, string> = {
  web_ui_prompt: "Web UI",
  image_generation_prompt: "图像生成",
  skill_repository: "Skill 仓库",
  video_generation_prompt: "视频生成"
};

export const repoDetectionStrategyLabels: Record<string, string> = {
  web_ui_prompt: "Web UI 仓库级标注策略",
  image_generation_prompt: "图像生成 Prompt 检测策略",
  skill_repository: "Skill 仓库级标注策略",
  video_generation_prompt: "视频生成 Prompt 检测策略"
};

export const statusLabels: Record<string, string> = {
  featured: "精选",
  normal: "普通",
  reference: "仅参考",
  rejected: "拒绝",
  pending_review: "待分级"
};

export const repoStatusLabels: Record<string, string> = {
  ...statusLabels,
  ready_to_scan: "待扫描",
  discovery_review: "待观察",
  active: "可用",
  archived: "已归档"
};

export const qualityLabels: Record<string, string> = {
  excellent: "高价值",
  good: "可复用",
  normal: "普通",
  reference: "参考",
  pending_review: "待分级",
  rejected: "不建议"
};

export const repoQualityLabels: Record<string, string> = {
  ...qualityLabels,
  candidate_review: "待观察",
  rejected: "不建议"
};

export const visualAssetTypeLabels: Record<string, string> = {
  creative_image: "创意图",
  product_image: "商品图",
  scene_image: "场景图",
  character_image: "角色图",
  cover_image: "封面图",
  uncategorized: "未分类"
};

export const visualAssetTypes = [
  "creative_image",
  "product_image",
  "scene_image",
  "character_image",
  "cover_image"
] as const;

export const scenarios = [
  "landing_page",
  "dashboard",
  "app_ui",
  "saas_ui",
  "product_image",
  "poster",
  "commercial_visual",
  "product_video",
  "cinematic_video",
  "short_video",
  "storyboard",
  "other"
];
