import { useEffect, useState } from "react";
import { Bot, Search, Sparkles, Star, Wrench } from "lucide-react";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { SkillRepoMasonryGrid } from "../components/skills/SkillRepoMasonryGrid";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
import { useSkillRepoProfiles, useUpdateSkillRepoProfile } from "../hooks/useSkillRepoProfiles";
import type { SkillRepoProfile } from "../lib/types";

export function SkillRepoLibraryPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const pageSize = 24;
  const updateProfile = useUpdateSkillRepoProfile();

  const { data, isLoading } = useSkillRepoProfiles({
    page,
    page_size: pageSize,
    search,
    selection_status: favoriteOnly ? "featured" : undefined
  });

  const items = data?.items || [];

  useEffect(() => {
    setPage(1);
  }, [search, favoriteOnly]);

  const toggleFavorite = (item: SkillRepoProfile) => {
    updateProfile.mutate({
      id: item.id,
      payload: { selection_status: item.selection_status === "featured" ? "normal" : "featured" }
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="text-xs text-muted-foreground">AI Skill Repository Assets</div>
        <h1 className="text-2xl font-semibold">Skill 资产库</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          这里按仓库级别沉淀 AI Skill、Agent 工具、MCP 服务和工作流能力包。列表按画像得分排序，搜索可匹配能力、场景、平台、工具名和标签。
        </p>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[minmax(280px,1fr)_auto] lg:items-center">
          <div className="relative min-w-0">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索具体需求，例如微信文章撰写、网页抓取、PDF 总结、代码审查、MCP 服务..."
            />
          </div>
          <label className="flex items-center gap-2 rounded-lg border bg-background/50 px-3 py-2 text-sm">
            <Switch checked={favoriteOnly} onCheckedChange={setFavoriteOnly} />
            <Star className="h-4 w-4 text-muted-foreground" />
            只看收藏
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4" />
              Skill 仓库画像
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">当前结果 {data?.total || 0} 条，按得分从高到低排序</p>
          </div>
          <div className="hidden items-center gap-2 text-xs text-muted-foreground md:flex">
            <Bot className="h-4 w-4" />
            <span>仓库级 AI 标注</span>
            <Wrench className="h-4 w-4" />
            <span>工具能力沉淀</span>
          </div>
        </CardHeader>
        <CardContent>
          <SkillRepoMasonryGrid items={items} isLoading={isLoading} onToggleFavorite={toggleFavorite} />
        </CardContent>
      </Card>

      <PaginationBar page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} isLoading={isLoading} />
    </div>
  );
}
