import { useEffect, useState } from "react";
import { Blocks, PanelsTopLeft, Ruler, Search, Star } from "lucide-react";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import { WebUiRepoMasonryGrid } from "../components/web-ui/WebUiRepoMasonryGrid";
import { useUpdateWebUiRepoProfile, useWebUiRepoProfiles } from "../hooks/useWebUiRepoProfiles";
import type { WebUiRepoProfile } from "../lib/types";

const profileTypeLabels: Record<string, string> = {
  design_spec: "设计规范",
  component_library: "组件库"
};

export function WebUiPromptLibraryPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [profileType, setProfileType] = useState<"component_library" | "design_spec">("component_library");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const pageSize = 24;
  const updateProfile = useUpdateWebUiRepoProfile();

  const { data, isLoading } = useWebUiRepoProfiles({
    page,
    page_size: pageSize,
    search,
    profile_type: profileType,
    selection_status: favoriteOnly ? "featured" : undefined
  });

  const items = data?.items || [];

  useEffect(() => {
    setPage(1);
  }, [search, profileType, favoriteOnly]);

  const toggleFavorite = (item: WebUiRepoProfile) => {
    updateProfile.mutate({
      id: item.id,
      payload: { selection_status: item.selection_status === "featured" ? "normal" : "featured" }
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="text-xs text-muted-foreground">Frontend Repository Assets</div>
        <h1 className="text-2xl font-semibold">前端资产库</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          这里沉淀前端组件仓库和设计规范仓库。列表按画像得分排序，主要用于快速判断仓库适合什么前端项目、能复用哪些组件或规范。
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 p-4">
          <Tabs value={profileType} onValueChange={(value) => setProfileType(value as "component_library" | "design_spec")}>
            <TabsList>
              <TabsTrigger value="component_library" className="min-w-28 gap-2">
                <Blocks className="h-4 w-4" />
                组件库
              </TabsTrigger>
              <TabsTrigger value="design_spec" className="min-w-28 gap-2">
                <Ruler className="h-4 w-4" />
                设计规范
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="grid gap-3 lg:grid-cols-[minmax(280px,1fr)_auto] lg:items-center">
            <div className="relative min-w-0">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-9"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={profileType === "component_library" ? "搜索仓库名、适用前端、技术栈、组件焦点..." : "搜索仓库名、设计规范、布局规则、技术栈..."}
              />
            </div>
            <label className="flex items-center gap-2 rounded-lg border bg-background/50 px-3 py-2 text-sm">
              <Switch checked={favoriteOnly} onCheckedChange={setFavoriteOnly} />
              <Star className="h-4 w-4 text-muted-foreground" />
              只看收藏
            </label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <PanelsTopLeft className="h-4 w-4" />
              {profileTypeLabels[profileType]}
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">当前结果 {data?.total || 0} 条，按得分从高到低排序</p>
          </div>
        </CardHeader>
        <CardContent>
          <WebUiRepoMasonryGrid items={items} isLoading={isLoading} onToggleFavorite={toggleFavorite} />
        </CardContent>
      </Card>

      <PaginationBar page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} isLoading={isLoading} />
    </div>
  );
}
