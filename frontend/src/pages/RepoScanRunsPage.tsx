import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RefreshCw, Search, Trash2, XCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { Checkbox } from "../components/ui/checkbox";
import { useBatchDeleteRepoScanRuns, useCancelRepoScanRun } from "../hooks/useRepos";
import { api } from "../lib/api";
import { categoryLabels } from "../lib/constants";
import type { RepoScanRun } from "../lib/types";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";

const activeStatuses = new Set(["queued", "running", "cancel_requested"]);
const successStatuses = new Set(["succeeded", "success", "ok"]);

const statusOptions = [
  ["all", "全部状态"],
  ["queued", "排队中"],
  ["running", "扫描中"],
  ["cancel_requested", "取消中"],
  ["succeeded", "已完成"],
  ["failed", "失败"],
  ["canceled", "已取消"]
];

function statusLabel(status?: string | null) {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "扫描中",
    cancel_requested: "取消中",
    canceled: "已取消",
    succeeded: "已完成",
    success: "已完成",
    ok: "已完成",
    failed: "失败"
  };
  return labels[status || ""] || status || "未知";
}

function StatusBadge({ status }: { status?: string | null }) {
  if (status && activeStatuses.has(status)) {
    return <Badge variant="secondary">{statusLabel(status)}</Badge>;
  }
  if (status && successStatuses.has(status)) {
    return <Badge>{statusLabel(status)}</Badge>;
  }
  if (status === "failed") {
    return <Badge variant="destructive">失败</Badge>;
  }
  return <Badge variant="outline">{statusLabel(status)}</Badge>;
}

function splitIsoDateTime(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    const pad = (part: number) => String(part).padStart(2, "0");
    return {
      date: `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`,
      time: `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`
    };
  }
  const cleaned = value.replace(/([+-]\d{2}:\d{2}|Z)$/i, "");
  const [date, rawTime = ""] = cleaned.split("T");
  if (!date) return null;
  return { date, time: rawTime.slice(0, 8) };
}

function DateStack({ value }: { value?: string | null }) {
  const parts = splitIsoDateTime(value);
  if (!parts) return <span className="text-xs text-muted-foreground">-</span>;
  return (
    <span className="inline-flex flex-col text-xs leading-5 text-muted-foreground">
      <span>{parts.date}</span>
      <span>{parts.time || "-"}</span>
    </span>
  );
}

function ProgressBar({ value }: { value?: number | null }) {
  const percent = Math.max(0, Math.min(Number(value || 0), 100));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${percent}%` }} />
    </div>
  );
}

function parseError(error: unknown) {
  if (!(error instanceof Error)) return "";
  try {
    return (JSON.parse(error.message) as { detail?: string }).detail || error.message;
  } catch {
    return error.message;
  }
}

export function RepoScanRunsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedRunIds, setSelectedRunIds] = useState<number[]>([]);
  const pageSize = 80;
  const cancelRun = useCancelRepoScanRun();
  const batchDeleteRuns = useBatchDeleteRepoScanRuns();
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["repo-scan-runs", { page, search, status }],
    queryFn: () => api.repoScanRunsList({ page, page_size: pageSize, search, status: status === "all" ? undefined : status }),
    refetchInterval: 2000
  });

  const runs = data?.items || [];
  const deletableRuns = runs.filter((run) => !activeStatuses.has(run.status));
  const deletableIds = deletableRuns.map((run) => run.id);
  const selectedOnPageCount = selectedRunIds.filter((id) => deletableIds.includes(id)).length;
  const allDeletableSelected = deletableIds.length > 0 && selectedOnPageCount === deletableIds.length;
  const stats = useMemo(() => {
    return {
      total: data?.total || 0,
      active: runs.filter((run) => activeStatuses.has(run.status)).length,
      failed: runs.filter((run) => run.status === "failed").length,
      succeeded: runs.filter((run) => successStatuses.has(run.status)).length
    };
  }, [data?.total, runs]);

  const requestCancel = (run: RepoScanRun) => {
    cancelRun.mutate(run.id, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["repo-scan-runs"] });
      }
    });
  };
  useEffect(() => {
    setPage(1);
  }, [search, status]);

  useEffect(() => {
    const visibleIds = new Set(runs.map((run) => run.id));
    setSelectedRunIds((prev) => {
      const next = prev.filter((id) => visibleIds.has(id));
      return next.length === prev.length ? prev : next;
    });
  }, [runs]);

  const toggleRun = (run: RepoScanRun, checked: boolean) => {
    if (activeStatuses.has(run.status)) return;
    setSelectedRunIds((prev) => (checked ? Array.from(new Set([...prev, run.id])) : prev.filter((id) => id !== run.id)));
  };

  const toggleAllVisible = (checked: boolean) => {
    const currentPageIds = new Set(deletableIds);
    setSelectedRunIds((prev) => {
      if (!checked) return prev.filter((id) => !currentPageIds.has(id));
      return Array.from(new Set([...prev, ...deletableIds]));
    });
  };

  const handleBatchDelete = () => {
    if (!selectedRunIds.length) return;
    const ok = window.confirm(`删除选中的 ${selectedRunIds.length} 条扫描任务记录？运行中、排队中或取消中的任务会被后端跳过。`);
    if (!ok) return;
    batchDeleteRuns.mutate(selectedRunIds, {
      onSuccess: (result) => {
        setSelectedRunIds([]);
        queryClient.invalidateQueries({ queryKey: ["repo-scan-runs"] });
        if (result.skipped_count || result.missing_ids.length) {
          window.alert(`已删除 ${result.deleted_count} 条，跳过 ${result.skipped_count} 条，未找到 ${result.missing_ids.length} 条。`);
        }
      }
    });
  };

  return (
    <div>
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs text-muted-foreground">Repository Scan Runs</div>
          <h1 className="text-2xl font-semibold">扫描任务</h1>
        </div>
        <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ["repo-scan-runs"] })}>
          <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
          刷新
        </Button>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">任务总数</div>
            <div className="mt-2 text-2xl font-semibold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">运行 / 排队</div>
            <div className="mt-2 text-2xl font-semibold">{stats.active}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">已完成</div>
            <div className="mt-2 text-2xl font-semibold">{stats.succeeded}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">失败</div>
            <div className="mt-2 text-2xl font-semibold">{stats.failed}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="mb-4">
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索仓库名、Owner、当前文件、摘要、错误信息..."
              className="h-10 pl-9"
            />
          </div>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="h-10 w-full md:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="destructive" disabled={!selectedRunIds.length || batchDeleteRuns.isPending} onClick={handleBatchDelete}>
            <Trash2 className={batchDeleteRuns.isPending ? "h-4 w-4 animate-pulse" : "h-4 w-4"} />
            批量删除
          </Button>
          <span className="text-xs text-muted-foreground">已选 {selectedRunIds.length}</span>
        </CardContent>
      </Card>

      {error instanceof Error && (
        <Card className="mb-4 border-destructive/50">
          <CardContent className="p-4 text-sm text-destructive">{parseError(error)}</CardContent>
        </Card>
      )}
      {batchDeleteRuns.error instanceof Error && (
        <Card className="mb-4 border-destructive/50">
          <CardContent className="p-4 text-sm text-destructive">{parseError(batchDeleteRuns.error)}</CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">任务列表</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <Checkbox
                    checked={allDeletableSelected}
                    disabled={!deletableIds.length}
                    onCheckedChange={(checked) => toggleAllVisible(Boolean(checked))}
                    aria-label="选择当前页可删除扫描任务"
                  />
                </TableHead>
                <TableHead>任务</TableHead>
                <TableHead>仓库</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>进度</TableHead>
                <TableHead>当前文件 / 摘要</TableHead>
                <TableHead>结果</TableHead>
                <TableHead>时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={9} className="h-28 text-center text-muted-foreground">
                    正在读取扫描任务...
                  </TableCell>
                </TableRow>
              )}
              {!isLoading &&
                runs.map((run) => {
                  const active = activeStatuses.has(run.status);
                  return (
                    <TableRow key={run.id}>
                      <TableCell>
                        <Checkbox
                          checked={selectedRunIds.includes(run.id)}
                          disabled={active}
                          onCheckedChange={(checked) => toggleRun(run, Boolean(checked))}
                          aria-label={`选择扫描任务 ${run.id}`}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">#{run.id}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{run.use_ai ? "Qwen 辅助" : "规则扫描"}</div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-56 truncate font-medium" title={run.repo_name || `repo ${run.repo_id}`}>
                          {run.repo_owner ? `${run.repo_owner}/` : ""}
                          {run.repo_name || `repo ${run.repo_id}`}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">{run.repo_category ? categoryLabels[run.repo_category] || run.repo_category : "-"}</div>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={run.status} />
                      </TableCell>
                      <TableCell className="min-w-40">
                        <ProgressBar value={run.progress_percent} />
                        <div className="mt-1 text-xs text-muted-foreground">
                          {run.progress_percent || 0}% · 文件 {run.processed_files || 0}/{run.total_files || 0}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-80 whitespace-normal text-xs leading-5 text-muted-foreground">
                          {run.current_file || run.summary || run.error || "等待进度更新"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="grid gap-1 text-xs text-muted-foreground">
                          <span>Prompt {run.prompt_candidates || 0}</span>
                          <span>候选 {run.pair_candidates || 0}</span>
                          <span>正式 {run.prompt_pairs_added || 0}</span>
                          <span>图片 {run.downloaded_images || run.images_added || 0}</span>
                          {!!run.error_count && <span className="text-destructive">错误 {run.error_count}</span>}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="grid gap-2">
                          <DateStack value={run.started_at || run.created_at} />
                          {run.finished_at && <DateStack value={run.finished_at} />}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1.5">
                          {run.repo_url && (
                            <Button variant="outline" size="icon-sm" onClick={() => window.open(run.repo_url || "", "_blank")} title="打开 GitHub">
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          )}
                          <Button variant="outline" size="sm" onClick={() => navigate("/repos")}>
                            资源库
                          </Button>
                          {active && (
                            <Button variant="destructive" size="sm" disabled={cancelRun.isPending} onClick={() => requestCancel(run)}>
                              <XCircle className="h-4 w-4" />
                              取消
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              {!isLoading && !runs.length && (
                <TableRow>
                  <TableCell colSpan={9} className="h-28 text-center text-muted-foreground">
                    暂无扫描任务。你可以在资源库中选择仓库后点击扫描。
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <PaginationBar className="mt-4" page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} isLoading={isLoading || isFetching} />
    </div>
  );
}
