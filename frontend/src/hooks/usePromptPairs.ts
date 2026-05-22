import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { PromptPairBatchUpdate, PromptPairPatch } from "../lib/types";

export function usePromptPairs(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["prompt-pairs", filters], queryFn: () => api.promptPairs(filters) });
}

export function useUpdatePromptPair() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: PromptPairPatch }) => api.updatePromptPair(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompt-pairs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useBatchUpdatePromptPairs() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PromptPairBatchUpdate) => api.batchUpdatePromptPairs(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompt-pairs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}
