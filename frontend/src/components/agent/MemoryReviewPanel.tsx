import { useState } from "react";
import { CheckCircle2, Trash2, XCircle } from "lucide-react";
import { useAgentMemories, useApproveAgentMemory, useDeleteAgentMemory, useRejectAgentMemory } from "../../hooks/useAgent";
import { PaginationBar } from "../navigation/PaginationBar";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

const typeLabels: Record<string, string> = {
  user_preference: "用户偏好",
  scan_pattern: "扫描经验",
  review_decision: "复查结论",
  query_context: "查询上下文"
};

export function MemoryReviewPanel({ status }: { status?: string }) {
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const { data, isLoading } = useAgentMemories(status ? { status, page, page_size: pageSize } : { page, page_size: pageSize });
  const memories = data?.items || [];
  const approve = useApproveAgentMemory();
  const reject = useRejectAgentMemory();
  const remove = useDeleteAgentMemory();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{status === "pending_review" ? "待确认记忆" : "智能体记忆"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <div className="text-sm text-muted-foreground">正在读取记忆...</div>}
        {!isLoading && !memories.length && <div className="text-sm text-muted-foreground">暂无记录。</div>}
        {memories.map((memory) => (
          <div key={memory.id} className="rounded-lg border bg-muted/10 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={memory.status === "active" ? "default" : "outline"}>{memory.status}</Badge>
                  <span className="text-xs text-muted-foreground">{typeLabels[memory.memory_type] || memory.memory_type}</span>
                  <span className="text-xs text-muted-foreground">置信度 {memory.confidence}</span>
                </div>
                <div className="mt-2 text-sm leading-6">{memory.content}</div>
              </div>
              <div className="flex shrink-0 gap-1">
                {memory.status === "pending_review" && (
                  <>
                    <Button size="icon-sm" variant="secondary" disabled={approve.isPending} onClick={() => approve.mutate(memory.id)}>
                      <CheckCircle2 className="h-4 w-4" />
                    </Button>
                    <Button size="icon-sm" variant="destructive" disabled={reject.isPending} onClick={() => reject.mutate(memory.id)}>
                      <XCircle className="h-4 w-4" />
                    </Button>
                  </>
                )}
                <Button size="icon-sm" variant="outline" disabled={remove.isPending} onClick={() => remove.mutate(memory.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        ))}
        <PaginationBar page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} isLoading={isLoading} />
      </CardContent>
    </Card>
  );
}
