import { useState } from "react";
import type { PromptPair, PromptPairPatch } from "../lib/types";
import { PromptDetailDrawer } from "../components/prompts/PromptDetailDrawer";
import { QualitySwipeDeck } from "../components/prompts/QualitySwipeDeck";
import { usePromptPairs, useUpdatePromptPair } from "../hooks/usePromptPairs";

export function PendingReviewPage() {
  const [selected, setSelected] = useState<PromptPair | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const updateMutation = useUpdatePromptPair();
  const { data } = usePromptPairs({ page, page_size: pageSize, selection_status: "pending_review" });
  const pairs = data?.items || [];
  const update = (payload: PromptPairPatch) => {
    if (!selected) return;
    updateMutation.mutate({ id: selected.id, payload });
    setSelected({ ...selected, ...payload } as PromptPair);
  };
  return (
    <div className="space-y-5">
      <QualitySwipeDeck
        pairs={pairs}
        total={data?.total || 0}
        page={page}
        pageSize={pageSize}
        isUpdating={updateMutation.isPending}
        onOpen={setSelected}
        onDecision={(id, status) => updateMutation.mutate({ id, payload: { selection_status: status } })}
        onPageChange={setPage}
      />
      <PromptDetailDrawer pair={selected} onClose={() => setSelected(null)} onUpdate={update} />
    </div>
  );
}
