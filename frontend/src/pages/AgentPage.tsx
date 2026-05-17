import { AgentChat } from "../components/agent/AgentChat";
import { MemoryReviewPanel } from "../components/agent/MemoryReviewPanel";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

export function AgentPage() {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
      <AgentChat />
      <div className="space-y-5">
        <Card>
          <CardHeader>
            <div className="text-xs text-muted-foreground">LangGraph Agent</div>
            <CardTitle>工作边界</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
            <p>智能体可以检索本地 SQLite 中的仓库、Prompt 效果对和候选配对。</p>
            <p>涉及写入的偏好会进入待确认记忆，不会自动污染正式规则。</p>
            <p>仓库扫描不再使用 AI 生成的仓库专属模板；资源库详情只展示当前仓库对应的四类固定检测策略。</p>
          </CardContent>
        </Card>
        <MemoryReviewPanel status="pending_review" />
      </div>
    </div>
  );
}
