import { AnimatePresence, motion, type PanInfo } from "framer-motion";
import { Bookmark, Check, Eye, Star, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { PromptPair } from "../../lib/types";
import { assetUrl, truncate } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

const decisions = [
  { value: "rejected", label: "拒绝", hint: "左滑", icon: X, variant: "destructive" as const },
  { value: "reference", label: "仅参考", hint: "保留参考", icon: Bookmark, variant: "outline" as const },
  { value: "normal", label: "普通", hint: "可复用", icon: Check, variant: "outline" as const },
  { value: "featured", label: "精选", hint: "右滑", icon: Star, variant: "default" as const }
];

export function QualitySwipeDeck({
  pairs,
  total,
  page,
  pageSize,
  isUpdating,
  onOpen,
  onDecision,
  onPageChange
}: {
  pairs: PromptPair[];
  total: number;
  page: number;
  pageSize: number;
  isUpdating?: boolean;
  onOpen: (pair: PromptPair) => void;
  onDecision: (id: number, status: string) => void;
  onPageChange: (page: number) => void;
}) {
  const pairIds = useMemo(() => pairs.map((pair) => pair.id).join(","), [pairs]);
  const [index, setIndex] = useState(0);
  const current = pairs[index];
  const remainingOnPage = Math.max(pairs.length - index, 0);
  const completedBeforePage = Math.max((page - 1) * pageSize, 0);
  const gradedCount = Math.min(completedBeforePage + index, total);

  useEffect(() => {
    setIndex(0);
  }, [pairIds]);

  const nextCard = () => {
    setIndex((value) => {
      const next = value + 1;
      if (next >= pairs.length && page * pageSize < total) {
        onPageChange(page + 1);
      }
      return next;
    });
  };

  const decide = (status: string) => {
    if (!current || isUpdating) return;
    onDecision(current.id, status);
    nextCard();
  };

  const skip = () => {
    if (!current) return;
    nextCard();
  };

  const onDragEnd = (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.x > 140) decide("featured");
    if (info.offset.x < -140) decide("rejected");
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between border-b">
        <div>
          <div className="text-xs text-muted-foreground">Swipe Grading</div>
          <CardTitle>质量分级</CardTitle>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          <div>当前页剩余 {remainingOnPage}</div>
          <div>整体进度 {gradedCount}/{total}</div>
        </div>
      </CardHeader>
      <CardContent className="p-5">
        {current ? (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
            <div className="relative mx-auto flex min-h-[560px] w-full max-w-3xl items-center justify-center">
              {pairs.slice(index + 1, index + 3).map((pair, stackIndex) => (
                <div
                  key={pair.id}
                  className="absolute inset-x-8 top-8 h-[500px] rounded-xl border bg-card/80"
                  style={{
                    transform: `translateY(${(stackIndex + 1) * 12}px) scale(${1 - (stackIndex + 1) * 0.035})`,
                    opacity: 0.55 - stackIndex * 0.18
                  }}
                />
              ))}
              <AnimatePresence mode="popLayout">
                <motion.article
                  key={current.id}
                  drag="x"
                  dragElastic={0.18}
                  dragConstraints={{ left: 0, right: 0 }}
                  onDragEnd={onDragEnd}
                  initial={{ opacity: 0, y: 24, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -18, scale: 0.95 }}
                  whileDrag={{ rotate: 0, scale: 1.015 }}
                  className="relative z-10 w-full max-w-3xl overflow-hidden rounded-xl border bg-card shadow-2xl"
                >
                  <div className="grid h-[360px] place-items-center bg-black/30">
                    {current.image_local_path ? (
                      <img src={assetUrl(current.image_local_path)} alt={current.repo_name || "prompt"} className="max-h-[340px] w-full object-contain" />
                    ) : (
                      <div className="text-sm text-muted-foreground">暂无效果图</div>
                    )}
                  </div>
                  <div className="space-y-4 p-5">
                    <div className="flex flex-wrap gap-2">
                      <Badge>{current.category}</Badge>
                      <Badge variant="secondary">{current.scenario || "other"}</Badge>
                      {(current.tags || []).slice(0, 5).map((tag) => (
                        <Badge key={tag.id ?? tag.name} variant="outline">{tag.name}</Badge>
                      ))}
                    </div>
                    <div>
                      <div className="text-sm font-medium">中文 Prompt</div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{truncate(current.prompt_cn_explanation || "暂无中文翻译", 300)}</p>
                    </div>
                  </div>
                </motion.article>
              </AnimatePresence>
            </div>

            <aside className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">操作</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    {decisions.map((item) => {
                      const Icon = item.icon;
                      return (
                        <Button key={item.value} variant={item.variant} className="h-14 flex-col gap-1" onClick={() => decide(item.value)} disabled={isUpdating}>
                          <span className="flex items-center gap-2">
                            <Icon className="h-4 w-4" />
                            {item.label}
                          </span>
                          <span className="text-[11px] opacity-70">{item.hint}</span>
                        </Button>
                      );
                    })}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="secondary" onClick={skip}>
                      跳过
                    </Button>
                    <Button variant="outline" onClick={() => onOpen(current)}>
                      <Eye className="h-4 w-4" />
                      详情
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">分级规则</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>右滑或点精选：适合进入精选库、商品库或 Skill 示例。</p>
                  <p>左滑或点拒绝：效果差、风险高、证据不足或不建议复用。</p>
                  <p>普通和仅参考用按钮选择；跳过会保留待分级状态。</p>
                </CardContent>
              </Card>
            </aside>
          </div>
        ) : (
          <div className="grid min-h-[480px] place-items-center text-center">
            <div>
              <div className="text-lg font-medium">当前没有待分级项目</div>
              <p className="mt-2 text-sm text-muted-foreground">所有 pending_review 项已处理，或当前页已经抽完。</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
