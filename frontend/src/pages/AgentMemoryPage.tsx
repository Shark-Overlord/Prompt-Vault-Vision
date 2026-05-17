import { MemoryReviewPanel } from "../components/agent/MemoryReviewPanel";

export function AgentMemoryPage() {
  return (
    <div className="space-y-5">
      <div>
        <div className="text-xs text-muted-foreground">Agent Memory</div>
        <h1 className="text-2xl font-semibold">记忆管理</h1>
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <MemoryReviewPanel status="pending_review" />
        <MemoryReviewPanel status="active" />
      </div>
    </div>
  );
}
