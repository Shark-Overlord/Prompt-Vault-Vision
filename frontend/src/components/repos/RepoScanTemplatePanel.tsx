import { FileJson } from "lucide-react";
import { repoDetectionStrategyLabels } from "../../lib/constants";
import type { Repo } from "../../lib/types";
import { Badge } from "../ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

export function RepoScanTemplatePanel({ repo }: { repo: Repo }) {
  const detectionStrategy = repoDetectionStrategyLabels[repo.category] || "未知 Prompt 检测策略";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileJson className="h-4 w-4" />
          仓库检测策略
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-lg border bg-muted/20 p-3">
          <div className="text-xs text-muted-foreground">当前仓库采用的检测策略</div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{detectionStrategy}</Badge>
          </div>
        </div>
        <div className="rounded-lg border bg-muted/10 p-3 text-sm leading-6 text-muted-foreground">
          旧版 AI 生成的仓库专属扫描模板已移除。当前扫描只按仓库分类选择四类固定策略；Qwen 8B 只用于低置信复杂块的辅助判断，不再生成或套用仓库专属扫描模板。
        </div>
      </CardContent>
    </Card>
  );
}
