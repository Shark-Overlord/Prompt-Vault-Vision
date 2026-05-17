import type { PromptPair } from "../../lib/types";
import { Card, CardContent } from "../ui/card";
import { PromptCard } from "./PromptCard";

export function PromptMasonryGrid({ pairs, onOpen, onQuickStatus }: { pairs: PromptPair[]; onOpen: (pair: PromptPair) => void; onQuickStatus: (id: number, status: string) => void }) {
  if (!pairs.length) {
    return (
      <Card>
        <CardContent className="grid min-h-80 place-items-center p-10 text-center">
          <div>
            <div className="text-lg font-semibold">正式 Prompt 效果对为 0</div>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
              当前没有通过严格证据链校验的 Prompt + 效果图。下方会展示“候选效果图”，它们已保存到本地图片资产，但还不能当作可复用 Prompt 案例。
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }
  return (
    <div className="columns-1 gap-5 md:columns-2 xl:columns-3 2xl:columns-4">
      {pairs.map((pair) => (
        <div key={pair.id} className="mb-5 break-inside-avoid">
          <PromptCard pair={pair} onOpen={onOpen} onQuickStatus={onQuickStatus} />
        </div>
      ))}
    </div>
  );
}
