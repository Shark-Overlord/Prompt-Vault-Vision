import type { SkillRepoProfile } from "../../lib/types";
import { Card, CardContent } from "../ui/card";
import { SkillRepoCard } from "./SkillRepoCard";

export function SkillRepoMasonryGrid({
  items,
  isLoading,
  onToggleFavorite
}: {
  items: SkillRepoProfile[];
  isLoading?: boolean;
  onToggleFavorite: (item: SkillRepoProfile) => void;
}) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="grid min-h-80 place-items-center p-10 text-center text-muted-foreground">正在加载 Skill 仓库资产...</CardContent>
      </Card>
    );
  }

  if (!items.length) {
    return (
      <Card>
        <CardContent className="grid min-h-80 place-items-center p-10 text-center">
          <div>
            <div className="text-lg font-semibold">还没有 Skill 仓库画像</div>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
              先通过定时任务或资源库发现 Skill 仓库，再在资源库里扫描仓库。扫描后这里会展示仓库级能力标注。
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
          <SkillRepoCard item={item} onToggleFavorite={onToggleFavorite} />
        </div>
      ))}
    </div>
  );
}
