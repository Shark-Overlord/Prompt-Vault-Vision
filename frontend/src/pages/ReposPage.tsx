import { FormEvent, useEffect, useState } from "react";
import { Plus, RefreshCw, Save, Search, Trash2, X } from "lucide-react";
import { FilterBar } from "../components/filters/FilterBar";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { RepoDetailDrawer } from "../components/repos/RepoDetailDrawer";
import { RepoScanDialog } from "../components/repos/RepoScanDialog";
import { RepoTable } from "../components/repos/RepoTable";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
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
import { Textarea } from "../components/ui/textarea";
import {
  useBatchDeleteRepos,
  useBatchScanRepos,
  useCreateRepo,
  useDeleteRepo,
  useRepos,
  useScanRepo,
  useUpdateRepo
} from "../hooks/useRepos";
import { categoryLabels } from "../lib/constants";
import type { Repo, RepoPayload, RepoScanPayload } from "../lib/types";
import { useFilterStore } from "../stores/useFilterStore";

type RepoForm = {
  repo_url: string;
  repo_name: string;
  owner: string;
  category: string;
  quality_level: string;
  status: string;
  license: string;
  stars: string;
  forks: string;
  summary: string;
  notes: string;
};

const defaultForm: RepoForm = {
  repo_url: "",
  repo_name: "",
  owner: "",
  category: "image_generation_prompt",
  quality_level: "pending_review",
  status: "pending_review",
  license: "unknown",
  stars: "0",
  forks: "0",
  summary: "",
  notes: ""
};

const qualityOptions = [
  ["pending_review", "待复查"],
  ["excellent", "高价值"],
  ["good", "可复用"],
  ["normal", "普通"],
  ["reference", "仅参考"],
  ["rejected", "不建议"]
];

const statusOptions = [
  ["pending_review", "待复查"],
  ["active", "可用"],
  ["featured", "精选"],
  ["reference", "仅参考"],
  ["archived", "已归档"],
  ["rejected", "拒绝"]
];

function parseError(error: unknown) {
  if (!(error instanceof Error)) return "";
  try {
    return (JSON.parse(error.message) as { detail?: string }).detail || error.message;
  } catch {
    return error.message;
  }
}

function formFromRepo(repo: Repo): RepoForm {
  return {
    repo_url: repo.repo_url || repo.canonical_url,
    repo_name: repo.repo_name || "",
    owner: repo.owner || "",
    category: repo.category || "image_generation_prompt",
    quality_level: repo.quality_level || "pending_review",
    status: repo.status || "pending_review",
    license: repo.license || "unknown",
    stars: String(repo.stars || 0),
    forks: String(repo.forks || 0),
    summary: repo.summary || "",
    notes: ""
  };
}

function payloadFromForm(form: RepoForm): RepoPayload {
  return {
    repo_url: form.repo_url.trim(),
    repo_name: form.repo_name.trim() || undefined,
    owner: form.owner.trim() || undefined,
    category: form.category,
    quality_level: form.quality_level,
    status: form.status,
    license: form.license.trim() || "unknown",
    stars: Number(form.stars) || 0,
    forks: Number(form.forks) || 0,
    summary: form.summary.trim(),
    notes: form.notes.trim()
  };
}

function RepoFormFields({ form, setForm }: { form: RepoForm; setForm: (form: RepoForm) => void }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <label className="space-y-2 md:col-span-2">
        <span className="text-xs text-muted-foreground">GitHub 仓库地址</span>
        <Input placeholder="https://github.com/owner/repo" value={form.repo_url} onChange={(event) => setForm({ ...form, repo_url: event.target.value })} />
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">仓库名</span>
        <Input placeholder="留空则从 URL 自动解析" value={form.repo_name} onChange={(event) => setForm({ ...form, repo_name: event.target.value })} />
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">Owner</span>
        <Input placeholder="留空则从 URL 自动解析" value={form.owner} onChange={(event) => setForm({ ...form, owner: event.target.value })} />
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">分类</span>
        <Select value={form.category} onValueChange={(value) => setForm({ ...form, category: value })}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(categoryLabels).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">License</span>
        <Input value={form.license} onChange={(event) => setForm({ ...form, license: event.target.value })} />
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">推荐等级</span>
        <Select value={form.quality_level} onValueChange={(value) => setForm({ ...form, quality_level: value })}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {qualityOptions.map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">状态</span>
        <Select value={form.status} onValueChange={(value) => setForm({ ...form, status: value })}>
          <SelectTrigger className="w-full">
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
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">Stars</span>
        <Input type="number" min={0} value={form.stars} onChange={(event) => setForm({ ...form, stars: event.target.value })} />
      </label>
      <label className="space-y-2">
        <span className="text-xs text-muted-foreground">Forks</span>
        <Input type="number" min={0} value={form.forks} onChange={(event) => setForm({ ...form, forks: event.target.value })} />
      </label>
      <label className="space-y-2 md:col-span-2">
        <span className="text-xs text-muted-foreground">一句话总结</span>
        <Textarea value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
      </label>
      <label className="space-y-2 md:col-span-2">
        <span className="text-xs text-muted-foreground">备注</span>
        <Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
      </label>
    </div>
  );
}

export function ReposPage() {
  const { category, qualityLevel } = useFilterStore();
  const [repoSearch, setRepoSearch] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 40;
  const { data, isLoading } = useRepos({
    page,
    page_size: pageSize,
    search: repoSearch,
    category,
    quality_level: qualityLevel
  });
  const scanRepo = useScanRepo();
  const batchScanRepos = useBatchScanRepos();
  const createRepo = useCreateRepo();
  const updateRepo = useUpdateRepo();
  const deleteRepo = useDeleteRepo();
  const batchDeleteRepos = useBatchDeleteRepos();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [createForm, setCreateForm] = useState(defaultForm);
  const [editForm, setEditForm] = useState(defaultForm);
  const [editingRepoId, setEditingRepoId] = useState<number | null>(null);
  const [selectedRepoIds, setSelectedRepoIds] = useState<number[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);
  const [scanDialogRepo, setScanDialogRepo] = useState<Repo | null>(null);

  useEffect(() => {
    setPage(1);
  }, [repoSearch, category, qualityLevel]);

  useEffect(() => {
    const visibleIds = new Set((data?.items || []).map((repo) => repo.id));
    setSelectedRepoIds((prev) => {
      const next = prev.filter((id) => visibleIds.has(id));
      return next.length === prev.length ? prev : next;
    });
  }, [data?.items]);

  useEffect(() => {
    if (!selectedRepo) return;
    const updatedRepo = (data?.items || []).find((repo) => repo.id === selectedRepo.id);
    if (updatedRepo && updatedRepo !== selectedRepo) setSelectedRepo(updatedRepo);
  }, [data?.items, selectedRepo]);

  const submitCreate = (event: FormEvent) => {
    event.preventDefault();
    createRepo.mutate(payloadFromForm(createForm), {
      onSuccess: () => {
        setCreateForm(defaultForm);
        setCreateOpen(false);
      }
    });
  };

  const openEdit = (repo: Repo) => {
    setEditingRepoId(repo.id);
    setEditForm(formFromRepo(repo));
    setEditOpen(true);
  };

  const submitEdit = (event: FormEvent) => {
    event.preventDefault();
    if (!editingRepoId) return;
    updateRepo.mutate(
      { id: editingRepoId, payload: payloadFromForm(editForm) },
      {
        onSuccess: () => {
          setEditOpen(false);
          setEditingRepoId(null);
        }
      }
    );
  };

  const handleDelete = (repo: Repo) => {
    const ok = window.confirm(`删除资源「${repo.repo_name}」？该仓库下的效果对、候选和资产索引会一起从 SQLite 删除。`);
    if (ok) {
      deleteRepo.mutate(repo.id, {
        onSuccess: () => {
          setSelectedRepoIds((prev) => prev.filter((id) => id !== repo.id));
          if (selectedRepo?.id === repo.id) setSelectedRepo(null);
        }
      });
    }
  };

  const handleBatchScan = () => {
    if (!selectedRepoIds.length) return;
    batchScanRepos.mutate(selectedRepoIds, {
      onSuccess: () => {
        setSelectedRepoIds([]);
      }
    });
  };

  const handleBatchDelete = () => {
    if (!selectedRepoIds.length) return;
    const ok = window.confirm(`批量删除 ${selectedRepoIds.length} 个资源？这些仓库下的效果对、候选和资产索引会一起从 SQLite 删除。`);
    if (!ok) return;
    batchDeleteRepos.mutate(selectedRepoIds, {
      onSuccess: () => {
        if (selectedRepo && selectedRepoIds.includes(selectedRepo.id)) setSelectedRepo(null);
        setSelectedRepoIds([]);
      }
    });
  };

  const handleOpenScan = (repo: Repo) => {
    setScanDialogRepo(repo);
  };

  const handleScan = (repo: Repo, payload: RepoScanPayload = {}) => {
    scanRepo.mutate(
      { id: repo.id, payload },
      {
        onSuccess: () => {
          setScanDialogRepo(null);
        }
      }
    );
  };

  const batchBusy = batchScanRepos.isPending || batchDeleteRepos.isPending;
  const activeError = createRepo.error || updateRepo.error || deleteRepo.error || scanRepo.error || batchScanRepos.error || batchDeleteRepos.error;

  return (
    <div>
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs text-muted-foreground">GitHub Repository Index</div>
          <h1 className="text-2xl font-semibold">资源库</h1>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" />
              新增资源
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <form onSubmit={submitCreate} className="space-y-4">
              <DialogHeader>
                <DialogTitle>新增仓库资源</DialogTitle>
                <DialogDescription>手动加入资源库后，可以在表格右侧点击“扫描”抽取该仓库里的 Prompt 和效果图。</DialogDescription>
              </DialogHeader>
              <RepoFormFields form={createForm} setForm={setCreateForm} />
              {createRepo.error && <div className="text-sm text-destructive">{parseError(createRepo.error)}</div>}
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={createRepo.isPending}>
                  <Save className="h-4 w-4" />
                  保存
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-2xl">
          <form onSubmit={submitEdit} className="space-y-4">
            <DialogHeader>
              <DialogTitle>编辑仓库资源</DialogTitle>
              <DialogDescription>只更新资源库索引信息，不会覆盖已经人工整理过的 Prompt 内容。</DialogDescription>
            </DialogHeader>
            <RepoFormFields form={editForm} setForm={setEditForm} />
            {updateRepo.error && <div className="text-sm text-destructive">{parseError(updateRepo.error)}</div>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                取消
              </Button>
              <Button type="submit" disabled={updateRepo.isPending}>
                <Save className="h-4 w-4" />
                保存修改
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <FilterBar
        showSelection={false}
        onReset={() => {
          setRepoSearch("");
          setSelectedRepoIds([]);
        }}
        leading={
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={repoSearch}
              onChange={(event) => setRepoSearch(event.target.value)}
              placeholder="搜索仓库名、Owner、GitHub 地址、License、分类、摘要、备注..."
              className="h-10 pl-9 pr-10"
            />
            {repoSearch && (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="absolute right-2 top-1/2 -translate-y-1/2"
                onClick={() => setRepoSearch("")}
                aria-label="清空资源库搜索"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        }
        trailing={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="text-xs text-muted-foreground">
              已选 {selectedRepoIds.length} / 当前结果 {data?.total ?? 0}
            </span>
            <Button type="button" variant="secondary" size="sm" disabled={!selectedRepoIds.length || batchBusy} onClick={handleBatchScan}>
              <RefreshCw className={batchScanRepos.isPending ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              批量扫描
            </Button>
            <Button type="button" variant="destructive" size="sm" disabled={!selectedRepoIds.length || batchBusy} onClick={handleBatchDelete}>
              <Trash2 className={batchDeleteRepos.isPending ? "h-4 w-4 animate-pulse" : "h-4 w-4"} />
              批量删除
            </Button>
          </div>
        }
      />

      {batchDeleteRepos.data && (
        <Card className="mb-4">
          <CardContent className="p-4 text-sm text-muted-foreground">
            批量删除完成：已删除 {batchDeleteRepos.data.deleted_count} 个资源
            {batchDeleteRepos.data.missing_ids.length ? `，未找到 ${batchDeleteRepos.data.missing_ids.length} 个。` : "。"}
          </CardContent>
        </Card>
      )}
      {activeError instanceof Error && (
        <Card className="mb-4 border-destructive/50">
          <CardContent className="p-4 text-sm text-destructive">{parseError(activeError)}</CardContent>
        </Card>
      )}
      {isLoading ? (
        <Card>
          <CardContent className="p-10 text-muted-foreground">加载资源中...</CardContent>
        </Card>
      ) : (
        <RepoTable
          data={data?.items || []}
          selectedIds={selectedRepoIds}
          onSelectionChange={setSelectedRepoIds}
          onOpenRepo={setSelectedRepo}
          scanningRepoIds={[]}
          deletingRepoId={deleteRepo.isPending ? deleteRepo.variables ?? null : null}
          batchBusy={batchBusy}
          onScanRepo={handleOpenScan}
          onEditRepo={openEdit}
          onDeleteRepo={handleDelete}
        />
      )}
      {!isLoading && <PaginationBar className="mt-4" page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} />}
      <RepoDetailDrawer
        repo={selectedRepo}
        onClose={() => setSelectedRepo(null)}
        onScan={handleOpenScan}
        onEdit={openEdit}
        onDelete={handleDelete}
        busy={Boolean(scanRepo.isPending || deleteRepo.isPending || batchBusy)}
      />
      <RepoScanDialog
        repo={scanDialogRepo}
        open={Boolean(scanDialogRepo)}
        onOpenChange={(open) => !open && setScanDialogRepo(null)}
        onScan={handleScan}
        busy={scanRepo.isPending}
      />
    </div>
  );
}
