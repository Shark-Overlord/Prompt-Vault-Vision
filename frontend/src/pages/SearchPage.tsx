import { useEffect, useState } from "react";
import { FilterBar } from "../components/filters/FilterBar";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { PromptMasonryGrid } from "../components/prompts/PromptMasonryGrid";
import { PromptDetailDrawer } from "../components/prompts/PromptDetailDrawer";
import { usePromptPairs, useUpdatePromptPair } from "../hooks/usePromptPairs";
import { useFilterStore } from "../stores/useFilterStore";
import type { PromptPair, PromptPairPatch } from "../lib/types";

export function SearchPage() {
  const [selected, setSelected] = useState<PromptPair | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 80;
  const { globalSearch, category, qualityLevel, selectionStatus } = useFilterStore();
  const updateMutation = useUpdatePromptPair();
  const { data } = usePromptPairs({
    page,
    page_size: pageSize,
    search: globalSearch,
    category,
    quality_level: qualityLevel,
    selection_status: selectionStatus
  });
  useEffect(() => {
    setPage(1);
  }, [globalSearch, category, qualityLevel, selectionStatus]);

  const update = (payload: PromptPairPatch) => {
    if (!selected) return;
    updateMutation.mutate({ id: selected.id, payload });
    setSelected({ ...selected, ...payload } as PromptPair);
  };
  return (
    <div>
      <div className="mb-5">
        <div className="text-xs text-muted-foreground">Full Text Search</div>
        <h1 className="text-2xl font-semibold">组合搜索</h1>
      </div>
      <FilterBar />
      <PromptMasonryGrid pairs={data?.items || []} onOpen={setSelected} onQuickStatus={(id, status) => updateMutation.mutate({ id, payload: { selection_status: status } })} />
      <PaginationBar className="mt-5" page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} />
      <PromptDetailDrawer pair={selected} onClose={() => setSelected(null)} onUpdate={update} />
    </div>
  );
}
