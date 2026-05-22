import { Database, ExternalLink, FileText, GitBranch, PanelsTopLeft, Puzzle } from "lucide-react";
import { useState } from "react";
import type { AgentSource } from "../../lib/types";
import { assetUrl, truncate } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "../ui/sheet";

function iconFor(type: AgentSource["type"]) {
  if (type === "repo") return <GitBranch className="h-3.5 w-3.5" />;
  if (type === "prompt_pair") return <FileText className="h-3.5 w-3.5" />;
  if (type === "web_ui_prompt") return <PanelsTopLeft className="h-3.5 w-3.5" />;
  if (type === "skill_repo") return <Puzzle className="h-3.5 w-3.5" />;
  return <Database className="h-3.5 w-3.5" />;
}

function sourceTypeLabel(type: AgentSource["type"]) {
  if (type === "repo") return "资源仓库";
  if (type === "prompt_pair") return "Prompt 效果对";
  if (type === "web_ui_prompt") return "Web UI 资产";
  if (type === "skill_repo") return "Skill 资产";
  return "候选配对";
}

function textValue(value: unknown) {
  return typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);
}

function SourcePreview({ source }: { source: AgentSource }) {
  const data = source.data || {};
  const prompt = textValue(
    data.prompt_cn_explanation ||
      data.prompt_cn_translation ||
      data.original_prompt ||
      data.prompt_text ||
      data.ai_summary_cn ||
      data.summary_cn ||
      source.snippet
  );
  const evidence = textValue(data.effect_review || data.evidence || data.pair_evidence || data.ai_reason_cn || source.matched_reason);
  const repoName = textValue(data.repo_name || source.title);
  const image = source.preview_image;

  return (
    <div className="grid gap-5 xl:grid-cols-[320px_1fr]">
      <div className="overflow-hidden rounded-lg border bg-muted/30">
        {image ? (
          <img src={assetUrl(image)} alt={source.title} className="max-h-[460px] w-full object-contain" />
        ) : (
          <div className="grid h-64 place-items-center text-muted-foreground">{iconFor(source.type)}</div>
        )}
      </div>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{sourceTypeLabel(source.type)}</Badge>
          {source.tool && <Badge variant="outline">{source.tool}</Badge>}
          {textValue(data.category) && <Badge variant="outline">{textValue(data.category)}</Badge>}
          {textValue(data.scenario || data.asset_type || data.skill_type) && (
            <Badge variant="outline">{textValue(data.scenario || data.asset_type || data.skill_type)}</Badge>
          )}
        </div>
        <div>
          <div className="text-xs text-muted-foreground">来源</div>
          <div className="mt-1 font-medium">{repoName}</div>
        </div>
        {prompt && (
          <div>
            <div className="text-xs text-muted-foreground">匹配内容</div>
            <div className="mt-1 max-h-40 overflow-y-auto rounded-md border bg-background/50 p-3 text-sm leading-6">{prompt}</div>
          </div>
        )}
        {source.type === "skill_repo" && (
          <div className="grid gap-2 rounded-md border bg-muted/20 p-3 text-xs text-muted-foreground md:grid-cols-2">
            <div>目标平台：{textValue(data.target_platform) || "-"}</div>
            <div>运行栈：{textValue(data.runtime_stack) || "-"}</div>
            <div className="md:col-span-2">复用方式：{textValue(data.reuse_mode) || "-"}</div>
          </div>
        )}
        {evidence && (
          <div>
            <div className="text-xs text-muted-foreground">证据 / 原因</div>
            <div className="mt-1 text-sm leading-6 text-muted-foreground">{evidence}</div>
          </div>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          {source.route && (
            <Button variant="secondary" size="sm" asChild>
              <a href={source.route}>跳转资产库页面</a>
            </Button>
          )}
          {source.external_url && (
            <Button variant="outline" size="sm" asChild>
              <a href={source.external_url} target="_blank" rel="noreferrer">
                打开来源
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export function AgentSourceDrawer({ source, open, onOpenChange }: { source: AgentSource | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[50vw] min-w-[720px] overflow-y-auto sm:max-w-none data-[side=right]:w-[50vw] data-[side=right]:min-w-[720px] data-[side=right]:sm:max-w-none">
        {source && (
          <>
            <SheetHeader className="border-b">
              <SheetTitle>{source.title}</SheetTitle>
              <SheetDescription>{source.matched_reason || "来自本地 SQLite 工具检索结果。"}</SheetDescription>
            </SheetHeader>
            <div className="p-4">
              <SourcePreview source={source} />
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

export function AgentSourceList({ sources, onOpenSource }: { sources: AgentSource[]; onOpenSource?: (source: AgentSource) => void }) {
  const [fallbackSelected, setFallbackSelected] = useState<AgentSource | null>(null);
  if (!sources?.length) return null;
  const openSource = (source: AgentSource) => {
    if (onOpenSource) onOpenSource(source);
    else setFallbackSelected(source);
  };
  return (
    <div className="mt-3 space-y-2">
      <div className="text-xs text-muted-foreground">工具结果，点击圆点查看</div>
      <div className="flex flex-wrap gap-2">
        {sources.slice(0, 8).map((source) => (
          <button
            key={`${source.type}-${source.id}`}
            type="button"
            className="inline-flex max-w-full items-center gap-2 rounded-full border bg-secondary px-2.5 py-1.5 text-xs text-secondary-foreground transition hover:border-primary/50 hover:bg-primary/10"
            onClick={() => openSource(source)}
          >
            <span className="h-2.5 w-2.5 rounded-full bg-foreground shadow-[0_0_10px_rgba(255,255,255,0.45)]" />
            {iconFor(source.type)}
            <span className="truncate">{truncate(source.title, 42)}</span>
          </button>
        ))}
      </div>
      {!onOpenSource && <AgentSourceDrawer source={fallbackSelected} open={Boolean(fallbackSelected)} onOpenChange={(open) => !open && setFallbackSelected(null)} />}
    </div>
  );
}
