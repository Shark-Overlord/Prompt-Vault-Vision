import { Copy, ExternalLink, Star } from "lucide-react";
import type { PromptPair, PromptPairPatch } from "../../lib/types";
import { visualAssetTypeLabels, visualAssetTypes } from "../../lib/constants";
import { effectiveCnExplanation } from "../../lib/annotation";
import { assetUrl } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "../ui/sheet";
import { Textarea } from "../ui/textarea";
import { SelectionStatusSwitch } from "./SelectionStatusSwitch";
import { TagSelector } from "./TagSelector";

export function PromptDetailDrawer({
  pair,
  onClose,
  onUpdate,
  favoriteOnly = false
}: {
  pair: PromptPair | null;
  onClose: () => void;
  onUpdate: (payload: PromptPairPatch) => void;
  favoriteOnly?: boolean;
}) {
  const isFavorite = pair?.selection_status === "featured";
  const isDraftAnnotation = pair?.annotation_display_status === "draft";
  const displayCn = pair ? effectiveCnExplanation(pair) : "";
  const displayTags = pair?.tags?.length ? pair.tags : pair?.latest_suggested_tags || [];

  return (
    <Sheet open={Boolean(pair)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-[86vw] overflow-y-auto data-[side=right]:sm:max-w-5xl">
        {pair && (
          <>
            <SheetHeader className="border-b">
              <SheetDescription>Prompt 详情</SheetDescription>
              <SheetTitle>{pair.repo_name || "未命名 Prompt"}</SheetTitle>
            </SheetHeader>
            <div className="grid gap-6 p-6 lg:grid-cols-[1.08fr_0.92fr]">
              <div className="space-y-4">
                <Card>
                  <CardContent className="p-0">
                    {pair.cloud_storage_url || pair.image_local_path ? (
                      <img src={assetUrl(pair.cloud_storage_url || pair.image_local_path)} alt={pair.repo_name} className="max-h-[680px] w-full object-contain" />
                    ) : (
                      <div className="grid h-96 place-items-center text-muted-foreground">暂无效果图</div>
                    )}
                  </CardContent>
                </Card>
                <div className="flex flex-wrap gap-2">
                  <Badge>{pair.category}</Badge>
                  {pair.scenario ? <Badge variant="secondary">{pair.scenario}</Badge> : null}
                  <Badge variant={pair.commercial_risk === "unknown" ? "outline" : "secondary"}>商用风险：{pair.commercial_risk || "unknown"}</Badge>
                  {isFavorite ? <Badge className="border-amber-300/40 bg-amber-300/10 text-amber-200" variant="outline">已收藏</Badge> : null}
                  {isDraftAnnotation ? <Badge variant="outline">草稿待审</Badge> : null}
                </div>
              </div>
              <div className="space-y-5">
                <Card>
                  <CardHeader>
                    <CardTitle>{favoriteOnly ? "收藏" : "筛选结论"}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {favoriteOnly ? (
                      <Button
                        variant={isFavorite ? "secondary" : "outline"}
                        onClick={() => onUpdate({ selection_status: isFavorite ? "normal" : "featured" })}
                      >
                        <Star className={isFavorite ? "h-4 w-4 fill-current text-amber-300" : "h-4 w-4"} />
                        {isFavorite ? "已收藏，点击取消" : "收藏这条 Prompt"}
                      </Button>
                    ) : (
                      <SelectionStatusSwitch value={pair.selection_status} onChange={(value) => onUpdate({ selection_status: value })} />
                    )}
                    <div className="space-y-2">
                      <div className="text-xs text-muted-foreground">视觉用途</div>
                      <Select value={pair.visual_asset_type || "uncategorized"} onValueChange={(value) => onUpdate({ visual_asset_type: value })}>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {visualAssetTypes.map((type) => (
                            <SelectItem key={type} value={type}>
                              {visualAssetTypeLabels[type]}
                            </SelectItem>
                          ))}
                          <SelectItem value="uncategorized">未分类</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>配对证据</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-muted-foreground">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="secondary">{pair.pair_relation_type || "unclear"}</Badge>
                      <Badge variant="outline">置信度：{pair.pair_confidence ?? 0}</Badge>
                    </div>
                    <p>{pair.pair_evidence || "暂无严格配对证据。"}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle>原始 Prompt</CardTitle>
                    <Button size="sm" variant="ghost" onClick={() => navigator.clipboard.writeText(pair.original_prompt || "")}>
                      <Copy className="h-4 w-4" />
                      复制
                    </Button>
                  </CardHeader>
                  <CardContent>
                    <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border bg-muted/40 p-4 font-mono text-xs leading-5">
                      {pair.original_prompt || "暂无"}
                    </pre>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>{isDraftAnnotation ? "中文翻译草稿" : "中文翻译"}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-6 text-muted-foreground">{displayCn || "暂无"}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>效果评价</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Textarea defaultValue={pair.effect_review || ""} onBlur={(event) => onUpdate({ effect_review: event.target.value })} className="min-h-28 resize-y" />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>相关标签</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <TagSelector tags={displayTags} onChange={(tags) => onUpdate({ tags })} />
                  </CardContent>
                </Card>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => window.open(pair.source_page_url || pair.repo_url, "_blank")}>
                    <ExternalLink className="h-4 w-4" />
                    打开来源
                  </Button>
                  {!favoriteOnly ? (
                    <Button variant="outline" onClick={() => onUpdate({ commercial_risk: "unknown", selection_status: "pending_review" })}>
                      标记待复查
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
