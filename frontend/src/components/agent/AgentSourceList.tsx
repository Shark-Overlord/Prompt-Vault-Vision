import { Database, FileText, GitBranch } from "lucide-react";
import type { AgentSource } from "../../lib/types";
import { Badge } from "../ui/badge";

function iconFor(type: AgentSource["type"]) {
  if (type === "repo") return <GitBranch className="h-3.5 w-3.5" />;
  if (type === "prompt_pair") return <FileText className="h-3.5 w-3.5" />;
  return <Database className="h-3.5 w-3.5" />;
}

export function AgentSourceList({ sources }: { sources: AgentSource[] }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-3 space-y-2">
      <div className="text-xs text-muted-foreground">引用来源</div>
      <div className="flex flex-wrap gap-2">
        {sources.slice(0, 8).map((source) => (
          <Badge key={`${source.type}-${source.id}`} variant="secondary" className="max-w-full">
            {iconFor(source.type)}
            <span className="truncate">{source.title}</span>
          </Badge>
        ))}
      </div>
    </div>
  );
}
