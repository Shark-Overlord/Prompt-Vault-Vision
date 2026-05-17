import {
  CalendarClock,
  Brain,
  Bot,
  ClipboardCheck,
  ClipboardList,
  ClipboardPenLine,
  Database,
  Download,
  GalleryVerticalEnd,
  LayoutDashboard,
  Settings2,
  ShieldAlert
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
      { label: "Prompt 效果库", href: "/prompts", icon: GalleryVerticalEnd },
      { label: "质量分级", href: "/pending", icon: ShieldAlert },
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
  web_ui_prompt: "Web UI Prompt",
  image_generation_prompt: "图像生成",
  image_editing_prompt: "图像编辑",
  video_generation_prompt: "视频生成"
};

export const repoDetectionStrategyLabels: Record<string, string> = {
  web_ui_prompt: "Web UI Prompt 检测策略",
  image_generation_prompt: "图像生成 Prompt 检测策略",
  image_editing_prompt: "图像编辑 Prompt 检测策略",
  video_generation_prompt: "视频生成 Prompt 检测策略"
};

export const statusLabels: Record<string, string> = {
  featured: "精选",
  normal: "普通",
  reference: "仅参考",
  rejected: "拒绝",
  pending_review: "待分级"
};

export const qualityLabels: Record<string, string> = {
  excellent: "高价值",
  good: "可复用",
  normal: "普通",
  reference: "参考",
  pending_review: "待分级",
  rejected: "不建议"
};

export const scenarios = [
  "landing_page",
  "dashboard",
  "app_ui",
  "saas_ui",
  "product_image",
  "poster",
  "commercial_visual",
  "image_editing",
  "product_video",
  "cinematic_video",
  "short_video",
  "storyboard",
  "other"
];
