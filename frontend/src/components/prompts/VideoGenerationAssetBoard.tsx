import { useEffect, useState } from "react";
import { Copy, ExternalLink, Film, ImageOff, Languages, Search, Star, Tags, X } from "lucide-react";
import type { PromptPair, PromptPairPatch } from "../../lib/types";
import { assetUrl, cn, truncate } from "../../lib/utils";
import { usePromptPairs, useUpdatePromptPair } from "../../hooks/usePromptPairs";
import { PaginationBar } from "../navigation/PaginationBar";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent } from "../ui/card";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";
import { PromptDetailDrawer } from "./PromptDetailDrawer";

function isAnnotated(pair: PromptPair) {
  return (
    pair.annotation_display_status === "formal" ||
    pair.annotation_display_status === "draft" ||
    (Boolean(pair.prompt_cn_explanation?.trim()) && Boolean((pair.tag_count || pair.tags?.length || 0) > 0))
  );
}

function displayTranslation(pair: PromptPair) {
  return pair.prompt_cn_explanation?.trim() || pair.latest_suggested_cn_explanation?.trim() || pair.original_prompt;
}

function displayTags(pair: PromptPair) {
  return pair.tags?.length ? pair.tags : pair.latest_suggested_tags || [];
}

function VideoAssetCard({
  pair,
  onOpen,
  onToggleFavorite
}: {
  pair: PromptPair;
  onOpen: (pair: PromptPair) => void;
  onToggleFavorite: (pair: PromptPair) => void;
}) {
  const image = assetUrl(pair.image_local_path);
  const annotated = isAnnotated(pair);
  const draft = pair.annotation_display_status === "draft";
  const favorite = pair.selection_status === "featured";
  const tags = displayTags(pair);

  return (
    <article className="mb-4 break-inside-avoid overflow-hidden rounded-lg border bg-card/80 shadow-sm transition hover:-translate-y-0.5 hover:border-foreground/20">
      <div className="relative bg-muted">
        <Button
          type="button"
          size="icon-sm"
          variant={favorite ? "secondary" : "ghost"}
          className={cn("absolute right-2 top-2 z-10 bg-background/80 backdrop-blur", favorite && "text-amber-300")}
          onClick={() => onToggleFavorite(pair)}
          title={favorite ? "取消收藏" : "收藏"}
        >
          <Star className={cn("h-4 w-4", favorite && "fill-current")} />
        </Button>
        <button type="button" className="block w-full text-left" onClick={() => onOpen(pair)}>
          {image ? (
            <img src={image} alt={pair.repo_name} className="max-h-[460px] min-h-44 w-full object-cover" loading="lazy" />
          ) : (
            <div className="grid h-64 place-items-center text-muted-foreground">
              <ImageOff className="h-10 w-10" />
            </div>
          )}
        </button>
      </div>

      <div className="space-y-3 p-3">
        <button type="button" className="block w-full text-left" onClick={() => onOpen(pair)}>
          <div className="line-clamp-1 text-xs font-medium">{pair.repo_name || "未命名视频 Prompt"}</div>
          <p className="mt-1 line-clamp-3 text-xs leading-5 text-muted-foreground">{truncate(displayTranslation(pair), 128)}</p>
        </button>

        <div className="flex flex-wrap gap-1.5">
          <Badge className="border-indigo-300/35 bg-indigo-300/10 text-indigo-100" variant="outline">
            {pair.scenario || "video_prompt"}
          </Badge>
          <Badge variant={annotated ? "secondary" : "outline"}>{draft ? "草稿待审" : annotated ? "已入库标注" : "待标注"}</Badge>
          {favorite ? <Badge className="border-amber-300/40 bg-amber-300/10 text-amber-200" variant="outline">已收藏</Badge> : null}
        </div>

        {tags.length ? (
          <div className="flex flex-wrap gap-1.5">
            {tags.slice(0, 5).map((tag) => (
              <Badge key={tag.id || tag.name} variant="outline" className="text-[11px] text-muted-foreground">
                {tag.name}
              </Badge>
            ))}
          </div>
        ) : null}

        <div className="flex items-center justify-between border-t pt-2">
          <div className="line-clamp-1 text-[11px] text-muted-foreground">{pair.source_page_url || pair.repo_url}</div>
          <div className="flex shrink-0 gap-1">
            <Button size="icon-sm" variant="ghost" onClick={() => navigator.clipboard.writeText(pair.original_prompt || "")} title="复制 Prompt">
              <Copy className="h-3.5 w-3.5" />
            </Button>
            <Button size="icon-sm" variant="ghost" onClick={() => window.open(pair.source_page_url || pair.repo_url, "_blank")} title="打开来源">
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </article>
  );
}

export function VideoGenerationAssetBoard({
  title = "视频生成 Prompt 资产库",
  eyebrow = "Video Generation Asset Library",
  description = "整理视频生成 Prompt 与对应缩略图或输出证据。默认显示已正式标注或已有 AI 草稿的视频资产，可继续按标签和收藏筛选。"
}: {
  title?: string;
  eyebrow?: string;
  description?: string;
}) {
  const [selectedPair, setSelectedPair] = useState<PromptPair | null>(null);
  const [search, setSearch] = useState("");
  const [tagSearch, setTagSearch] = useState("");
  const [annotatedOnly, setAnnotatedOnly] = useState(true);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 60;
  const updatePair = useUpdatePromptPair();
  const { data, isLoading } = usePromptPairs({
    page,
    page_size: pageSize,
    search,
    tag_search: tagSearch,
    category: "video_generation_prompt",
    annotated: annotatedOnly ? true : undefined,
    favorite_only: favoriteOnly ? true : undefined,
    has_image: true
  });
  const items = data?.items || [];
  const total = data?.total || 0;

  useEffect(() => {
    setPage(1);
  }, [search, tagSearch, annotatedOnly, favoriteOnly]);

  const updateDetail = (payload: PromptPairPatch) => {
    if (!selectedPair) return;
    updatePair.mutate({ id: selectedPair.id, payload });
    setSelectedPair({ ...selectedPair, ...payload } as PromptPair);
  };

  const toggleFavorite = (pair: PromptPair) => {
    updatePair.mutate({ id: pair.id, payload: { selection_status: pair.selection_status === "featured" ? "normal" : "featured" } });
  };

  const resetFilters = () => {
    setSearch("");
    setTagSearch("");
    setAnnotatedOnly(true);
    setFavoriteOnly(false);
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="text-xs text-muted-foreground">{eyebrow}</div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">{description}</p>
      </div>

      <Card className="border-foreground/10 bg-card/70">
        <CardContent className="space-y-4 p-4">
          <div className="grid gap-3 xl:grid-cols-[minmax(280px,1fr)_260px_auto_auto_auto] xl:items-center">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索仓库、Prompt、中文翻译、效果评价..." className="pl-9" />
            </div>
            <div className="relative">
              <Tags className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={tagSearch} onChange={(event) => setTagSearch(event.target.value)} placeholder="搜索标签，例如运镜、产品视频、短片" className="pl-9" />
            </div>
            <label className="flex items-center gap-2 rounded-lg border bg-background/50 px-3 py-2 text-sm">
              <Switch checked={annotatedOnly} onCheckedChange={setAnnotatedOnly} />
              <Languages className="h-4 w-4 text-muted-foreground" />
              已标注/含草稿
            </label>
            <label className="flex items-center gap-2 rounded-lg border bg-background/50 px-3 py-2 text-sm">
              <Switch checked={favoriteOnly} onCheckedChange={setFavoriteOnly} />
              <Star className="h-4 w-4 text-muted-foreground" />
              只看收藏
            </label>
            <Button variant="ghost" onClick={resetFilters}>
              <X className="h-4 w-4" />
              重置
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t pt-4">
            <Badge className="border-indigo-300/35 bg-indigo-300/10 text-indigo-100" variant="outline">
              <Film className="mr-1 h-3.5 w-3.5" />
              视频 Prompt 瀑布流
            </Badge>
            <Badge variant="secondary">当前结果 {total} 条</Badge>
            <p className="text-xs leading-5 text-muted-foreground">适合沉淀运镜、镜头语言、产品视频、短视频、分镜和广告视频 Prompt。</p>
          </div>
        </CardContent>
      </Card>

      <Card className="border-foreground/10 bg-card/50">
        <CardContent className="p-4">
          {isLoading ? (
            <div className="grid h-72 place-items-center text-sm text-muted-foreground">加载中...</div>
          ) : items.length ? (
            <div className="columns-1 gap-4 sm:columns-2 lg:columns-3 2xl:columns-4">
              {items.map((pair) => (
                <VideoAssetCard key={pair.id} pair={pair} onOpen={setSelectedPair} onToggleFavorite={toggleFavorite} />
              ))}
            </div>
          ) : (
            <div className="grid h-72 place-items-center rounded-lg border border-dashed text-center text-sm leading-6 text-muted-foreground">
              当前条件下没有视频资产。可以关闭“已标注/含草稿”，或换一个标签搜索。
            </div>
          )}
        </CardContent>
      </Card>

      <PaginationBar page={page} pageSize={pageSize} total={total} onPageChange={setPage} isLoading={isLoading} />
      <PromptDetailDrawer pair={selectedPair} onClose={() => setSelectedPair(null)} onUpdate={updateDetail} favoriteOnly />
    </div>
  );
}
