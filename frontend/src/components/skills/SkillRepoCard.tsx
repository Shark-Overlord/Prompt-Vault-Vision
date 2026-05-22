import { motion } from "framer-motion";
import { Bot, ExternalLink, Puzzle, Star, TerminalSquare, Wrench } from "lucide-react";
import type { SkillRepoProfile } from "../../lib/types";
import { cn, truncate } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

const skillTypeLabels: Record<string, string> = {
  mcp_server: "MCP 服务",
  agent_toolkit: "Agent 工具包",
  claude_skill: "Claude Skill",
  codex_skill: "Codex Skill",
  cursor_rule_pack: "Cursor 规则",
  desktop_ai_skill: "桌面 AI Skill",
  workflow_pack: "工作流包",
  other: "Skill 仓库"
};

export function SkillRepoCard({ item, onToggleFavorite }: { item: SkillRepoProfile; onToggleFavorite: (item: SkillRepoProfile) => void }) {
  const title = item.repo_name || `Skill Repo #${item.repo_id}`;
  const summary = item.ai_summary_cn || item.summary_cn || item.evidence || "";
  const capabilities = item.capabilities || [];
  const useCases = item.use_cases || [];
  const tools = item.tools || [];
  const tags = item.tags || [];
  const favorite = item.selection_status === "featured";
  const typeLabel = skillTypeLabels[item.skill_type || ""] || item.skill_type || "Skill 仓库";

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      className="group relative overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm"
    >
      <div className="relative grid min-h-48 place-items-center overflow-hidden bg-muted/35">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,hsl(var(--border))_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--border))_1px,transparent_1px)] bg-[size:28px_28px] opacity-20" />
        <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-background to-transparent" />
        <div className="relative grid h-16 w-16 place-items-center rounded-xl border bg-background/70 shadow-sm">
          <Puzzle className="h-8 w-8 text-muted-foreground" />
        </div>
        <div className="absolute left-3 top-3 flex flex-wrap gap-2">
          <Badge>{typeLabel}</Badge>
          {item.target_platform && <Badge variant="secondary">{truncate(item.target_platform, 28)}</Badge>}
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
          <p className="text-sm leading-6 text-muted-foreground">{truncate(summary, 190)}</p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {[...tags, ...capabilities].filter(Boolean).slice(0, 8).map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
        </div>

        <div className="space-y-2 rounded-lg border bg-muted/20 p-3 text-sm">
          <div className="flex items-center gap-2 text-foreground">
            <Bot className="h-4 w-4" />
            <span className="font-medium">面向场景</span>
          </div>
          <div className="text-xs leading-5 text-muted-foreground">{useCases.slice(0, 5).join(" / ") || "待 AI 标注具体场景"}</div>
          {item.runtime_stack && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <TerminalSquare className="h-3.5 w-3.5" />
              {item.runtime_stack}
            </div>
          )}
          {tools.length > 0 && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Wrench className="h-3.5 w-3.5" />
              {tools.slice(0, 4).join(" / ")}
            </div>
          )}
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
