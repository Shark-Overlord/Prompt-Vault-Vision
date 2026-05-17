import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  CheckCircle2,
  History,
  Loader2,
  Pause,
  Pencil,
  Play,
  Plus,
  SearchCheck,
  SkipForward,
  Trash2,
  XCircle
} from "lucide-react";
import {
  useCreateScheduledTask,
  useDeleteScheduledTask,
  useRunScheduledTaskNow,
  useScheduledTaskRuns,
  useScheduledTasks,
  useUpdateScheduledTask
} from "../hooks/useScheduledTasks";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { categoryLabels } from "../lib/constants";
import type { ScheduledTask, ScheduledTaskPayload, ScheduledTaskStatus, ScheduleType, TaskRunStatus } from "../lib/types";
import { Badge } from "../components/ui/badge";
import { Button, buttonVariants } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";

type TaskForm = {
  name: string;
  status: ScheduledTaskStatus;
  schedule_type: ScheduleType;
  interval_minutes: string;
  daily_time: string;
  weekly_day: string;
  weekly_time: string;
  category: string;
  keywords: string;
  per_keyword_limit: string;
  allow_anonymous: boolean;
};

const defaultForm: TaskForm = {
  name: "GitHub 仓库发现",
  status: "paused",
  schedule_type: "daily_time",
  interval_minutes: "60",
  daily_time: "09:00",
  weekly_day: "0",
  weekly_time: "09:00",
  category: "all",
  keywords: "",
  per_keyword_limit: "30",
  allow_anonymous: false
};

const weekDays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function parseError(error: unknown) {
  if (!(error instanceof Error)) return "";
  try {
    const payload = JSON.parse(error.message) as { detail?: string };
    return payload.detail || error.message;
  } catch {
    return error.message;
  }
}

function formatDate(value?: string | null) {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    const cleaned = value.replace(/([+-]\d{2}:\d{2}|Z)$/i, "");
    const [rawDate, rawTime = ""] = cleaned.split("T");
    return `${rawDate} ${rawTime.slice(0, 5)}`;
  }
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatDuration(ms?: number | null) {
  if (!ms) return "0s";
  if (ms < 1000) return `${ms}ms`;
  return `${Math.round(ms / 1000)}s`;
}

function describeSchedule(task: ScheduledTask) {
  if (task.schedule_type === "interval_minutes") {
    const minutes = task.interval_minutes || 0;
    return minutes >= 60 && minutes % 60 === 0 ? `每 ${minutes / 60} 小时` : `每 ${minutes} 分钟`;
  }
  if (task.schedule_type === "daily_time") return `每天 ${task.daily_time}`;
  return `每 ${weekDays[task.weekly_day ?? 0]} ${task.weekly_time}`;
}

function formFromTask(task: ScheduledTask): TaskForm {
  return {
    name: task.name,
    status: task.status,
    schedule_type: task.schedule_type,
    interval_minutes: String(task.interval_minutes || 60),
    daily_time: task.daily_time || "09:00",
    weekly_day: String(task.weekly_day ?? 0),
    weekly_time: task.weekly_time || "09:00",
    category: task.categories?.[0] || "all",
    keywords: task.keywords?.join(", ") || "",
    per_keyword_limit: String(task.per_keyword_limit || 30),
    allow_anonymous: Boolean(task.allow_anonymous)
  };
}

function taskPayloadFromForm(form: TaskForm): ScheduledTaskPayload {
  const keywords = form.keywords
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  return {
    name: form.name,
    task_type: "github_incremental_search",
    status: form.status,
    schedule_type: form.schedule_type,
    interval_minutes: form.schedule_type === "interval_minutes" ? Number(form.interval_minutes) || 60 : null,
    daily_time: form.schedule_type === "daily_time" ? form.daily_time : null,
    weekly_day: form.schedule_type === "weekly_time" ? Number(form.weekly_day) : null,
    weekly_time: form.schedule_type === "weekly_time" ? form.weekly_time : null,
    categories: form.category && form.category !== "all" ? [form.category] : null,
    keywords: keywords.length ? keywords : null,
    per_keyword_limit: Number(form.per_keyword_limit) || 30,
    allow_anonymous: form.allow_anonymous
  };
}

function StatusBadge({ status, running, legacy }: { status: ScheduledTaskStatus; running?: boolean; legacy?: boolean }) {
  if (legacy) return <Badge variant="secondary">旧任务已停用</Badge>;
  if (running) return <Badge variant="secondary">运行中</Badge>;
  return status === "active" ? <Badge>已启用</Badge> : <Badge variant="outline">已暂停</Badge>;
}

function RunStatusBadge({ status }: { status?: TaskRunStatus | null }) {
  if (status === "success") {
    return (
      <Badge>
        <CheckCircle2 className="size-3" />
        成功
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="destructive">
        <XCircle className="size-3" />
        失败
      </Badge>
    );
  }
  if (status === "skipped") {
    return (
      <Badge variant="secondary">
        <SkipForward className="size-3" />
        跳过
      </Badge>
    );
  }
  if (status === "started") return <Badge variant="outline">执行中</Badge>;
  return <Badge variant="outline">无记录</Badge>;
}

function TaskConfigForm({
  form,
  setForm,
  mode,
  isPending,
  error,
  onSubmit,
  onCancel
}: {
  form: TaskForm;
  setForm: (form: TaskForm) => void;
  mode: "create" | "edit";
  isPending: boolean;
  error: unknown;
  onSubmit: (event: FormEvent) => void;
  onCancel: () => void;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>{mode === "create" ? "创建仓库发现任务" : "编辑仓库发现任务"}</DialogTitle>
        <DialogDescription>
          定时任务只负责按四类方向发现 GitHub 仓库并写入资源库。仓库内部 Prompt、图片和配对证据必须在资源库页面手动或批量扫描。
        </DialogDescription>
      </DialogHeader>

      <div className="rounded-lg border bg-muted/20 p-3 text-sm text-muted-foreground">
        任务类型固定为 GitHub 仓库发现。资源库扫描不再作为定时任务执行。
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">任务名称</span>
          <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        </label>
        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">状态</span>
          <Select value={form.status} onValueChange={(value) => setForm({ ...form, status: value as ScheduledTaskStatus })}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="paused">暂停</SelectItem>
              <SelectItem value="active">启用</SelectItem>
            </SelectContent>
          </Select>
        </label>
        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">计划类型</span>
          <Select value={form.schedule_type} onValueChange={(value) => setForm({ ...form, schedule_type: value as ScheduleType })}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="interval_minutes">间隔执行</SelectItem>
              <SelectItem value="daily_time">每天固定时间</SelectItem>
              <SelectItem value="weekly_time">每周固定时间</SelectItem>
            </SelectContent>
          </Select>
        </label>
        {form.schedule_type === "interval_minutes" && (
          <label className="space-y-2">
            <span className="text-xs text-muted-foreground">间隔分钟</span>
            <Input min={1} type="number" value={form.interval_minutes} onChange={(event) => setForm({ ...form, interval_minutes: event.target.value })} />
          </label>
        )}
        {form.schedule_type === "daily_time" && (
          <label className="space-y-2">
            <span className="text-xs text-muted-foreground">每日时间</span>
            <Input type="time" value={form.daily_time} onChange={(event) => setForm({ ...form, daily_time: event.target.value })} />
          </label>
        )}
        {form.schedule_type === "weekly_time" && (
          <>
            <label className="space-y-2">
              <span className="text-xs text-muted-foreground">星期</span>
              <Select value={form.weekly_day} onValueChange={(value) => setForm({ ...form, weekly_day: value })}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {weekDays.map((day, index) => (
                    <SelectItem key={day} value={String(index)}>
                      {day}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="space-y-2">
              <span className="text-xs text-muted-foreground">每周时间</span>
              <Input type="time" value={form.weekly_time} onChange={(event) => setForm({ ...form, weekly_time: event.target.value })} />
            </label>
          </>
        )}
        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">检索分类</span>
          <Select value={form.category} onValueChange={(value) => setForm({ ...form, category: value })}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">四类全部</SelectItem>
              {Object.entries(categoryLabels).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">单关键词仓库数</span>
          <Input min={1} max={50} type="number" value={form.per_keyword_limit} onChange={(event) => setForm({ ...form, per_keyword_limit: event.target.value })} />
        </label>
        <label className="space-y-2 md:col-span-2">
          <span className="text-xs text-muted-foreground">关键词覆盖，逗号分隔</span>
          <Input
            placeholder="留空则使用该分类的默认关键词"
            value={form.keywords}
            onChange={(event) => setForm({ ...form, keywords: event.target.value })}
          />
        </label>
        <div className="flex items-center justify-between rounded-lg border bg-muted/30 p-3 md:col-span-2">
          <div>
            <div className="text-sm font-medium">允许匿名搜索</div>
            <div className="text-xs text-muted-foreground">关闭时，未连接 GitHub 会失败并写入运行记录，不推进增量窗口。</div>
          </div>
          <Switch checked={form.allow_anonymous} onCheckedChange={(checked) => setForm({ ...form, allow_anonymous: checked })} />
        </div>
      </div>

      {Boolean(error) && <div className="text-sm text-destructive">{parseError(error)}</div>}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          取消
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending && <Loader2 className="size-4 animate-spin" />}
          保存配置
        </Button>
      </DialogFooter>
    </form>
  );
}

export function ScheduledTasksPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [createForm, setCreateForm] = useState<TaskForm>(defaultForm);
  const [editForm, setEditForm] = useState<TaskForm>(defaultForm);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const { data: tasksData, isLoading } = useScheduledTasks({ page, page_size: pageSize });
  const tasks = tasksData?.items || [];
  const createTask = useCreateScheduledTask();
  const updateTask = useUpdateScheduledTask();
  const deleteTask = useDeleteScheduledTask();
  const runNow = useRunScheduledTaskNow();
  const [manualRunningTaskId, setManualRunningTaskId] = useState<number | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<number | undefined>();
  const selectedTask = tasks.find((task) => task.id === selectedTaskId) || tasks[0];
  const [runPage, setRunPage] = useState(1);
  const runPageSize = 20;
  const { data: runsData = { items: [], page: 1, page_size: runPageSize, total: 0 } } = useScheduledTaskRuns(selectedTask?.id, { page: runPage, page_size: runPageSize });
  const runs = runsData.items;

  useEffect(() => {
    setRunPage(1);
  }, [selectedTask?.id]);

  const stats = useMemo(
    () => ({
      active: tasks.filter((task) => task.status === "active" && task.task_type === "github_incremental_search").length,
      paused: tasks.filter((task) => task.status === "paused" && task.task_type === "github_incremental_search").length,
      running: tasks.filter((task) => task.running).length
    }),
    [tasks]
  );

  const submitCreate = (event: FormEvent) => {
    event.preventDefault();
    createTask.mutate(taskPayloadFromForm(createForm), {
      onSuccess: (task) => {
        setSelectedTaskId(task.id);
        setCreateForm(defaultForm);
        setCreateOpen(false);
      }
    });
  };

  const openEditor = (task: ScheduledTask) => {
    if (task.task_type !== "github_incremental_search") return;
    setEditingTaskId(task.id);
    setEditForm(formFromTask(task));
    setSelectedTaskId(task.id);
    setEditOpen(true);
  };

  const submitEdit = (event: FormEvent) => {
    event.preventDefault();
    if (!editingTaskId) return;
    updateTask.mutate(
      { id: editingTaskId, payload: taskPayloadFromForm(editForm) },
      {
        onSuccess: (task) => {
          setSelectedTaskId(task.id);
          setEditOpen(false);
          setEditingTaskId(null);
        }
      }
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Badge variant="secondary" className="mb-3">
            Repository Discovery
          </Badge>
          <h1 className="text-3xl font-semibold tracking-tight">定时任务</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            定时任务只负责按四类方向发现 GitHub 仓库并写入资源库。仓库内部 Prompt、图片和配对证据，请在资源库页面点击“扫描”或“批量扫描”处理。
          </p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger className={buttonVariants()}>
            <Plus className="size-4" />
            创建发现任务
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <TaskConfigForm
              mode="create"
              form={createForm}
              setForm={setCreateForm}
              isPending={createTask.isPending}
              error={createTask.error}
              onSubmit={submitCreate}
              onCancel={() => setCreateOpen(false)}
            />
          </DialogContent>
        </Dialog>
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent className="sm:max-w-2xl">
            <TaskConfigForm
              mode="edit"
              form={editForm}
              setForm={setEditForm}
              isPending={updateTask.isPending}
              error={updateTask.error}
              onSubmit={submitEdit}
              onCancel={() => setEditOpen(false)}
            />
          </DialogContent>
        </Dialog>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">已启用</CardTitle>
            <Play className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{stats.active}</CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">已暂停</CardTitle>
            <Pause className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{stats.paused}</CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">运行中</CardTitle>
            <CalendarClock className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{stats.running}</CardContent>
        </Card>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <Card className="min-w-0">
          <CardHeader>
            <div className="text-xs text-muted-foreground">GitHub Repository Discovery</div>
            <CardTitle>任务列表</CardTitle>
            <p className="text-xs text-muted-foreground">只发现 Web UI、图像生成、图像编辑、视频生成四类仓库，并写入资源库。</p>
          </CardHeader>
          <CardContent className="min-w-0">
            <Table className="min-w-[860px] table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[26%]">任务</TableHead>
                  <TableHead className="w-24">状态</TableHead>
                  <TableHead className="w-24">计划</TableHead>
                  <TableHead className="hidden w-32 lg:table-cell">下次运行</TableHead>
                  <TableHead className="w-[24%]">最近结果</TableHead>
                  <TableHead className="w-40 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => {
                  const legacy = task.task_type !== "github_incremental_search";
                  return (
                    <TableRow key={task.id} className="cursor-pointer" onClick={() => setSelectedTaskId(task.id)}>
                      <TableCell className="min-w-0 whitespace-normal">
                        <div className="truncate font-medium" title={task.name}>
                          {task.name}
                        </div>
                        <div className="mt-1 truncate text-xs text-muted-foreground">
                          {legacy ? "旧资源库扫描任务" : "GitHub 仓库发现"} ·{" "}
                          {task.categories?.map((category) => categoryLabels[category] || category).join(" / ") || "四类全部"} · 每词 {task.per_keyword_limit} 个仓库
                        </div>
                        {task.keywords?.length ? <div className="mt-1 truncate text-xs text-muted-foreground">{task.keywords.join(", ")}</div> : null}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={task.status} running={task.running} legacy={legacy} />
                      </TableCell>
                      <TableCell>{describeSchedule(task)}</TableCell>
                      <TableCell className="hidden lg:table-cell">{formatDate(task.next_run_at)}</TableCell>
                      <TableCell className="min-w-0 whitespace-normal">
                        <div className="space-y-1">
                          <RunStatusBadge status={task.last_status} />
                          {task.last_summary && <div className="max-w-full truncate text-xs text-muted-foreground">{task.last_summary}</div>}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={(event) => event.stopPropagation()}>
                          {(() => {
                            const isManualRunning = manualRunningTaskId === task.id;
                            const isAnotherManualRunning = manualRunningTaskId !== null && manualRunningTaskId !== task.id;
                            const showRunningIcon = isManualRunning || task.running;
                            return (
                              <>
                                <Switch
                                  checked={!legacy && task.status === "active"}
                                  disabled={legacy || updateTask.isPending}
                                  onCheckedChange={(checked) => updateTask.mutate({ id: task.id, payload: { status: checked ? "active" : "paused" } })}
                                />
                                <Button size="icon-sm" variant="outline" disabled={legacy} onClick={() => openEditor(task)} title="编辑配置">
                                  <Pencil className="size-4" />
                                </Button>
                                <Button
                                  size="icon-sm"
                                  variant="outline"
                                  disabled={legacy || isAnotherManualRunning || showRunningIcon}
                                  onClick={() => {
                                    setManualRunningTaskId(task.id);
                                    runNow.mutate(task.id, { onSettled: () => setManualRunningTaskId(null) });
                                  }}
                                  title="立即运行"
                                >
                                  {showRunningIcon ? <Loader2 className="size-4 animate-spin" /> : <SearchCheck className="size-4" />}
                                </Button>
                                <Button size="icon-sm" variant="ghost" onClick={() => setSelectedTaskId(task.id)} title="运行历史">
                                  <History className="size-4" />
                                </Button>
                                <Button size="icon-sm" variant="destructive" disabled={deleteTask.isPending} onClick={() => deleteTask.mutate(task.id)} title="删除">
                                  <Trash2 className="size-4" />
                                </Button>
                              </>
                            );
                          })()}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {!tasks.length && (
                  <TableRow>
                    <TableCell colSpan={6} className="h-36 text-center text-muted-foreground">
                      {isLoading ? "正在读取任务..." : "尚未创建定时任务。点击右上角创建第一条仓库发现任务。"}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
            <PaginationBar className="mt-4" page={page} pageSize={pageSize} total={tasksData?.total || 0} onPageChange={setPage} isLoading={isLoading} />
            {(updateTask.error || deleteTask.error || runNow.error) && <div className="mt-4 text-sm text-destructive">{parseError(updateTask.error || deleteTask.error || runNow.error)}</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="text-xs text-muted-foreground">Run History</div>
            <CardTitle>{selectedTask ? selectedTask.name : "运行历史"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {runs.map((run) => (
              <div key={run.id} className="rounded-lg border bg-muted/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <RunStatusBadge status={run.status} />
                  <span className="text-xs text-muted-foreground">
                    {formatDate(run.started_at)} · {formatDuration(run.duration_ms)}
                  </span>
                </div>
                <div className="mt-2 text-sm">{run.summary || run.error || "暂无摘要"}</div>
                <div className="mt-2 text-xs text-muted-foreground">触发方式：{run.trigger_type === "scheduled" ? "定时触发" : "手动执行"}</div>
              </div>
            ))}
            {selectedTask && !runs.length && <div className="grid h-36 place-items-center text-center text-sm text-muted-foreground">暂无运行记录。</div>}
            {!selectedTask && <div className="grid h-36 place-items-center text-center text-sm text-muted-foreground">选择任务后查看历史。</div>}
            {selectedTask && <PaginationBar page={runPage} pageSize={runPageSize} total={runsData.total} onPageChange={setRunPage} />}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
