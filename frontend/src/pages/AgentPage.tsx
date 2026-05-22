import { AgentChat } from "../components/agent/AgentChat";
import { MemoryReviewPanel } from "../components/agent/MemoryReviewPanel";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

export function AgentPage() {
  const tools = [
    ["Web UI Prompt", "查 web_ui_repo_profiles，返回组件库与设计规范仓库画像"],
    ["图像生成 Prompt", "查 prompt_effect_pairs，按场景、标签、效果评价匹配"],
    ["Skill 仓库", "查 skill_repo_profiles，匹配 AI Skill、MCP、Agent 工具和工作流仓库"],
    ["视频生成 Prompt", "查视频生成类 Prompt、镜头、分镜、缩略图"],
    ["资源仓库", "查 repos，定位值得复扫或待扫描的 GitHub 仓库"],
    ["候选配对", "查 pair_candidates，找需要人工确认的 Prompt-图片匹配"]
  ];
  return (
    <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
      <AgentChat />
      <div className="space-y-5">
        <Card>
          <CardHeader>
            <div className="text-xs text-muted-foreground">Agent Tool Layer</div>
            <CardTitle>工具部分</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
            <p>Chat 负责理解你的描述；工具层负责判断要查哪类资产，并只从本地 SQLite 返回结果。</p>
            <div className="space-y-2">
              {tools.map(([name, desc]) => (
                <div key={name} className="rounded-lg border bg-background/40 p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-foreground/80" />
                    <Badge variant="secondary">{name}</Badge>
                  </div>
                  <div className="text-xs leading-5">{desc}</div>
                </div>
              ))}
            </div>
            <p>返回结果会显示在回答下方的小圆点胶囊中，点击即可预览 Prompt、图片、证据和来源链接。</p>
          </CardContent>
        </Card>
        <MemoryReviewPanel status="pending_review" />
      </div>
    </div>
  );
}
