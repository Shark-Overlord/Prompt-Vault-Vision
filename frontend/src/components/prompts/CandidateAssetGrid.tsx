import { ExternalLink, ImageOff, Link2 } from "lucide-react";
import { categoryLabels } from "../../lib/constants";
import type { VisualAsset } from "../../lib/types";
import { assetUrl } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

export function CandidateAssetGrid({ assets, isLoading }: { assets: VisualAsset[]; isLoading?: boolean }) {
  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs text-muted-foreground">Candidate Assets</div>
          <CardTitle>已抓到的候选效果图</CardTitle>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            这些图片来自已保存仓库，但还没有通过严格的 Prompt + 效果图同源证据校验，所以暂不进入正式 Prompt 瀑布流。
          </p>
        </div>
        <Badge variant="outline">未配对候选</Badge>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="grid min-h-56 place-items-center text-sm text-muted-foreground">正在读取候选图片...</div>
        ) : assets.length ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {assets.map((asset) => (
              <div key={asset.id} className="overflow-hidden rounded-lg border bg-card/70">
                <div className="aspect-[4/3] bg-muted">
                  {asset.cloud_storage_url || asset.image_local_path ? (
                    <img src={assetUrl(asset.cloud_storage_url || asset.image_local_path)} alt={asset.repo_name || "候选效果图"} className="h-full w-full object-cover" />
                  ) : (
                    <div className="grid h-full place-items-center text-muted-foreground">
                      <ImageOff className="size-8" />
                    </div>
                  )}
                </div>
                <div className="space-y-3 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{asset.repo_name || "未命名仓库"}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {asset.repo_category ? categoryLabels[asset.repo_category] || asset.repo_category : "未分类"} · {asset.width || "?"}x
                        {asset.height || "?"}
                      </div>
                    </div>
                    <Badge variant="secondary">{asset.asset_type || "image"}</Badge>
                  </div>
                  <p className="line-clamp-2 text-xs leading-5 text-muted-foreground">{asset.description || "README 中解析到的图片候选。"}</p>
                  <div className="flex gap-2">
                    {asset.repo_url && (
                      <Button size="sm" variant="outline" asChild>
                        <a href={asset.repo_url} target="_blank" rel="noreferrer">
                          <Link2 className="size-3.5" />
                          仓库
                        </a>
                      </Button>
                    )}
                    {asset.image_original_url && (
                      <Button size="sm" variant="ghost" asChild>
                        <a href={asset.image_original_url} target="_blank" rel="noreferrer">
                          <ExternalLink className="size-3.5" />
                          原图
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid min-h-56 place-items-center text-center text-sm text-muted-foreground">还没有图片资产。请先执行 GitHub 增量搜索。</div>
        )}
      </CardContent>
    </Card>
  );
}
