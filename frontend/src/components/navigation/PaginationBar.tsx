import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "../ui/button";

type PaginationBarProps = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  isLoading?: boolean;
  className?: string;
};

export function PaginationBar({ page, pageSize, total, onPageChange, isLoading, className }: PaginationBarProps) {
  const totalPages = Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  const currentPage = Math.min(Math.max(1, page), totalPages);
  const start = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = Math.min(total, currentPage * pageSize);

  return (
    <div className={`flex flex-col gap-3 rounded-lg border bg-muted/10 p-3 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between ${className || ""}`}>
      <div>
        共 {total} 条，当前 {start}-{end} 条，每页 {pageSize} 条
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={isLoading || currentPage <= 1} onClick={() => onPageChange(currentPage - 1)}>
          <ChevronLeft className="h-4 w-4" />
          上一页
        </Button>
        <span className="min-w-20 text-center">
          {currentPage} / {totalPages}
        </span>
        <Button variant="outline" size="sm" disabled={isLoading || currentPage >= totalPages} onClick={() => onPageChange(currentPage + 1)}>
          下一页
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
