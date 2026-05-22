import { useMemo, useState } from "react";
import { Copy, ExternalLink, ImageOff, Languages, Search, Star, Tags, X } from "lucide-react";
import type { PromptPair, PromptPairPatch } from "../../lib/types";
import { assetUrl, cn, truncate } from "../../lib/utils";
import { visualAssetTypeLabels, visualAssetTypes } from "../../lib/constants";
import { usePromptPairs, useUpdatePromptPair } from "../../hooks/usePromptPairs";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent } from "../ui/card";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";
import { PromptDetailDrawer } from "./PromptDetailDrawer";

type VisualAssetType = (typeof visualAssetTypes)[number];

const assetTypeMeta: Record<VisualAssetType, { hint: string; accent: string }> = {
  creative_image: { hint: "概念、超现实、创意广告、艺术化表达", accent: "border-cyan-400/35 bg-cyan-400/10 text-cyan-100" },
  product_image: { hint: "商品主图、产品摄影、商业广告、包装视觉", accent: "border-amber-400/35 bg-amber-400/10 text-amber-100" },
  scene_image: { hint: "空间、环境、城市、室内外氛围和镜头场景", accent: "border-emerald-400/35 bg-emerald-400/10 text-emerald-100" },
  character_image: { hint: "人物、角色设定、头像、肖像和形象稿", accent: "border-rose-400/35 bg-rose-400/10 text-rose-100" },
  cover_image: { hint: "封面、海报、缩略图、主视觉和宣传图", accent: "border-blue-400/35 bg-blue-400/10 text-blue-100" }
};

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

function ImageAssetCard({
  pair,
  activeType,
  onOpen,
  onToggleFavorite
}: {
  pair: PromptPair;
  activeType: VisualAssetType;
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
            <img src={image} alt={pair.repo_name} className="max-h-[520px] min-h-44 w-full object-cover" loading="lazy" />
          ) : (
            <div className="grid h-64 place-items-center text-muted-foreground">
              <ImageOff className="h-10 w-10" />
            </div>
          )}
        </button>
      </div>

      <div className="space-y-3 p-3">
        <button type="button" className="block w-full text-left" onClick={() => onOpen(pair)}>
          <div className="line-clamp-1 text-xs font-medium">{pair.repo_name || "未命名 Prompt"}</div>
          <p className="mt-1 line-clamp-3 text-xs leading-5 text-muted-foreground">{truncate(displayTranslation(pair), 128)}</p>
        </button>

        <div className="flex flex-wrap gap-1.5">
          <Badge className={cn("border", assetTypeMeta[activeType].accent)} variant="outline">
            {visualAssetTypeLabels[pair.visual_asset_type || activeType] || visualAssetTypeLabels[activeType]}
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
          <div className="line-clamp-1 text-[11px] text-muted-foreground">{pair.visual_asset_type_reason || pair.source_page_url || pair.repo_url}</div>
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

export function ImageGenerationAssetBoard({
  title = "图像生成 Prompt 资产库",
  eyebrow = "Image Generation Asset Library",
  description = "按创意图、商品图、场景图、角色图、封面图整理图像生成 Prompt。默认显示已正式标注或已有 AI 草稿的图片资产，可继续按标签和收藏筛选。"
}: {
  title?: string;
  eyebrow?: string;
  description?: string;
}) {
  const [activeType, setActiveType] = useState<VisualAssetType>("product_image");
  const [selectedPair, setSelectedPair] = useState<PromptPair | null>(null);
  const [search, setSearch] = useState("");
  const [tagSearch, setTagSearch] = useState("");
  const [annotatedOnly, setAnnotatedOnly] = useState(true);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const updatePair = useUpdatePromptPair();
  const commonFilters = {
    page: 1,
    page_size: 60,
    search,
    tag_search: tagSearch,
    category: "image_generation_prompt",
    annotated: annotatedOnly ? true : undefined,
    favorite_only: favoriteOnly ? true : undefined,
    has_image: true
  };
  const creative = usePromptPairs({ ...commonFilters, visual_asset_type: "creative_image" });
  const product = usePromptPairs({ ...commonFilters, visual_asset_type: "product_image" });
  const scene = usePromptPairs({ ...commonFilters, visual_asset_type: "scene_image" });
  const character = usePromptPairs({ ...commonFilters, visual_asset_type: "character_image" });
  const cover = usePromptPairs({ ...commonFilters, visual_asset_type: "cover_image" });
  const queryByType = useMemo(
    () => ({
      creative_image: creative,
      product_image: product,
      scene_image: scene,
      character_image: character,
      cover_image: cover
    }),
    [creative, product, scene, character, cover]
  );
  const activeQuery = queryByType[activeType];
  const activeItems = activeQuery.data?.items || [];

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
              <Input value={tagSearch} onChange={(event) => setTagSearch(event.target.value)} placeholder="搜索标签，例如商品、角色、海报" className="pl-9" />
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

          <div className="flex flex-wrap gap-2 border-t pt-4">
            {visualAssetTypes.map((type) => {
              const isActive = activeType === type;
              return (
                <Button
                  key={type}
                  variant={isActive ? "secondary" : "outline"}
                  className={cn("h-auto min-w-36 justify-between gap-4 px-3 py-2", isActive && "border-foreground/20 bg-foreground text-background hover:bg-foreground/90")}
                  onClick={() => setActiveType(type)}
                >
                  <span className="text-sm font-medium">{visualAssetTypeLabels[type]}</span>
                  <Badge variant={isActive ? "secondary" : "outline"}>{queryByType[type].data?.total || 0}</Badge>
                </Button>
              );
            })}
          </div>
          <p className="text-xs leading-5 text-muted-foreground">{assetTypeMeta[activeType].hint}</p>
        </CardContent>
      </Card>

      <Card className="border-foreground/10 bg-card/50">
        <CardContent className="p-4">
          {activeQuery.isLoading ? (
            <div className="grid h-72 place-items-center text-sm text-muted-foreground">加载中...</div>
          ) : activeItems.length ? (
            <div className="columns-1 gap-4 sm:columns-2 lg:columns-3 2xl:columns-4">
              {activeItems.map((pair) => (
                <ImageAssetCard key={pair.id} pair={pair} activeType={activeType} onOpen={setSelectedPair} onToggleFavorite={toggleFavorite} />
              ))}
            </div>
          ) : (
            <div className="grid h-72 place-items-center rounded-lg border border-dashed text-center text-sm leading-6 text-muted-foreground">
              当前条件下没有图片。可以关闭“已标注/含草稿”，或换一个标签搜索。
            </div>
          )}
        </CardContent>
      </Card>

      <PromptDetailDrawer pair={selectedPair} onClose={() => setSelectedPair(null)} onUpdate={updateDetail} favoriteOnly />
    </div>
  );
}
