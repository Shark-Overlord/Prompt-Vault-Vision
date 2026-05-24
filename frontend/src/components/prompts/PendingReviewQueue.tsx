import type { PromptPair } from "../../lib/types";
import { assetUrl, truncate } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

export function PendingReviewQueue({ pairs, onOpen, onDecision }: { pairs: PromptPair[]; onOpen: (pair: PromptPair) => void; onDecision: (id: number, status: string) => void }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <div className="text-xs text-muted-foreground">Quality Grading</div>
          <CardTitle>质量分级</CardTitle>
        </div>
        <Badge variant="secondary">{pairs.length}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {pairs.map((pair) => (
          <div key={pair.id} className="rounded-xl border bg-muted/30 p-3">
            <button onClick={() => onOpen(pair)} className="flex w-full gap-3 text-left">
              <div className="h-20 w-24 shrink-0 overflow-hidden rounded-lg bg-muted">
                {(pair.cloud_storage_url || pair.image_local_path) && <img src={assetUrl(pair.cloud_storage_url || pair.image_local_path)} className="h-full w-full object-cover" />}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium">{pair.repo_name || "未命名"}</div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{truncate(pair.effect_review || pair.prompt_cn_explanation, 82)}</p>
              </div>
            </button>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => onDecision(pair.id, "featured")}>
                精选
              </Button>
              <Button size="sm" variant="outline" onClick={() => onDecision(pair.id, "normal")}>
                普通
              </Button>
              <Button size="sm" variant="outline" onClick={() => onDecision(pair.id, "reference")}>
                仅参考
              </Button>
              <Button size="sm" variant="destructive" onClick={() => onDecision(pair.id, "rejected")}>
                拒绝
              </Button>
            </div>
          </div>
        ))}
        {!pairs.length && <div className="py-10 text-center text-sm text-muted-foreground">当前没有待分级项目。</div>}
      </CardContent>
    </Card>
  );
}
