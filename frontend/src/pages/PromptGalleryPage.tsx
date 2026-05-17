import { useEffect, useState } from "react";
import type { PromptPair, PromptPairPatch } from "../lib/types";
import { FilterBar } from "../components/filters/FilterBar";
import { PaginationBar } from "../components/navigation/PaginationBar";
import { CandidateAssetGrid } from "../components/prompts/CandidateAssetGrid";
import { PromptMasonryGrid } from "../components/prompts/PromptMasonryGrid";
import { PromptDetailDrawer } from "../components/prompts/PromptDetailDrawer";
import { Card, CardContent } from "../components/ui/card";
import { useAssets } from "../hooks/useAssets";
import { usePromptPairs, useUpdatePromptPair } from "../hooks/usePromptPairs";
import { useFilterStore } from "../stores/useFilterStore";

export function PromptGalleryPage({ pendingOnly = false }: { pendingOnly?: boolean }) {
  const [selected, setSelected] = useState<PromptPair | null>(null);
  const [page, setPage] = useState(1);
  const [assetPage, setAssetPage] = useState(1);
  const pageSize = pendingOnly ? 60 : 80;
  const assetPageSize = 24;
  const { globalSearch, category, qualityLevel, selectionStatus } = useFilterStore();
  const updateMutation = useUpdatePromptPair();
  const { data, isLoading } = usePromptPairs({
    page,
    page_size: pageSize,
    search: globalSearch,
    category,
    quality_level: qualityLevel,
    selection_status: pendingOnly ? "pending_review" : selectionStatus,
    has_image: true
  });
  const { data: assetData, isLoading: isAssetsLoading } = useAssets({
    page: assetPage,
    page_size: assetPageSize,
    search: globalSearch,
    category
  });
  const pairs = data?.items || [];
  const candidateAssets = assetData?.items || [];
  useEffect(() => {
    setPage(1);
    setAssetPage(1);
  }, [globalSearch, category, qualityLevel, selectionStatus, pendingOnly]);

  const update = (payload: PromptPairPatch) => {
    if (!selected) return;
    updateMutation.mutate({ id: selected.id, payload });
    setSelected({ ...selected, ...payload } as PromptPair);
  };
  const quickStatus = (id: number, status: string) => updateMutation.mutate({ id, payload: { selection_status: status } });

  return (
    <div>
      <div className="mb-5">
        <div className="text-xs text-muted-foreground">{pendingOnly ? "Review Queue" : "Prompt Effect Pairs"}</div>
        <h1 className="text-2xl font-semibold">{pendingOnly ? "待复查" : "Prompt 效果图瀑布流"}</h1>
      </div>
      {!pendingOnly && <FilterBar />}
      {isLoading ? (
        <Card>
          <CardContent className="p-10 text-muted-foreground">加载 Prompt 效果图中...</CardContent>
        </Card>
      ) : (
        <div className="space-y-5">
          <PromptMasonryGrid pairs={pairs} onOpen={setSelected} onQuickStatus={quickStatus} />
          <PaginationBar page={page} pageSize={pageSize} total={data?.total || 0} onPageChange={setPage} isLoading={isLoading} />
          {!pendingOnly && !pairs.length && (
            <>
              <CandidateAssetGrid assets={candidateAssets} isLoading={isAssetsLoading} />
              <PaginationBar page={assetPage} pageSize={assetPageSize} total={assetData?.total || 0} onPageChange={setAssetPage} isLoading={isAssetsLoading} />
            </>
          )}
        </div>
      )}
      <PromptDetailDrawer pair={selected} onClose={() => setSelected(null)} onUpdate={update} />
    </div>
  );
}
