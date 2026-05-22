import type { WebUiRepoProfile } from "../../lib/types";
import { Card, CardContent } from "../ui/card";
import { WebUiRepoCard } from "./WebUiRepoCard";

export function WebUiRepoMasonryGrid({
  items,
  isLoading,
  onToggleFavorite
}: {
  items: WebUiRepoProfile[];
  isLoading?: boolean;
  onToggleFavorite: (item: WebUiRepoProfile) => void;
}) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="grid min-h-80 place-items-center p-10 text-center text-muted-foreground">正在加载前端仓库资产...</CardContent>
      </Card>
    );
  }

  if (!items.length) {
    return (
      <Card>
        <CardContent className="grid min-h-80 place-items-center p-10 text-center">
          <div>
            <div className="text-lg font-semibold">当前分类下还没有仓库级资产</div>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
              先在资源库里发现并扫描 Web UI 仓库。扫描后这里会以瀑布流展示组件库或设计规范仓库画像。
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="columns-1 gap-5 md:columns-2 xl:columns-3 2xl:columns-4">
      {items.map((item) => (
        <div key={item.id} className="mb-5 break-inside-avoid">
          <WebUiRepoCard item={item} onToggleFavorite={onToggleFavorite} />
        </div>
      ))}
    </div>
  );
}
