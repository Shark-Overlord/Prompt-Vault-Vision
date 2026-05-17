import { CheckCircle2 } from "lucide-react";
import { useApproveAgentMemory } from "../../hooks/useAgent";
import type { AgentAction } from "../../lib/types";
import { Button } from "../ui/button";

export function AgentActionConfirm({ actions }: { actions: AgentAction[] }) {
  const approveMemory = useApproveAgentMemory();
  if (!actions?.length) return null;
  return (
    <div className="mt-3 space-y-2">
      <div className="text-xs text-muted-foreground">待确认动作</div>
      {actions.map((action, index) => (
        <div key={`${action.type}-${action.memory_id || index}`} className="flex items-center justify-between gap-3 rounded-lg border bg-muted/20 p-2">
          <div className="text-sm">{action.label || action.type}</div>
          {action.type === "review_memory" && action.memory_id && (
            <Button size="sm" variant="secondary" disabled={approveMemory.isPending} onClick={() => approveMemory.mutate(action.memory_id as number)}>
              <CheckCircle2 className="h-4 w-4" />
              批准记忆
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
