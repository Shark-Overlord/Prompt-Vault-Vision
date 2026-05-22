import { motion } from "framer-motion";
import { Blocks, ExternalLink, Layers3, Ruler, Star } from "lucide-react";
import type { WebUiRepoProfile } from "../../lib/types";
import { assetUrl, cn, truncate } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

const profileTypeLabels: Record<string, string> = {
  design_spec: "设计规范",
  component_library: "组件库"
};

const libraryKindLabels: Record<string, string> = {
  shadcn_registry: "shadcn Registry",
  design_system_library: "设计系统库",
  blocks_library: "区块库",
  component_collection: "组件合集"
};

export function WebUiRepoCard({ item, onToggleFavorite }: { item: WebUiRepoProfile; onToggleFavorite: (item: WebUiRepoProfile) => void }) {
  const image = assetUrl(item.screenshot_local_path);
  const title = item.repo_name || `Web UI Repo #${item.repo_id}`;
  const summary = item.ai_summary_cn || item.summary_cn || item.evidence || "";
  const favorite = item.selection_status === "featured";
  const targetText =
    item.profile_type === "component_library"
      ? (item.supported_frontend_types || []).slice(0, 4).join(" / ") || "待 AI 判断"
      : (item.component_focus || []).slice(0, 4).join(" / ") || "待补充规范焦点";
  const typeLabel =
    item.profile_type === "component_library"
      ? libraryKindLabels[item.library_kind || ""] || item.library_kind || "组件库"
      : "设计规范仓库";

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      className="group relative overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm"
    >
      <div className="relative min-h-52 bg-muted">
        {image ? (
          <img src={image} alt={title} className="h-full max-h-[360px] min-h-52 w-full object-cover" loading="lazy" />
        ) : (
          <div className="grid h-64 place-items-center bg-muted/40 text-muted-foreground">
            {item.profile_type === "component_library" ? <Blocks className="h-10 w-10" /> : <Ruler className="h-10 w-10" />}
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/25 to-transparent opacity-95" />
        <div className="absolute left-3 top-3 flex flex-wrap gap-2">
          <Badge>{profileTypeLabels[item.profile_type] || item.profile_type}</Badge>
          <Badge variant="secondary">{typeLabel}</Badge>
        </div>
        <Button
          size="icon-sm"
          variant={favorite ? "secondary" : "ghost"}
          className={cn("absolute right-3 top-3 bg-background/80 backdrop-blur", favorite && "text-amber-300")}
          onClick={() => onToggleFavorite(item)}
          title={favorite ? "取消收藏" : "收藏"}
        >
          <Star className={cn("h-4 w-4", favorite && "fill-current")} />
        </Button>
      </div>

      <div className="space-y-4 p-4">
        <div className="space-y-2">
          <div className="text-base font-medium leading-6">{title}</div>
          <p className="text-sm leading-6 text-muted-foreground">{truncate(summary, 180)}</p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {(item.style_keywords || []).slice(0, 6).map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
        </div>

        <div className="space-y-2 rounded-lg border bg-muted/20 p-3 text-sm">
          <div className="flex items-center gap-2 text-foreground">
            <Layers3 className="h-4 w-4" />
            <span className="font-medium">适用前端</span>
          </div>
          <div className="text-xs leading-5 text-muted-foreground">{targetText}</div>
          {item.reuse_mode && <div className="text-xs text-muted-foreground">复用方式：{item.reuse_mode}</div>}
          {item.ui_stack && <div className="text-xs text-muted-foreground">技术栈：{item.ui_stack}</div>}
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {favorite ? <Badge className="border-amber-300/40 bg-amber-300/10 text-amber-200" variant="outline">已收藏</Badge> : null}
            {typeof item.confidence === "number" && <Badge variant="outline">得分 {item.confidence}</Badge>}
          </div>
          {item.repo_url && (
            <Button variant="ghost" size="icon" asChild>
              <a href={item.repo_url} target="_blank" rel="noreferrer" aria-label={`打开 ${title}`}>
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
        </div>
      </div>
    </motion.article>
  );
}
