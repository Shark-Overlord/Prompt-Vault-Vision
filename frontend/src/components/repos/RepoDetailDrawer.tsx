import type { ReactNode } from "react";
import { ExternalLink, GitFork, Image, Link2, Pencil, RefreshCw, Star, Trash2 } from "lucide-react";
import { categoryLabels } from "../../lib/constants";
import type { Repo } from "../../lib/types";
import { QualityBadge } from "../prompts/QualityBadge";
import { StatusBadge } from "../prompts/StatusBadge";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "../ui/sheet";
import { RepoScanTemplatePanel } from "./RepoScanTemplatePanel";

function splitIsoDateTime(value?: string | null) {
  if (!value) return null;
  const cleaned = value.replace(/([+-]\d{2}:\d{2}|Z)$/i, "");
  const [date, rawTime = ""] = cleaned.split("T");
  if (!date) return null;
  return {
    date,
    time: rawTime.slice(0, 8)
  };
}

function DateBlock({ label, value }: { label: string; value?: string | null }) {
  const parts = splitIsoDateTime(value);
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      {parts ? (
        <div className="mt-1 text-sm leading-5">
          <div>{parts.date}</div>
          <div className="text-muted-foreground">{parts.time || "-"}</div>
        </div>
      ) : (
        <div className="mt-1 text-sm text-muted-foreground">-</div>
      )}
    </div>
  );
}

function MetricItem({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg border bg-muted/20 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

export function RepoDetailDrawer({
  repo,
  onClose,
  onScan,
  onEdit,
  onDelete,
  busy
}: {
  repo: Repo | null;
  onClose: () => void;
  onScan?: (repo: Repo) => void;
  onEdit?: (repo: Repo) => void;
  onDelete?: (repo: Repo) => void;
  busy?: boolean;
}) {
  return (
    <Sheet open={Boolean(repo)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[88vw] overflow-y-auto data-[side=right]:sm:max-w-2xl">
        {repo && (
          <>
            <SheetHeader className="border-b pr-12">
              <SheetDescription>仓库资源详情</SheetDescription>
              <SheetTitle className="break-words text-xl">{repo.repo_name}</SheetTitle>
              <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                <Link2 className="h-4 w-4" />
                <span className="truncate">{repo.owner}</span>
              </div>
            </SheetHeader>

            <div className="space-y-5 p-5">
              <div className="flex flex-wrap gap-2">
                <Badge>{categoryLabels[repo.category] || repo.category}</Badge>
                <QualityBadge value={repo.quality_level} />
                <StatusBadge value={repo.status} />
                <Badge variant={repo.license === "unknown" ? "outline" : "secondary"}>{repo.license || "unknown"}</Badge>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <MetricItem icon={<Star className="h-3.5 w-3.5" />} label="Stars" value={repo.stars ?? 0} />
                <MetricItem icon={<GitFork className="h-3.5 w-3.5" />} label="Forks" value={repo.forks ?? 0} />
                <MetricItem icon={<Image className="h-3.5 w-3.5" />} label="效果对" value={repo.prompt_effect_pair_count ?? 0} />
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>资源摘要</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{repo.summary || "暂无摘要"}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>索引信息</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-4 sm:grid-cols-2">
                  <DateBlock label="最近检查" value={repo.last_checked_at} />
                  <DateBlock label="最近更新" value={repo.last_updated_at} />
                  <DateBlock label="入库时间" value={repo.created_at} />
                  <div>
                    <div className="text-xs text-muted-foreground">预览图</div>
                    <div className="mt-1 text-sm">{repo.has_preview_images ? "有" : "无"}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Prompt 效果对</div>
                    <div className="mt-1 text-sm">{repo.has_prompt_effect_pairs ? "已发现" : "未发现"}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Fork</div>
                    <div className="mt-1 text-sm">{repo.is_fork ? "是" : "否"}</div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>来源链接</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="break-all rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">{repo.canonical_url || repo.repo_url}</div>
                  <Button variant="outline" onClick={() => window.open(repo.repo_url || repo.canonical_url, "_blank")}>
                    <ExternalLink className="h-4 w-4" />
                    打开 GitHub
                  </Button>
                </CardContent>
              </Card>

              <RepoScanTemplatePanel repo={repo} />
            </div>

            <div className="sticky bottom-0 mt-auto flex flex-wrap gap-2 border-t bg-popover/95 p-4 backdrop-blur">
              <Button variant="secondary" disabled={busy} onClick={() => onScan?.(repo)}>
                <RefreshCw className={busy ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
                扫描仓库
              </Button>
              <Button variant="outline" disabled={busy} onClick={() => onEdit?.(repo)}>
                <Pencil className="h-4 w-4" />
                编辑
              </Button>
              <Button variant="destructive" disabled={busy} onClick={() => onDelete?.(repo)}>
                <Trash2 className="h-4 w-4" />
                删除
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
