import { Archive, Clock, Database, GalleryVerticalEnd, SearchCheck, Sparkles } from "lucide-react";
import { useDashboard } from "../hooks/useDashboard";
import { categoryLabels } from "../lib/constants";
import { assetUrl, truncate } from "../lib/utils";
import { StatsCard } from "../components/dashboard/StatsCard";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

export function DashboardPage() {
  const { data, isLoading } = useDashboard();
  const counts = data?.counts;
  const totalCategories = Math.max(...(data?.categories.map((item) => item.count) || [1]));

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-6">
          <div className="max-w-3xl">
            <Badge variant="secondary" className="mb-3">
              本地 Prompt 资产管理器
            </Badge>
            <h1 className="text-3xl font-semibold tracking-tight">Prompt + 效果图 + 来源页面 + 评价结论</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">用 SQLite 沉淀 GitHub 视觉 Prompt 资源，前端负责浏览、筛选、质量分级和导出。</p>
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <StatsCard title="GitHub 资源总数" value={counts?.repo_count ?? (isLoading ? "..." : 0)} icon={Database} />
        <StatsCard title="Prompt 效果对" value={counts?.pair_count ?? (isLoading ? "..." : 0)} icon={GalleryVerticalEnd} accent="emerald" />
        <StatsCard title="精选 Prompt" value={counts?.featured_count ?? (isLoading ? "..." : 0)} icon={Sparkles} />
        <StatsCard title="待分级" value={counts?.pending_count ?? (isLoading ? "..." : 0)} icon={Clock} accent="amber" />
        <StatsCard title="今日新增" value={counts?.today_new_count ?? (isLoading ? "..." : 0)} icon={Archive} accent="emerald" />
        <StatsCard title="今日更新" value={counts?.today_updated_count ?? (isLoading ? "..." : 0)} icon={SearchCheck} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <div className="text-xs text-muted-foreground">分类分布</div>
            <CardTitle>资源结构</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {(data?.categories || []).map((item) => (
              <div key={item.category}>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span>{categoryLabels[item.category] || item.category}</span>
                  <span className="text-muted-foreground">{item.count}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${(item.count / totalCategories) * 100}%` }} />
                </div>
              </div>
            ))}
            {!data?.categories.length && <div className="py-12 text-center text-sm text-muted-foreground">暂无分类统计。</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <div className="text-xs text-muted-foreground">最近保存的效果图</div>
              <CardTitle>视觉证据链</CardTitle>
            </div>
            <Badge>image-first</Badge>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {(data?.recent_pairs || []).map((pair) => (
                <div key={pair.id} className="overflow-hidden rounded-xl border bg-muted/30">
                  <div className="aspect-[4/3] bg-muted">
                    {pair.image_local_path && <img src={assetUrl(pair.image_local_path)} className="h-full w-full object-cover" />}
                  </div>
                  <div className="p-3">
                    <div className="text-xs font-medium">{pair.repo_name || "未命名"}</div>
                    <p className="mt-1 text-xs text-muted-foreground">{truncate(pair.original_prompt, 46)}</p>
                  </div>
                </div>
              ))}
            </div>
            {!data?.recent_pairs.length && <div className="grid min-h-56 place-items-center text-center text-sm text-muted-foreground">首次搜索后，这里会显示最近保存的 Prompt 效果图。</div>}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
