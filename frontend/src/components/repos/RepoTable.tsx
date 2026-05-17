import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { ExternalLink, Image, Link2, Pencil, RefreshCw, Star, Trash2 } from "lucide-react";
import { categoryLabels } from "../../lib/constants";
import type { Repo } from "../../lib/types";
import { QualityBadge } from "../prompts/QualityBadge";
import { StatusBadge } from "../prompts/StatusBadge";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";

type RepoTableProps = {
  data: Repo[];
  selectedIds?: number[];
  onSelectionChange?: (ids: number[]) => void;
  onOpenRepo?: (repo: Repo) => void;
  onScanRepo?: (repo: Repo) => void;
  onEditRepo?: (repo: Repo) => void;
  onDeleteRepo?: (repo: Repo) => void;
  scanningRepoIds?: number[];
  deletingRepoId?: number | null;
  batchBusy?: boolean;
};

function splitIsoDateTime(value?: string | null) {
  if (!value) return null;
  const cleaned = value.replace(/([+-]\d{2}:\d{2}|Z)$/i, "");
  const [date, rawTime = ""] = cleaned.split("T");
  if (!date) return null;
  return {
    date,
    time: rawTime.slice(0, 8)
  };
}

function DateTimeStack({ value }: { value?: string | null }) {
  const parts = splitIsoDateTime(value);
  if (!parts) return <span className="text-xs text-muted-foreground">-</span>;
  return (
    <span className="inline-flex flex-col text-xs leading-5 text-muted-foreground">
      <span>{parts.date}</span>
      <span>{parts.time || "-"}</span>
    </span>
  );
}

function mergeSelection(selectedIds: number[], visibleIds: number[], checked: boolean) {
  const next = new Set(selectedIds);
  visibleIds.forEach((id) => {
    if (checked) next.add(id);
    else next.delete(id);
  });
  return Array.from(next);
}

function columns(props: RepoTableProps): ColumnDef<Repo>[] {
  const {
    data,
    selectedIds = [],
    onSelectionChange,
    onScanRepo,
    onEditRepo,
    onDeleteRepo,
    scanningRepoIds = [],
    deletingRepoId,
    batchBusy
  } = props;
  const selectedSet = new Set(selectedIds);
  const scanningSet = new Set(scanningRepoIds);
  const visibleIds = data.map((repo) => repo.id);
  const selectedVisibleCount = visibleIds.filter((id) => selectedSet.has(id)).length;
  const allVisibleSelected = visibleIds.length > 0 && selectedVisibleCount === visibleIds.length;
  const someVisibleSelected = selectedVisibleCount > 0 && !allVisibleSelected;

  return [
    {
      id: "select",
      header: () => (
        <div onClick={(event) => event.stopPropagation()}>
          <Checkbox
            checked={allVisibleSelected ? true : someVisibleSelected ? "indeterminate" : false}
            disabled={!visibleIds.length || batchBusy}
            onCheckedChange={(checked) => onSelectionChange?.(mergeSelection(selectedIds, visibleIds, checked === true))}
            aria-label="全选当前列表"
          />
        </div>
      ),
      cell: ({ row }) => {
        const repo = row.original;
        return (
          <div onClick={(event) => event.stopPropagation()}>
            <Checkbox
              checked={selectedSet.has(repo.id)}
              disabled={batchBusy}
              onCheckedChange={(checked) => {
                const next = new Set(selectedIds);
                if (checked === true) next.add(repo.id);
                else next.delete(repo.id);
                onSelectionChange?.(Array.from(next));
              }}
              aria-label={`选择 ${repo.repo_name}`}
            />
          </div>
        );
      }
    },
    {
      accessorKey: "repo_name",
      header: "资源",
      cell: ({ row }) => (
        <div className="min-w-0">
          <div className="truncate font-medium" title={row.original.repo_name}>
            {row.original.repo_name}
          </div>
          <div className="mt-1 flex items-center gap-1 truncate text-xs text-muted-foreground">
            <Link2 className="h-3 w-3 shrink-0" />
            {row.original.owner}
          </div>
        </div>
      )
    },
    {
      accessorKey: "category",
      header: "分类",
      cell: ({ row }) => <Badge>{categoryLabels[row.original.category] || row.original.category}</Badge>
    },
    {
      accessorKey: "stars",
      header: "Star",
      cell: ({ row }) => (
        <span className="inline-flex items-center gap-1">
          <Star className="h-3.5 w-3.5" />
          {row.original.stars}
        </span>
      )
    },
    {
      accessorKey: "quality_level",
      header: "等级",
      cell: ({ row }) => <QualityBadge value={row.original.quality_level} />
    },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => <StatusBadge value={row.original.status} />
    },
    {
      accessorKey: "has_preview_images",
      header: "图片",
      cell: ({ row }) => (
        <Badge variant={row.original.has_preview_images ? "secondary" : "outline"}>
          <Image className="mr-1 h-3 w-3" />
          {row.original.has_preview_images ? "有" : "无"}
        </Badge>
      )
    },
    {
      accessorKey: "prompt_effect_pair_count",
      header: "效果对",
      cell: ({ row }) => <span className="text-sm">{row.original.prompt_effect_pair_count}</span>
    },
    {
      accessorKey: "last_checked_at",
      header: "最近检查",
      cell: ({ row }) => <DateTimeStack value={row.original.last_checked_at} />
    },
    {
      id: "actions",
      header: "操作",
      cell: ({ row }) => {
        const repo = row.original;
        const isScanning = scanningSet.has(repo.id);
        const isDeleting = deletingRepoId === repo.id;
        const rowBusy = Boolean(isScanning || isDeleting || batchBusy);
        return (
          <div className="flex justify-end gap-1.5" onClick={(event) => event.stopPropagation()}>
            <Button variant="secondary" size="sm" disabled={!onScanRepo || rowBusy} onClick={() => onScanRepo?.(repo)} title="扫描仓库内部文件">
              <RefreshCw className={isScanning ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              扫描
            </Button>
            <Button variant="outline" size="icon-sm" disabled={rowBusy} onClick={() => onEditRepo?.(repo)} title="编辑资源">
              <Pencil className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon-sm" disabled={batchBusy} onClick={() => window.open(repo.repo_url, "_blank")} title="打开 GitHub">
              <ExternalLink className="h-4 w-4" />
            </Button>
            <Button variant="destructive" size="icon-sm" disabled={!onDeleteRepo || rowBusy} onClick={() => onDeleteRepo?.(repo)} title="删除资源">
              {isDeleting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            </Button>
          </div>
        );
      }
    }
  ];
}

export function RepoTable(props: RepoTableProps) {
  const tableColumns = columns(props);
  const table = useReactTable({ data: props.data, columns: tableColumns, getCoreRowModel: getCoreRowModel() });
  const selectedSet = new Set(props.selectedIds || []);
  return (
    <Card className="overflow-hidden">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((group) => (
            <TableRow key={group.id}>
              {group.headers.map((header) => (
                <TableHead key={header.id}>{header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}</TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow
              key={row.id}
              className={selectedSet.has(row.original.id) ? "cursor-pointer bg-primary/5" : "cursor-pointer"}
              onClick={() => props.onOpenRepo?.(row.original)}
            >
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
              ))}
            </TableRow>
          ))}
          {!props.data.length && (
            <TableRow>
              <TableCell colSpan={tableColumns.length} className="h-28 text-center text-muted-foreground">
                暂无资源。先通过 GitHub 仓库发现任务加入资源库，或手动新增仓库。
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </Card>
  );
}
