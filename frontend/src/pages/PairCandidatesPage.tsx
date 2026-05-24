import { useEffect, useMemo, useState } from "react";
import { Check, ExternalLink, Search, X } from "lucide-react";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { usePairCandidateActions, usePairCandidates } from "../hooks/usePairCandidates";
import { assetUrl, truncate } from "../lib/utils";

const statusOptions = [
  { value: "pending_review", label: "待复查" },
  { value: "auto_saved", label: "已自动保存" },
  { value: "accepted", label: "已接受" },
  { value: "rejected", label: "已拒绝" }
];

export function PairCandidatesPage() {
  const [search, setSearch] = useState("");
  const [reviewStatus, setReviewStatus] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 40;
  const filters = useMemo(
    () => ({ page, page_size: pageSize, search, review_status: reviewStatus === "all" ? undefined : reviewStatus }),
    [page, search, reviewStatus]
  );
  const { data, isLoading } = usePairCandidates(filters);
  const actions = usePairCandidateActions();
  const candidates = data?.items || [];
  useEffect(() => {
    setPage(1);
  }, [search, reviewStatus]);

  return (
    <div className="space-y-5">
      <div>
        <div className="text-xs text-muted-foreground">Pair Candidates</div>
        <h1 className="text-2xl font-semibold">候选配对复查</h1>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索仓库、Prompt、证据、来源文件..." />
          </div>
          <Select value={reviewStatus} onValueChange={setReviewStatus}>
            <SelectTrigger className="w-full md:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              {statusOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {isLoading ? (
        <Card>
          <CardContent className="p-10 text-muted-foreground">正在加载候选配对...</CardContent>
        </Card>
      ) : !candidates.length ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">暂无候选配对。运行 GitHub 搜索后，低置信或待确认结果会出现在这里。</CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {candidates.map((candidate) => (
            <Card key={candidate.id} className="overflow-hidden">
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div className="min-w-0">
                  <CardTitle className="truncate text-base">{candidate.repo_name}</CardTitle>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {candidate.source_file || "未知文件"} {candidate.source_heading ? `· ${candidate.source_heading}` : ""}
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap justify-end gap-2">
                  <Badge>{candidate.match_type}</Badge>
                  <Badge variant={candidate.match_score >= 85 ? "default" : "secondary"}>{candidate.match_score} 分</Badge>
                  <Badge variant="outline">{candidate.review_status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-[260px_1fr]">
                <div className="overflow-hidden rounded-lg border bg-muted">
                  {candidate.cloud_storage_url || candidate.image_local_path ? (
                    <img src={assetUrl(candidate.cloud_storage_url || candidate.image_local_path)} alt={candidate.repo_name} className="h-64 w-full object-cover" loading="lazy" />
                  ) : (
                    <div className="grid h-64 place-items-center text-sm text-muted-foreground">无本地图片</div>
                  )}
                </div>
                <div className="space-y-4">
                  <div className="grid grid-cols-5 gap-2 text-center text-xs">
                    <div className="rounded-lg border p-2">
                      <div className="text-muted-foreground">结构</div>
                      <div className="font-semibold">{candidate.structural_score}</div>
                    </div>
                    <div className="rounded-lg border p-2">
                      <div className="text-muted-foreground">距离</div>
                      <div className="font-semibold">{candidate.distance_score}</div>
                    </div>
                    <div className="rounded-lg border p-2">
                      <div className="text-muted-foreground">命名</div>
                      <div className="font-semibold">{candidate.filename_score}</div>
                    </div>
                    <div className="rounded-lg border p-2">
                      <div className="text-muted-foreground">语义</div>
                      <div className="font-semibold">{candidate.semantic_score}</div>
                    </div>
                    <div className="rounded-lg border p-2">
                      <div className="text-muted-foreground">扣分</div>
                      <div className="font-semibold">{candidate.penalty_score}</div>
                    </div>
                  </div>

                  <div>
                    <div className="mb-1 text-xs text-muted-foreground">Prompt</div>
                    <p className="text-sm leading-6">{truncate(candidate.original_prompt, 520)}</p>
                  </div>
                  <div>
                    <div className="mb-1 text-xs text-muted-foreground">匹配证据</div>
                    <p className="text-sm leading-6 text-muted-foreground">{candidate.evidence}</p>
                    {candidate.review_reason && <p className="mt-2 text-xs text-amber-300">{candidate.review_reason}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => actions.accept.mutate({ id: candidate.id })}>
                      <Check className="mr-2 h-4 w-4" />
                      接受匹配
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => actions.update.mutate({ id: candidate.id, review_status: "style_reference", review_reason: "人工改为风格参考" })}>
                      改为风格参考
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => actions.reject.mutate(candidate.id)}>
                      <X className="mr-2 h-4 w-4" />
                      拒绝
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => window.open(candidate.source_page_url || candidate.repo_url, "_blank")}>
                      <ExternalLink className="mr-2 h-4 w-4" />
                      来源
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          <PaginationBar page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} isLoading={isLoading} />
        </div>
      )}
    </div>
  );
}
