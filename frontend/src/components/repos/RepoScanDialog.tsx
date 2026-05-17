import { FormEvent, useState } from "react";
import { Bot, RefreshCw } from "lucide-react";
import { useAiConfigs } from "../../hooks/useAiConfigs";
import type { Repo, RepoScanPayload } from "../../lib/types";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "../ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Switch } from "../ui/switch";

export function RepoScanDialog({
  repo,
  open,
  onOpenChange,
  onScan,
  busy
}: {
  repo: Repo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onScan: (repo: Repo, payload: RepoScanPayload) => void;
  busy?: boolean;
}) {
  const { data: aiConfigs = [] } = useAiConfigs();
  const [useAi, setUseAi] = useState(false);
  const [aiConfigId, setAiConfigId] = useState("default");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!repo) return;
    onScan(repo, {
      use_ai: useAi,
      generate_template: false,
      scan_mode: "generic",
      template_id: null,
      ai_config_id: aiConfigId !== "default" ? Number(aiConfigId) : null
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>扫描仓库</DialogTitle>
            <DialogDescription>
              默认由规则扫描 Markdown：先按标题、Case、表格、分隔符切块，再在块内匹配 Prompt 和图片。启用 Qwen 8B 时，只辅助判断低置信复杂块，不直接替代规则或人工审核。
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-lg border bg-muted/20 p-3 text-sm text-muted-foreground">
            {repo ? `${repo.owner}/${repo.repo_name}` : "未选择仓库"}
          </div>

          <div className="flex items-center justify-between rounded-lg border bg-muted/10 p-3">
            <div>
              <div className="text-sm font-medium">Qwen 8B 辅助判断低置信块</div>
              <div className="mt-1 text-xs text-muted-foreground">规则负责稳定提取；Qwen 只接收低置信候选 JSON，输出辅助 evidence，结果仍进入人工复查。</div>
            </div>
            <Switch
              checked={useAi}
              onCheckedChange={setUseAi}
            />
          </div>

          {useAi && (
            <label className="space-y-2">
              <span className="text-xs text-muted-foreground">AI 配置</span>
              <Select value={aiConfigId} onValueChange={setAiConfigId}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">使用默认 AI 配置</SelectItem>
                  {aiConfigs.map((config) => (
                    <SelectItem key={config.id} value={String(config.id)}>
                      {config.name} · {config.model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={!repo || busy}>
              {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
              开始扫描
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
