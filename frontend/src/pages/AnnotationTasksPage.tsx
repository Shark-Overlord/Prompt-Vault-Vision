import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, ClipboardPenLine, Eye, Loader2, Pause, Pencil, Play, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Checkbox } from "../components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "../components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import { useAiConfigs } from "../hooks/useAiConfigs";
import {
  useAnnotationQueue,
  useAnnotationRunActions,
  useAnnotationRuns,
  useAnnotationSuggestionActions,
  useAnnotationSuggestions,
  useCancelAnnotationRun,
  useCreateAnnotationRun
} from "../hooks/useAnnotations";
import { api } from "../lib/api";
import type { AnnotationQueueItem, AnnotationRun, AnnotationSuggestion } from "../lib/types";
import { assetUrl, truncate } from "../lib/utils";

const suggestionStatusOptions = [
  ["pending_review", "待确认"],
  ["accepted", "已接受"],
  ["rejected", "已拒绝"],
  ["failed", "失败"],
  ["all", "全部"]
];

const activeRunStatuses = new Set(["queued", "running", "cancel_requested"]);

function parseTags(value?: string | null) {
  if (!value) return [];
  try {
    const data = JSON.parse(value);
    return Array.isArray(data) ? data.map(String).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function runProgress(run: { total_items?: number; processed_items?: number }) {
  const total = Math.max(1, Number(run.total_items || 0));
  return Math.round((Number(run.processed_items || 0) / total) * 100);
}

function parseRunOptions(run?: Pick<AnnotationRun, "options_json"> | null) {
  if (!run?.options_json) return {};
  try {
    const data = JSON.parse(run.options_json);
    return data && typeof data === "object" ? data : {};
  } catch {
    return {};
  }
}

function formatRunTime(value?: string | null) {
  if (!value) return "未设置";
  return value.replace("T", " ").replace("+00:00", "");
}

function SuggestionDrawer({
  suggestion,
  onClose,
  aiConfigId,
  onRegenerate
}: {
  suggestion: AnnotationSuggestion | null;
  onClose: () => void;
  aiConfigId?: number | null;
  onRegenerate: (pairId: number, aiConfigId?: number | null) => void;
}) {
  const actions = useAnnotationSuggestionActions();
  const [cn, setCn] = useState("");
  const [tags, setTags] = useState("");
  const [imageType, setImageType] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    setCn(suggestion?.suggested_cn_explanation || "");
    setTags(parseTags(suggestion?.suggested_tags_json).join("，"));
    setImageType(suggestion?.image_type_cn || "");
    setReason(suggestion?.reason_cn || "");
  }, [suggestion]);

  const patchPayload = () => ({
    suggested_cn_explanation: cn,
    suggested_tags: tags
      .split(/[，,、;；\n]+/)
      .map((item) => item.trim())
      .filter(Boolean),
    image_type_cn: imageType,
    reason_cn: reason
  });

  const save = () => {
    if (!suggestion) return;
    actions.update.mutate({ id: suggestion.id, payload: patchPayload() });
  };

  const acceptEdited = () => {
    if (!suggestion) return;
    actions.update.mutate(
      { id: suggestion.id, payload: patchPayload() },
      {
        onSuccess: () => {
          actions.accept.mutate(suggestion.id, { onSuccess: onClose });
        }
      }
    );
  };

  return (
    <Sheet open={Boolean(suggestion)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-[90vw] overflow-y-auto data-[side=right]:sm:max-w-5xl">
        {suggestion && (
          <>
            <SheetHeader className="border-b pr-12">
              <SheetDescription>AI 翻译与标签草稿审核</SheetDescription>
              <SheetTitle>{suggestion.repo_name || `Prompt #${suggestion.pair_id}`}</SheetTitle>
            </SheetHeader>
            <div className="grid gap-6 p-6 lg:grid-cols-[1fr_1fr]">
              <div className="space-y-4">
                <Card>
                  <CardContent className="p-0">
                    {suggestion.image_local_path ? (
                      <img src={assetUrl(suggestion.image_local_path)} alt={suggestion.repo_name || "annotation"} className="max-h-[560px] w-full object-contain" />
                    ) : (
                      <div className="grid h-80 place-items-center text-muted-foreground">暂无效果图</div>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>原始 Prompt</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 text-xs leading-5">{suggestion.original_prompt || "暂无"}</pre>
                  </CardContent>
                </Card>
              </div>
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge>{suggestion.status}</Badge>
                  <Badge variant="secondary">{suggestion.prompt_language || "unknown"}</Badge>
                  <Badge variant="outline">置信度 {suggestion.confidence || 0}</Badge>
                </div>
                {suggestion.error && <Card className="border-destructive/50"><CardContent className="p-3 text-sm text-destructive">{suggestion.error}</CardContent></Card>}
                <label className="space-y-2 block">
                  <span className="text-xs text-muted-foreground">中文翻译（忠实翻译原始 Prompt）</span>
                  <Textarea value={cn} onChange={(event) => setCn(event.target.value)} className="min-h-32 resize-y" />
                </label>
                <label className="space-y-2 block">
                  <span className="text-xs text-muted-foreground">中文标签，建议 4-5 个</span>
                  <Input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="产品摄影，商业海报，高级质感，..." />
                </label>
                <label className="space-y-2 block">
                  <span className="text-xs text-muted-foreground">效果图类型</span>
                  <Input value={imageType} onChange={(event) => setImageType(event.target.value)} />
                </label>
                <label className="space-y-2 block">
                  <span className="text-xs text-muted-foreground">AI 理由</span>
                  <Textarea value={reason} onChange={(event) => setReason(event.target.value)} className="min-h-24 resize-y" />
                </label>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={acceptEdited} disabled={actions.update.isPending || actions.accept.isPending}>
                    <Check className="h-4 w-4" />
                    编辑后接受
                  </Button>
                  <Button variant="secondary" onClick={save} disabled={actions.update.isPending}>
                    保存草稿
                  </Button>
                  <Button variant="outline" onClick={() => onRegenerate(suggestion.pair_id, aiConfigId)}>
                    <RefreshCw className="h-4 w-4" />
                    重新生成
                  </Button>
                  <Button variant="destructive" onClick={() => actions.reject.mutate(suggestion.id, { onSuccess: onClose })} disabled={actions.reject.isPending}>
                    <X className="h-4 w-4" />
                    拒绝
                  </Button>
                </div>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

export function AnnotationTasksPage() {
  const [queuePage, setQueuePage] = useState(1);
  const [runPage, setRunPage] = useState(1);
  const [suggestionPage, setSuggestionPage] = useState(1);
  const [selectedPairIds, setSelectedPairIds] = useState<number[]>([]);
  const [limit, setLimit] = useState("20");
  const [aiConfigId, setAiConfigId] = useState("default");
  const [suggestionStatus, setSuggestionStatus] = useState("pending_review");
  const [selectedSuggestion, setSelectedSuggestion] = useState<AnnotationSuggestion | null>(null);
  const [selectedRun, setSelectedRun] = useState<AnnotationRun | null>(null);
  const [editingRun, setEditingRun] = useState<AnnotationRun | null>(null);
  const [editLimit, setEditLimit] = useState("20");
  const [editAiConfigId, setEditAiConfigId] = useState("default");

  const queuePageSize = 20;
  const runPageSize = 20;
  const suggestionPageSize = 20;
  const queueFilters = useMemo(
    () => ({
      page: queuePage,
      page_size: queuePageSize,
      annotation_status: "unannotated"
    }),
    [queuePage]
  );
  const { data: queueData, isLoading: queueLoading } = useAnnotationQueue(queueFilters);
  const { data: runsData, isFetching: runsFetching } = useAnnotationRuns({ page: runPage, page_size: runPageSize });
  const { data: suggestionData, isLoading: suggestionsLoading } = useAnnotationSuggestions({
    page: suggestionPage,
    page_size: suggestionPageSize,
    status: suggestionStatus === "all" ? undefined : suggestionStatus
  });
  const { data: aiConfigs = [] } = useAiConfigs();
  const createRun = useCreateAnnotationRun();
  const cancelRun = useCancelAnnotationRun();
  const runActions = useAnnotationRunActions();
  const queueItems = queueData?.items || [];
  const suggestions = suggestionData?.items || [];
  const activeRuns = (runsData?.items || []).filter((run) => activeRunStatuses.has(run.status));
  const visibleIds = queueItems.map((item) => item.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedPairIds.includes(id));

  useEffect(() => {
    setQueuePage(1);
    setSuggestionPage(1);
    setSelectedPairIds([]);
  }, [suggestionStatus]);

  useEffect(() => {
    if (!editingRun) return;
    const options = parseRunOptions(editingRun);
    setEditLimit(String(options.limit || editingRun.total_items || 20));
    setEditAiConfigId(editingRun.ai_config_id ? String(editingRun.ai_config_id) : "default");
  }, [editingRun]);

  const selectedAiConfigId = aiConfigId === "default" ? null : Number(aiConfigId);
  const createPayload = (pairIds?: number[]) => ({
    limit: Math.min(Math.max(Number(limit) || 20, 1), 200),
    pair_ids: pairIds || (selectedPairIds.length ? selectedPairIds : null),
    ai_config_id: selectedAiConfigId,
    allow_pending_suggestions: false,
    annotation_status: "unannotated"
  });

  const startRun = () => {
    if (activeRuns.length) return;
    createRun.mutate(createPayload(), { onSuccess: () => setSelectedPairIds([]) });
  };

  const regenerateOne = (pairId: number, configId?: number | null) => {
    createRun.mutate({ limit: 1, pair_ids: [pairId], ai_config_id: configId ?? selectedAiConfigId, allow_pending_suggestions: true });
  };

  const saveRunEdit = () => {
    if (!editingRun) return;
    runActions.update.mutate(
      {
        id: editingRun.id,
        payload: {
          limit: Math.min(Math.max(Number(editLimit) || 20, 1), 200),
          ai_config_id: editAiConfigId === "default" ? null : Number(editAiConfigId),
          annotation_status: "unannotated"
        }
      },
      { onSuccess: () => setEditingRun(null) }
    );
  };

  const deleteRun = (run: AnnotationRun) => {
    if (window.confirm(`删除标注任务 #${run.id}？草稿会保留，但不再关联这个任务。`)) {
      runActions.remove.mutate(run.id);
    }
  };

  const toggleAll = (checked: boolean) => {
    setSelectedPairIds((prev) => {
      const current = new Set(visibleIds);
      if (!checked) return prev.filter((id) => !current.has(id));
      return Array.from(new Set([...prev, ...visibleIds]));
    });
  };

  const togglePair = (pair: AnnotationQueueItem, checked: boolean) => {
    setSelectedPairIds((prev) => (checked ? Array.from(new Set([...prev, pair.id])) : prev.filter((id) => id !== pair.id)));
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs text-muted-foreground">Annotation Tasks</div>
          <h1 className="text-2xl font-semibold">标注任务</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">AI 生成原始 Prompt 的中文翻译和中文标签草稿，人工确认后才写入正式 Prompt 效果库。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={aiConfigId} onValueChange={setAiConfigId}>
            <SelectTrigger className="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">默认 AI 配置</SelectItem>
              {aiConfigs.map((config) => (
                <SelectItem key={config.id} value={String(config.id)}>
                  {config.name} · {config.model}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input className="w-28" type="number" min={1} max={200} value={limit} onChange={(event) => setLimit(event.target.value)} />
          <Button onClick={startRun} disabled={createRun.isPending || activeRuns.length > 0}>
            {createRun.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            生成标注草稿
          </Button>
          {activeRuns.length > 0 && (
            <Button variant="destructive" onClick={() => activeRuns.forEach((run) => cancelRun.mutate(run.id))} disabled={cancelRun.isPending}>
              {cancelRun.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
              停止当前任务
            </Button>
          )}
        </div>
      </div>

      {createRun.error instanceof Error && <Card className="border-destructive/50"><CardContent className="p-4 text-sm text-destructive">{createRun.error.message}</CardContent></Card>}

      <Tabs defaultValue="queue" className="space-y-4">
        <TabsList className="grid h-11 w-full grid-cols-3">
          <TabsTrigger value="queue" className="gap-2">
            标注队列
            <Badge variant="outline">{queueData?.total ?? 0}</Badge>
          </TabsTrigger>
          <TabsTrigger value="runs" className="gap-2">
            任务运行
            <Badge variant={activeRuns.length ? "secondary" : "outline"}>{activeRuns.length || runsData?.total || 0}</Badge>
          </TabsTrigger>
          <TabsTrigger value="suggestions" className="gap-2">
            草稿审核
            <Badge variant="outline">{suggestionData?.total ?? 0}</Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="queue" className="mt-0">
          <Card className="min-w-0">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base"><ClipboardPenLine className="h-4 w-4" />标注队列</CardTitle>
              <span className="text-xs text-muted-foreground">已选 {selectedPairIds.length}</span>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12"><Checkbox checked={allVisibleSelected} onCheckedChange={(checked) => toggleAll(Boolean(checked))} /></TableHead>
                    <TableHead>效果图</TableHead>
                    <TableHead>Prompt</TableHead>
                    <TableHead>当前标注</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {queueLoading && <TableRow><TableCell colSpan={5} className="h-28 text-center text-muted-foreground">正在读取标注队列...</TableCell></TableRow>}
                  {!queueLoading && queueItems.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell><Checkbox checked={selectedPairIds.includes(item.id)} onCheckedChange={(checked) => togglePair(item, Boolean(checked))} /></TableCell>
                      <TableCell>
                        {item.image_local_path ? <img src={assetUrl(item.image_local_path)} alt={item.repo_name} className="h-20 w-28 rounded-md object-cover" /> : <div className="h-20 w-28 rounded-md border bg-muted" />}
                      </TableCell>
                      <TableCell className="max-w-xl">
                        <div className="font-medium">{item.repo_name}</div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">{truncate(item.original_prompt || "", 220)}</div>
                      </TableCell>
                      <TableCell>
                        <div className="text-xs text-muted-foreground">翻译：{item.prompt_cn_explanation ? "已有" : "缺失"}</div>
                        <div className="mt-1 text-xs text-muted-foreground">标签：{item.tag_count || 0}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={item.annotation_status === "annotated" ? "default" : "outline"}>{item.annotation_status}</Badge>
                        {item.latest_suggestion_status && <div className="mt-2 text-xs text-muted-foreground">草稿：{item.latest_suggestion_status}</div>}
                      </TableCell>
                    </TableRow>
                  ))}
                  {!queueLoading && !queueItems.length && <TableRow><TableCell colSpan={5} className="h-28 text-center text-muted-foreground">暂无符合条件的待标注效果图。</TableCell></TableRow>}
                </TableBody>
              </Table>
              <div className="p-4">
                <PaginationBar page={queuePage} pageSize={queuePageSize} total={queueData?.total || 0} onPageChange={setQueuePage} isLoading={queueLoading} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="runs" className="mt-0">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">任务列表</CardTitle>
              {runsFetching && <div className="text-xs text-muted-foreground">正在刷新...</div>}
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>任务</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>参数</TableHead>
                    <TableHead>进度</TableHead>
                    <TableHead>时间</TableHead>
                    <TableHead>结果</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(runsData?.items || []).map((run) => {
                    const active = activeRunStatuses.has(run.status);
                    const options = parseRunOptions(run);
                    return (
                      <TableRow key={run.id}>
                        <TableCell className="font-medium">#{run.id}</TableCell>
                        <TableCell>
                          <Badge variant={active ? "secondary" : run.status === "failed" ? "destructive" : "outline"}>{run.status}</Badge>
                          {run.status === "cancel_requested" && <div className="mt-1 text-xs text-muted-foreground">正在停止</div>}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          <div>数量：{options.limit || run.total_items || 0}</div>
                          <div>AI：{run.ai_config_id ? `#${run.ai_config_id}` : "默认配置"}</div>
                        </TableCell>
                        <TableCell className="min-w-40">
                          <div className="h-2 overflow-hidden rounded-full bg-muted">
                            <div className="h-full rounded-full bg-primary" style={{ width: `${runProgress(run)}%` }} />
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">{run.processed_items}/{run.total_items}</div>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          <div>创建：{formatRunTime(run.created_at)}</div>
                          <div>结束：{formatRunTime(run.finished_at)}</div>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          <div>草稿：{run.created_suggestions}</div>
                          {run.error && (
                            <button className="mt-1 inline-flex items-center gap-1 text-destructive hover:underline" onClick={() => setSelectedRun(run)}>
                              <AlertTriangle className="h-3.5 w-3.5" />
                              查看错误
                            </button>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            {active ? (
                              <Button size="icon-sm" variant="destructive" onClick={() => runActions.pause.mutate(run.id)} disabled={runActions.pause.isPending || run.status === "cancel_requested"}>
                                <Pause className="h-4 w-4" />
                              </Button>
                            ) : (
                              <Button size="icon-sm" variant="outline" onClick={() => runActions.rerun.mutate(run.id)} disabled={runActions.rerun.isPending || activeRuns.length > 0}>
                                <Play className="h-4 w-4" />
                              </Button>
                            )}
                            <Button size="icon-sm" variant="outline" onClick={() => setEditingRun(run)} disabled={active}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button size="icon-sm" variant="outline" onClick={() => setSelectedRun(run)}>
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button size="icon-sm" variant="destructive" onClick={() => deleteRun(run)} disabled={active || runActions.remove.isPending}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {!runsData?.items?.length && <TableRow><TableCell colSpan={7} className="h-28 text-center text-muted-foreground">暂无标注任务。</TableCell></TableRow>}
                </TableBody>
              </Table>
              <div className="p-4">
                <PaginationBar page={runPage} pageSize={runPageSize} total={runsData?.total || 0} onPageChange={setRunPage} isLoading={runsFetching} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="suggestions" className="mt-0">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">草稿审核</CardTitle>
              <Select value={suggestionStatus} onValueChange={setSuggestionStatus}>
                <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                <SelectContent>{suggestionStatusOptions.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
              </Select>
            </CardHeader>
            <CardContent className="space-y-3">
              {suggestionsLoading && <div className="text-sm text-muted-foreground">正在读取草稿...</div>}
              <div className="grid gap-3 lg:grid-cols-2">
                {suggestions.map((suggestion) => (
                  <button key={suggestion.id} className="w-full rounded-lg border bg-muted/10 p-3 text-left hover:bg-muted/20" onClick={() => setSelectedSuggestion(suggestion)}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">{suggestion.repo_name || `Prompt #${suggestion.pair_id}`}</span>
                      <Badge variant={suggestion.status === "pending_review" ? "secondary" : "outline"}>{suggestion.status}</Badge>
                    </div>
                    <div className="mt-2 text-xs leading-5 text-muted-foreground">{truncate(suggestion.suggested_cn_explanation || suggestion.error || "暂无中文翻译", 120)}</div>
                    <div className="mt-2 flex flex-wrap gap-1">{parseTags(suggestion.suggested_tags_json).map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}</div>
                  </button>
                ))}
              </div>
              {!suggestionsLoading && !suggestions.length && <div className="text-sm text-muted-foreground">暂无草稿。</div>}
              <PaginationBar page={suggestionPage} pageSize={suggestionPageSize} total={suggestionData?.total || 0} onPageChange={setSuggestionPage} isLoading={suggestionsLoading} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={Boolean(editingRun)} onOpenChange={(open) => !open && setEditingRun(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑标注任务</DialogTitle>
            <DialogDescription>只能编辑已结束或已暂停任务的复跑参数；保存后点击运行会按新参数重新创建任务。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <label className="space-y-2">
              <span className="text-xs text-muted-foreground">处理数量</span>
              <Input type="number" min={1} max={200} value={editLimit} onChange={(event) => setEditLimit(event.target.value)} />
            </label>
            <label className="space-y-2">
              <span className="text-xs text-muted-foreground">AI 配置</span>
              <Select value={editAiConfigId} onValueChange={setEditAiConfigId}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">默认 AI 配置</SelectItem>
                  {aiConfigs.map((config) => (
                    <SelectItem key={config.id} value={String(config.id)}>
                      {config.name} · {config.model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingRun(null)}>取消</Button>
            <Button onClick={saveRunEdit} disabled={runActions.update.isPending}>
              {runActions.update.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(selectedRun)} onOpenChange={(open) => !open && setSelectedRun(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>标注任务详情 {selectedRun ? `#${selectedRun.id}` : ""}</DialogTitle>
            <DialogDescription>查看任务状态、运行参数和失败原因。</DialogDescription>
          </DialogHeader>
          {selectedRun && (
            <div className="grid gap-4 text-sm">
              <div className="grid gap-2 rounded-lg border bg-muted/20 p-3 md:grid-cols-2">
                <div>状态：<Badge variant={selectedRun.status === "failed" ? "destructive" : "outline"}>{selectedRun.status}</Badge></div>
                <div>草稿：{selectedRun.created_suggestions}</div>
                <div>进度：{selectedRun.processed_items}/{selectedRun.total_items}</div>
                <div>AI：{selectedRun.ai_config_id ? `#${selectedRun.ai_config_id}` : "默认配置"}</div>
                <div>创建：{formatRunTime(selectedRun.created_at)}</div>
                <div>结束：{formatRunTime(selectedRun.finished_at)}</div>
              </div>
              {selectedRun.error && (
                <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-destructive">
                  <div className="mb-2 flex items-center gap-2 font-medium"><AlertTriangle className="h-4 w-4" />失败原因</div>
                  <pre className="whitespace-pre-wrap text-xs leading-5">{selectedRun.error}</pre>
                </div>
              )}
              <div>
                <div className="mb-2 text-xs text-muted-foreground">任务参数</div>
                <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/20 p-3 text-xs leading-5">{JSON.stringify(parseRunOptions(selectedRun), null, 2)}</pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <SuggestionDrawer suggestion={selectedSuggestion} onClose={() => setSelectedSuggestion(null)} aiConfigId={selectedAiConfigId} onRegenerate={regenerateOne} />
    </div>
  );
}
